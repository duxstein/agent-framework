"""
Executor Worker for Enterprise AI Agent Framework.

This module provides the executor worker that processes tasks from the task queue,
executes them using dynamic connector loading, and handles success/failure scenarios
with comprehensive monitoring and idempotency support.
"""

import asyncio
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
import traceback
import importlib
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing

import structlog
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import threading

# Add the parent directory to Python path for SDK imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.registry import ConnectorRegistry
from executor.config import config


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class ExecutionMode(Enum):
    """Execution mode for connectors."""
    ASYNC = "async"
    SYNC = "sync"
    CPU_INTENSIVE = "cpu_intensive"


class TaskExecutionResult:
    """Result of task execution."""
    
    def __init__(
        self,
        task_id: str,
        run_id: str,
        success: bool,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: int = 0,
        execution_mode: ExecutionMode = ExecutionMode.SYNC
    ):
        self.task_id = task_id
        self.run_id = run_id
        self.success = success
        self.output = output
        self.error = error
        self.execution_time_ms = execution_time_ms
        self.execution_mode = execution_mode
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "execution_mode": self.execution_mode.value,
            "timestamp": self.timestamp.isoformat()
        }


# Prometheus metrics
TASK_DURATION_SECONDS = Histogram(
    'executor_task_duration_seconds', 
    'Task execution duration in seconds',
    ['handler', 'execution_mode', 'status']
)
TASK_SUCCESS_COUNT = Counter(
    'executor_task_success_count_total',
    'Total number of successful task executions',
    ['handler', 'execution_mode']
)
TASK_FAILURE_COUNT = Counter(
    'executor_task_failure_count_total',
    'Total number of failed task executions',
    ['handler', 'execution_mode', 'error_type']
)
TASK_RETRY_COUNT = Counter(
    'executor_task_retry_count_total',
    'Total number of task retries',
    ['handler', 'attempt']
)
TASK_DEAD_LETTER_COUNT = Counter(
    'executor_task_dead_letter_count_total',
    'Total number of tasks moved to dead letter queue',
    ['handler']
)
ACTIVE_TASKS = Gauge(
    'executor_active_tasks',
    'Number of currently active tasks'
)
CONNECTOR_LOAD_TIME = Histogram(
    'executor_connector_load_seconds',
    'Time taken to load connectors',
    ['handler']
)


class ExecutorWorker:
    """Main executor worker for processing tasks."""
    
    def __init__(
        self,
        kafka_bootstrap_servers: str,
        redis_url: str,
        database_url: str,
        connector_registry_url: str,
        metrics_port: int = 9091,
        max_workers: int = 10
    ):
        """Initialize the executor worker."""
        # Parse comma-separated kafka servers
        self.kafka_bootstrap_servers = [s.strip() for s in kafka_bootstrap_servers.split(',')]
        self.redis_url = redis_url
        self.database_url = database_url
        self.connector_registry_url = connector_registry_url
        self.metrics_port = metrics_port
        self.max_workers = max_workers
        
        # Initialize clients
        self.redis_client = redis.from_url(redis_url)
        self.connector_registry = ConnectorRegistry(connection_string=connector_registry_url)
        
        # Kafka consumers and producers
        self.task_queue_consumer = None
        self.task_done_producer = None
        self.task_failed_producer = None
        self.dead_letter_producer = None
        
        # Execution pools
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=min(max_workers, multiprocessing.cpu_count()))
        
        # Connector cache
        self.connector_cache: Dict[str, Any] = {}
        
        # Metrics server
        self.metrics_server = None
        
        # Configuration
        self.max_retry_attempts = config.max_retry_attempts
        self.task_timeout_default = config.task_timeout_default
        self.idempotency_ttl = config.idempotency_ttl
        
    async def start(self):
        """Start the executor worker."""
        logger.info("Starting Executor Worker")
        
        # Start metrics server
        self.metrics_server = start_http_server(self.metrics_port)
        logger.info(f"Metrics server started on port {self.metrics_port}")
        
        # Initialize Kafka clients
        await self._initialize_kafka_clients()
        
        # Initialize database schema
        await self._initialize_database_schema()
        
        # Start consumer
        await self._start_consumer()
        
        logger.info("Executor Worker started successfully")
    
    async def stop(self):
        """Stop the executor worker."""
        logger.info("Stopping Executor Worker")
        
        # Stop consumer
        if self.task_queue_consumer:
            self.task_queue_consumer.close()
        
        # Close producers
        if self.task_done_producer:
            self.task_done_producer.close()
        if self.task_failed_producer:
            self.task_failed_producer.close()
        if self.dead_letter_producer:
            self.dead_letter_producer.close()
        
        # Close execution pools
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        
        # Close Redis connection
        self.redis_client.close()
        
        logger.info("Executor Worker stopped")
    
    async def _initialize_kafka_clients(self):
        """Initialize Kafka consumers and producers."""
        try:
            # Task queue consumer
            self.task_queue_consumer = KafkaConsumer(
                'task_queue',
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id=config.kafka_consumer_group,
                auto_offset_reset=config.kafka_auto_offset_reset,
                enable_auto_commit=True
            )
            
            # Task done producer
            self.task_done_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            
            # Task failed producer
            self.task_failed_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            
            # Dead letter queue producer
            self.dead_letter_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            
            logger.info("Kafka clients initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Kafka clients", error=str(e))
            raise
    
    async def _initialize_database_schema(self):
        """Initialize database schema for task execution audit."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS task_execution_audit (
                id SERIAL PRIMARY KEY,
                run_id VARCHAR(255) NOT NULL,
                task_id VARCHAR(255) NOT NULL,
                handler VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                attempts INTEGER DEFAULT 0,
                execution_mode VARCHAR(50) DEFAULT 'sync',
                input_data JSONB,
                output_data JSONB,
                error_message TEXT,
                execution_time_ms INTEGER,
                worker_id VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE
            );
            
            CREATE INDEX IF NOT EXISTS idx_task_execution_audit_run_id ON task_execution_audit(run_id);
            CREATE INDEX IF NOT EXISTS idx_task_execution_audit_task_id ON task_execution_audit(task_id);
            CREATE INDEX IF NOT EXISTS idx_task_execution_audit_status ON task_execution_audit(status);
            CREATE INDEX IF NOT EXISTS idx_task_execution_audit_handler ON task_execution_audit(handler);
            """
            
            cursor.execute(create_table_query)
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Database schema initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database schema", error=str(e))
            raise
    
    async def _start_consumer(self):
        """Start Kafka consumer."""
        asyncio.create_task(self._consume_tasks())
        logger.info("Kafka consumer started")
    
    async def _consume_tasks(self):
        """Consume tasks from Kafka."""
        logger.info("Starting task consumer")
        
        for message in self.task_queue_consumer:
            try:
                await self._process_task(message.value)
            except Exception as e:
                logger.error("Failed to process task", error=str(e), message=message.value)
    
    async def _process_task(self, task_message: Dict[str, Any]):
        """Process a single task."""
        run_id = task_message.get('run_id')
        task_id = task_message.get('task_id')
        handler = task_message.get('handler')
        inputs = task_message.get('inputs', {})
        attempt = task_message.get('attempt', 0)
        max_retries = task_message.get('max_retries', 3)
        timeout = task_message.get('timeout', self.task_timeout_default)
        correlation_id = task_message.get('correlation_id')
        tenant_id = task_message.get('tenant_id')
        user_id = task_message.get('user_id')
        execution_context = task_message.get('execution_context', {})
        is_retry = task_message.get('is_retry', False)
        
        logger.info(
            "Processing task",
            run_id=run_id,
            task_id=task_id,
            handler=handler,
            attempt=attempt,
            is_retry=is_retry
        )
        
        # Check idempotency
        if not await self._check_idempotency(run_id, task_id):
            logger.info(
                "Task already processed, skipping",
                run_id=run_id,
                task_id=task_id
            )
            return
        
        # Mark task as running
        await self._mark_task_running(run_id, task_id, handler, inputs, attempt)
        
        try:
            # Execute task
            result = await self._execute_task(
                task_id=task_id,
                run_id=run_id,
                handler=handler,
                inputs=inputs,
                timeout=timeout,
                execution_context=execution_context
            )
            
            if result.success:
                await self._handle_task_success(result, correlation_id, tenant_id, user_id)
            else:
                await self._handle_task_failure(
                    result, attempt, max_retries, correlation_id, tenant_id, user_id
                )
                
        except Exception as e:
            logger.error(
                "Task execution failed with exception",
                run_id=run_id,
                task_id=task_id,
                handler=handler,
                error=str(e),
                traceback=traceback.format_exc()
            )
            
            # Create failure result
            result = TaskExecutionResult(
                task_id=task_id,
                run_id=run_id,
                success=False,
                error=str(e),
                execution_time_ms=0
            )
            
            await self._handle_task_failure(
                result, attempt, max_retries, correlation_id, tenant_id, user_id
            )
    
    async def _check_idempotency(self, run_id: str, task_id: str) -> bool:
        """Check if task has already been processed."""
        try:
            idempotency_key = f"run:{run_id}:task:{task_id}:status"
            
            # Check if task is already completed
            status = self.redis_client.get(idempotency_key)
            if status and status.decode('utf-8') in ['COMPLETED', 'FAILED']:
                return False
            
            # Set task as running with TTL
            self.redis_client.setex(
                idempotency_key,
                self.idempotency_ttl,
                'RUNNING'
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to check idempotency", run_id=run_id, task_id=task_id, error=str(e))
            return True  # Allow execution if idempotency check fails
    
    async def _mark_task_running(self, run_id: str, task_id: str, handler: str, inputs: Dict[str, Any], attempt: int):
        """Mark task as running in Redis and database."""
        try:
            # Update idempotency key
            idempotency_key = f"run:{run_id}:task:{task_id}:status"
            self.redis_client.setex(idempotency_key, self.idempotency_ttl, 'RUNNING')
            
            # Update database
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            upsert_query = """
            INSERT INTO task_execution_audit 
            (run_id, task_id, handler, status, attempts, input_data, execution_mode, worker_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, task_id) 
            DO UPDATE SET 
                status = EXCLUDED.status,
                attempts = EXCLUDED.attempts,
                input_data = EXCLUDED.input_data,
                execution_mode = EXCLUDED.execution_mode,
                worker_id = EXCLUDED.worker_id,
                updated_at = EXCLUDED.updated_at
            """
            
            cursor.execute(upsert_query, (
                run_id,
                task_id,
                handler,
                'RUNNING',
                attempt,
                json.dumps(inputs),
                'sync',  # Will be updated based on actual execution mode
                os.getenv('HOSTNAME', 'unknown'),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to mark task as running", run_id=run_id, task_id=task_id, error=str(e))
    
    async def _execute_task(
        self,
        task_id: str,
        run_id: str,
        handler: str,
        inputs: Dict[str, Any],
        timeout: int,
        execution_context: Dict[str, Any]
    ) -> TaskExecutionResult:
        """Execute a task using the appropriate connector."""
        start_time = time.time()
        
        try:
            # Load connector
            connector = await self._load_connector(handler)
            if not connector:
                raise ValueError(f"Connector not found for handler: {handler}")
            
            # Determine execution mode
            execution_mode = self._determine_execution_mode(connector, inputs, execution_context)
            
            # Execute based on mode
            if execution_mode == ExecutionMode.ASYNC:
                output = await self._execute_async(connector, inputs, timeout)
            elif execution_mode == ExecutionMode.CPU_INTENSIVE:
                output = await self._execute_cpu_intensive(connector, inputs, timeout)
            else:  # SYNC
                output = await self._execute_sync(connector, inputs, timeout)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return TaskExecutionResult(
                task_id=task_id,
                run_id=run_id,
                success=True,
                output=output,
                execution_time_ms=execution_time_ms,
                execution_mode=execution_mode
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return TaskExecutionResult(
                task_id=task_id,
                run_id=run_id,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
                execution_mode=execution_mode if 'execution_mode' in locals() else ExecutionMode.SYNC
            )
    
    async def _load_connector(self, handler: str) -> Optional[Any]:
        """Load connector dynamically."""
        try:
            # Check cache first
            if handler in self.connector_cache:
                return self.connector_cache[handler]
            
            start_time = time.time()
            
            # Load from registry
            connector_info = self.connector_registry.get_connector(handler)
            if not connector_info:
                logger.error("Connector not found in registry", handler=handler)
                return None
            
            # Import connector module
            module_path = connector_info.get('module_path')
            class_name = connector_info.get('class_name')
            
            if not module_path or not class_name:
                logger.error("Invalid connector configuration", handler=handler, connector_info=connector_info)
                return None
            
            # Import module
            module = importlib.import_module(module_path)
            connector_class = getattr(module, class_name)
            
            # Instantiate connector
            connector = connector_class()
            
            # Cache connector
            self.connector_cache[handler] = connector
            
            load_time = time.time() - start_time
            CONNECTOR_LOAD_TIME.labels(handler=handler).observe(load_time)
            
            logger.info("Connector loaded successfully", handler=handler, load_time=load_time)
            return connector
            
        except Exception as e:
            logger.error("Failed to load connector", handler=handler, error=str(e))
            return None
    
    def _determine_execution_mode(
        self,
        connector: Any,
        inputs: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> ExecutionMode:
        """Determine the appropriate execution mode for the connector."""
        try:
            # Check if connector has async methods
            if hasattr(connector, 'execute_action_async'):
                return ExecutionMode.ASYNC
            
            # Check if connector is CPU intensive
            if hasattr(connector, 'is_cpu_intensive') and connector.is_cpu_intensive():
                return ExecutionMode.CPU_INTENSIVE
            
            # Check execution context for hints
            if execution_context.get('execution_mode') == 'cpu_intensive':
                return ExecutionMode.CPU_INTENSIVE
            
            # Default to sync
            return ExecutionMode.SYNC
            
        except Exception as e:
            logger.warning("Failed to determine execution mode", error=str(e))
            return ExecutionMode.SYNC
    
    async def _execute_async(self, connector: Any, inputs: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """Execute connector asynchronously."""
        try:
            if hasattr(connector, 'execute_action_async'):
                return await asyncio.wait_for(
                    connector.execute_action_async(inputs),
                    timeout=timeout
                )
            else:
                # Fallback to sync execution in thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self.thread_pool,
                    connector.execute_action,
                    inputs
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task execution timed out after {timeout} seconds")
    
    async def _execute_sync(self, connector: Any, inputs: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """Execute connector synchronously in thread pool."""
        try:
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    self.thread_pool,
                    connector.execute_action,
                    inputs
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task execution timed out after {timeout} seconds")
    
    async def _execute_cpu_intensive(self, connector: Any, inputs: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """Execute CPU-intensive connector in process pool."""
        try:
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    self.process_pool,
                    connector.execute_action,
                    inputs
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task execution timed out after {timeout} seconds")
    
    async def _handle_task_success(
        self,
        result: TaskExecutionResult,
        correlation_id: str,
        tenant_id: str,
        user_id: str
    ):
        """Handle successful task execution."""
        try:
            # Update idempotency key
            idempotency_key = f"run:{result.run_id}:task:{result.task_id}:status"
            self.redis_client.setex(idempotency_key, self.idempotency_ttl, 'COMPLETED')
            
            # Store output in Redis
            output_key = f"run:{result.run_id}:outputs"
            self.redis_client.hset(
                output_key,
                result.task_id,
                json.dumps(result.output)
            )
            self.redis_client.expire(output_key, self.idempotency_ttl)
            
            # Update database
            await self._update_task_audit(result, 'COMPLETED')
            
            # Publish task done event
            task_done_message = {
                "run_id": result.run_id,
                "task_id": result.task_id,
                "output": result.output,
                "execution_time_ms": result.execution_time_ms,
                "execution_mode": result.execution_mode.value,
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "timestamp": result.timestamp.isoformat()
            }
            
            self.task_done_producer.send(
                'task_done',
                value=task_done_message,
                key=result.task_id
            )
            
            # Update metrics
            TASK_DURATION_SECONDS.labels(
                handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown',
                execution_mode=result.execution_mode.value,
                status='success'
            ).observe(result.execution_time_ms / 1000.0)
            
            TASK_SUCCESS_COUNT.labels(
                handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown',
                execution_mode=result.execution_mode.value
            ).inc()
            
            ACTIVE_TASKS.dec()
            
            logger.info(
                "Task completed successfully",
                run_id=result.run_id,
                task_id=result.task_id,
                execution_time_ms=result.execution_time_ms,
                execution_mode=result.execution_mode.value
            )
            
        except Exception as e:
            logger.error("Failed to handle task success", run_id=result.run_id, task_id=result.task_id, error=str(e))
    
    async def _handle_task_failure(
        self,
        result: TaskExecutionResult,
        attempt: int,
        max_retries: int,
        correlation_id: str,
        tenant_id: str,
        user_id: str
    ):
        """Handle failed task execution."""
        try:
            # Update idempotency key
            idempotency_key = f"run:{result.run_id}:task:{result.task_id}:status"
            
            if attempt >= max_retries:
                # Move to dead letter queue
                self.redis_client.setex(idempotency_key, self.idempotency_ttl, 'DEAD_LETTER')
                
                dead_letter_message = {
                    "run_id": result.run_id,
                    "task_id": result.task_id,
                    "error": result.error,
                    "attempts": attempt,
                    "max_retries": max_retries,
                    "execution_time_ms": result.execution_time_ms,
                    "execution_mode": result.execution_mode.value,
                    "correlation_id": correlation_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "timestamp": result.timestamp.isoformat(),
                    "moved_to_dlq_at": datetime.now(timezone.utc).isoformat()
                }
                
                self.dead_letter_producer.send(
                    config.dead_letter_queue_topic,
                    value=dead_letter_message,
                    key=result.task_id
                )
                
                # Update database
                await self._update_task_audit(result, 'DEAD_LETTER')
                
                # Update metrics
                TASK_DEAD_LETTER_COUNT.labels(
                    handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown'
                ).inc()
                
                logger.warning(
                    "Task moved to dead letter queue",
                    run_id=result.run_id,
                    task_id=result.task_id,
                    attempts=attempt,
                    max_retries=max_retries
                )
                
            else:
                # Publish task failed event for retry
                self.redis_client.setex(idempotency_key, self.idempotency_ttl, 'FAILED')
                
                task_failed_message = {
                    "run_id": result.run_id,
                    "task_id": result.task_id,
                    "error": result.error,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "execution_time_ms": result.execution_time_ms,
                    "execution_mode": result.execution_mode.value,
                    "correlation_id": correlation_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "timestamp": result.timestamp.isoformat()
                }
                
                self.task_failed_producer.send(
                    'task_failed',
                    value=task_failed_message,
                    key=result.task_id
                )
                
                # Update database
                await self._update_task_audit(result, 'FAILED')
                
                # Update metrics
                TASK_RETRY_COUNT.labels(
                    handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown',
                    attempt=attempt
                ).inc()
                
                logger.info(
                    "Task failed, will retry",
                    run_id=result.run_id,
                    task_id=result.task_id,
                    attempt=attempt,
                    max_retries=max_retries
                )
            
            # Update metrics
            TASK_DURATION_SECONDS.labels(
                handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown',
                execution_mode=result.execution_mode.value,
                status='failure'
            ).observe(result.execution_time_ms / 1000.0)
            
            TASK_FAILURE_COUNT.labels(
                handler=result.task_id.split('-')[0] if '-' in result.task_id else 'unknown',
                execution_mode=result.execution_mode.value,
                error_type=type(result.error).__name__ if result.error else 'unknown'
            ).inc()
            
            ACTIVE_TASKS.dec()
            
        except Exception as e:
            logger.error("Failed to handle task failure", run_id=result.run_id, task_id=result.task_id, error=str(e))
    
    async def _update_task_audit(self, result: TaskExecutionResult, status: str):
        """Update task execution audit in database."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            update_query = """
            UPDATE task_execution_audit 
            SET status = %s, output_data = %s, error_message = %s, 
                execution_time_ms = %s, execution_mode = %s, 
                completed_at = %s, updated_at = %s
            WHERE run_id = %s AND task_id = %s
            """
            
            cursor.execute(update_query, (
                status,
                json.dumps(result.output) if result.output else None,
                result.error,
                result.execution_time_ms,
                result.execution_mode.value,
                result.timestamp,
                result.timestamp,
                result.run_id,
                result.task_id
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to update task audit", run_id=result.run_id, task_id=result.task_id, error=str(e))


async def main():
    """Main function to run the executor worker."""
    executor = ExecutorWorker(
        kafka_bootstrap_servers=config.kafka_bootstrap_servers,
        redis_url=config.redis_url,
        database_url=config.database_url,
        connector_registry_url=config.connector_registry_url,
        metrics_port=config.metrics_port,
        max_workers=config.max_workers
    )
    
    try:
        await executor.start()
        
        # Keep the service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await executor.stop()


if __name__ == "__main__":
    asyncio.run(main())
