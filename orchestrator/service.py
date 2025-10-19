"""
Orchestrator Service for Enterprise AI Agent Framework.

This module provides the orchestrator service that manages workflow execution lifecycle,
including task scheduling, state management, retry handling, and metrics collection.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from enum import Enum
import time
import sys
import os

import structlog
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import threading

# Add the parent directory to Python path for SDK imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.models import Flow, Task
from sdk.registry import FlowRegistry, RegistryError
from orchestrator.config import config


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
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class RunStatus(Enum):
    """Flow run status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunState:
    """Represents the state of a flow run."""
    
    def __init__(
        self,
        run_id: str,
        flow_id: str,
        tenant_id: str,
        user_id: str,
        correlation_id: str,
        status: RunStatus = RunStatus.PENDING,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.run_id = run_id
        self.flow_id = flow_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.correlation_id = correlation_id
        self.status = status
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        
        # Task tracking
        self.tasks: Dict[str, TaskState] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.ready_tasks: Set[str] = set()
        
        # Execution context
        self.input_data: Dict[str, Any] = {}
        self.output_data: Dict[str, Any] = {}
        self.execution_context: Dict[str, Any] = {}
        
        # Retry tracking
        self.task_attempts: Dict[str, int] = {}
        self.max_retries: int = 3
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert run state to dictionary."""
        return {
            "run_id": self.run_id,
            "flow_id": self.flow_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tasks": {task_id: task_state.to_dict() for task_id, task_state in self.tasks.items()},
            "completed_tasks": list(self.completed_tasks),
            "failed_tasks": list(self.failed_tasks),
            "ready_tasks": list(self.ready_tasks),
            "input_data": self.input_data,
            "output_data": self.output_data,
            "execution_context": self.execution_context,
            "task_attempts": self.task_attempts,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunState':
        """Create run state from dictionary."""
        run_state = cls(
            run_id=data["run_id"],
            flow_id=data["flow_id"],
            tenant_id=data["tenant_id"],
            user_id=data["user_id"],
            correlation_id=data["correlation_id"],
            status=RunStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )
        
        # Restore task states
        for task_id, task_data in data.get("tasks", {}).items():
            run_state.tasks[task_id] = TaskState.from_dict(task_data)
        
        run_state.completed_tasks = set(data.get("completed_tasks", []))
        run_state.failed_tasks = set(data.get("failed_tasks", []))
        run_state.ready_tasks = set(data.get("ready_tasks", []))
        run_state.input_data = data.get("input_data", {})
        run_state.output_data = data.get("output_data", {})
        run_state.execution_context = data.get("execution_context", {})
        run_state.task_attempts = data.get("task_attempts", {})
        run_state.max_retries = data.get("max_retries", 3)
        
        return run_state


class TaskState:
    """Represents the state of a task within a run."""
    
    def __init__(
        self,
        task_id: str,
        handler: str,
        inputs: Dict[str, Any],
        status: TaskStatus = TaskStatus.PENDING,
        attempts: int = 0,
        max_retries: int = 3,
        timeout: int = 300,
        condition: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.handler = handler
        self.inputs = inputs
        self.status = status
        self.attempts = attempts
        self.max_retries = max_retries
        self.timeout = timeout
        self.condition = condition
        self.output = output
        self.error = error
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task state to dictionary."""
        return {
            "task_id": self.task_id,
            "handler": self.handler,
            "inputs": self.inputs,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "condition": self.condition,
            "output": self.output,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskState':
        """Create task state from dictionary."""
        return cls(
            task_id=data["task_id"],
            handler=data["handler"],
            inputs=data["inputs"],
            status=TaskStatus(data["status"]),
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            timeout=data.get("timeout", 300),
            condition=data.get("condition"),
            output=data.get("output"),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


# Prometheus metrics
FLOW_RUNS_PROCESSED = Counter('orchestrator_flow_runs_processed_total', 'Total flow runs processed')
TASKS_SCHEDULED = Counter('orchestrator_tasks_scheduled_total', 'Total tasks scheduled')
TASKS_COMPLETED = Counter('orchestrator_tasks_completed_total', 'Total tasks completed', ['status'])
TASK_EXECUTION_TIME = Histogram('orchestrator_task_execution_seconds', 'Task execution time', ['handler'])
RUN_EXECUTION_TIME = Histogram('orchestrator_run_execution_seconds', 'Run execution time')
ACTIVE_RUNS = Gauge('orchestrator_active_runs', 'Number of active runs')
ACTIVE_TASKS = Gauge('orchestrator_active_tasks', 'Number of active tasks')
RETRY_ATTEMPTS = Counter('orchestrator_retry_attempts_total', 'Total retry attempts', ['task_id', 'handler'])
DEAD_LETTER_QUEUE_SIZE = Gauge('orchestrator_dead_letter_queue_size', 'Size of dead letter queue')


class OrchestratorService:
    """Main orchestrator service for managing workflow execution."""
    
    def __init__(
        self,
        kafka_bootstrap_servers: str,
        redis_url: str,
        database_url: str,
        flow_registry_url: str,
        metrics_port: int = 9090
    ):
        """Initialize the orchestrator service."""
        # Parse comma-separated kafka servers
        self.kafka_bootstrap_servers = [s.strip() for s in kafka_bootstrap_servers.split(',')]
        self.redis_url = redis_url
        self.database_url = database_url
        self.flow_registry_url = flow_registry_url
        self.metrics_port = metrics_port
        
        # Initialize clients
        self.redis_client = redis.from_url(redis_url)
        self.flow_registry = FlowRegistry(connection_string=flow_registry_url)
        
        # Kafka consumers and producers
        self.flow_runs_consumer = None
        self.task_events_consumer = None
        self.task_queue_producer = None
        self.dead_letter_producer = None
        
        # State management
        self.active_runs: Dict[str, RunState] = {}
        self.dead_letter_queue: List[Dict[str, Any]] = []
        
        # Configuration
        self.max_retry_attempts = config.max_retry_attempts
        self.retry_backoff_base = config.retry_backoff_base  # Exponential backoff base
        self.task_timeout_default = config.task_timeout_default
        
        # Metrics server
        self.metrics_server = None
        
    async def start(self):
        """Start the orchestrator service."""
        logger.info("Starting Orchestrator Service")
        
        # Start metrics server
        self.metrics_server = start_http_server(self.metrics_port)
        logger.info(f"Metrics server started on port {self.metrics_port}")
        
        # Initialize Kafka clients
        await self._initialize_kafka_clients()
        
        # Initialize database schema
        await self._initialize_database_schema()
        
        # Start consumers
        await self._start_consumers()
        
        logger.info("Orchestrator Service started successfully")
    
    async def stop(self):
        """Stop the orchestrator service."""
        logger.info("Stopping Orchestrator Service")
        
        # Stop consumers
        if self.flow_runs_consumer:
            self.flow_runs_consumer.close()
        if self.task_events_consumer:
            self.task_events_consumer.close()
        
        # Close producers
        if self.task_queue_producer:
            self.task_queue_producer.close()
        if self.dead_letter_producer:
            self.dead_letter_producer.close()
        
        # Close Redis connection
        self.redis_client.close()
        
        logger.info("Orchestrator Service stopped")
    
    async def _initialize_kafka_clients(self):
        """Initialize Kafka consumers and producers."""
        try:
            # Flow runs consumer
            self.flow_runs_consumer = KafkaConsumer(
                'flow_runs',
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id=config.kafka_consumer_group,
                auto_offset_reset=config.kafka_auto_offset_reset,
                enable_auto_commit=config.kafka_enable_auto_commit
            )
            
            # Task events consumer
            self.task_events_consumer = KafkaConsumer(
                'task_done', 'task_failed',
                bootstrap_servers=self.kafka_bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id=config.kafka_consumer_group,
                auto_offset_reset=config.kafka_auto_offset_reset,
                enable_auto_commit=config.kafka_enable_auto_commit
            )
            
            # Task queue producer
            self.task_queue_producer = KafkaProducer(
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
        """Initialize database schema for flow run history."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS flow_run_history (
                id SERIAL PRIMARY KEY,
                run_id VARCHAR(255) UNIQUE NOT NULL,
                flow_id VARCHAR(255) NOT NULL,
                tenant_id VARCHAR(255) NOT NULL,
                user_id VARCHAR(255) NOT NULL,
                correlation_id VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                input_data JSONB,
                output_data JSONB,
                execution_context JSONB,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE
            );
            
            CREATE TABLE IF NOT EXISTS task_execution_history (
                id SERIAL PRIMARY KEY,
                run_id VARCHAR(255) NOT NULL,
                task_id VARCHAR(255) NOT NULL,
                handler VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL,
                attempts INTEGER DEFAULT 0,
                input_data JSONB,
                output_data JSONB,
                error_message TEXT,
                execution_time_ms INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                completed_at TIMESTAMP WITH TIME ZONE
            );
            
            CREATE INDEX IF NOT EXISTS idx_flow_run_history_run_id ON flow_run_history(run_id);
            CREATE INDEX IF NOT EXISTS idx_flow_run_history_tenant_id ON flow_run_history(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_flow_run_history_status ON flow_run_history(status);
            CREATE INDEX IF NOT EXISTS idx_task_execution_history_run_id ON task_execution_history(run_id);
            CREATE INDEX IF NOT EXISTS idx_task_execution_history_task_id ON task_execution_history(task_id);
            CREATE INDEX IF NOT EXISTS idx_task_execution_history_status ON task_execution_history(status);
            """
            
            cursor.execute(create_table_query)
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Database schema initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database schema", error=str(e))
            raise
    
    async def _start_consumers(self):
        """Start Kafka consumers."""
        # Start flow runs consumer
        asyncio.create_task(self._consume_flow_runs())
        
        # Start task events consumer
        asyncio.create_task(self._consume_task_events())
        
        logger.info("Kafka consumers started")
    
    async def _consume_flow_runs(self):
        """Consume flow run events from Kafka."""
        logger.info("Starting flow runs consumer")
        
        for message in self.flow_runs_consumer:
            try:
                await self._process_flow_run_event(message.value)
                FLOW_RUNS_PROCESSED.inc()
            except Exception as e:
                logger.error("Failed to process flow run event", error=str(e), message=message.value)
    
    async def _consume_task_events(self):
        """Consume task completion events from Kafka."""
        logger.info("Starting task events consumer")
        
        for message in self.task_events_consumer:
            try:
                if message.topic == 'task_done':
                    await self._process_task_done_event(message.value)
                elif message.topic == 'task_failed':
                    await self._process_task_failed_event(message.value)
                
                TASKS_COMPLETED.labels(status=message.topic).inc()
            except Exception as e:
                logger.error("Failed to process task event", error=str(e), message=message.value)
    
    async def _process_flow_run_event(self, event: Dict[str, Any]):
        """Process a flow run event."""
        run_id = event.get('run_id')
        flow_id = event.get('flow_id')
        tenant_id = event.get('tenant_id')
        user_id = event.get('user_id')
        correlation_id = event.get('correlation_id')
        input_data = event.get('input', {})
        flow_definition = event.get('flow_definition')
        execution_context = event.get('execution_context', {})
        
        logger.info(
            "Processing flow run event",
            run_id=run_id,
            flow_id=flow_id,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        try:
            # Load flow definition
            if flow_definition:
                flow = Flow(**flow_definition)
            else:
                flow = self.flow_registry.get_flow(flow_id)
                if not flow:
                    raise ValueError(f"Flow {flow_id} not found in registry")
            
            # Create run state
            run_state = RunState(
                run_id=run_id,
                flow_id=flow_id,
                tenant_id=tenant_id,
                user_id=user_id,
                correlation_id=correlation_id,
                status=RunStatus.RUNNING,
                input_data=input_data,
                execution_context=execution_context
            )
            
            # Initialize task states
            await self._initialize_task_states(run_state, flow)
            
            # Compute ready tasks
            await self._compute_ready_tasks(run_state, flow)
            
            # Persist state
            await self._persist_run_state(run_state)
            
            # Schedule ready tasks
            await self._schedule_ready_tasks(run_state)
            
            # Track active run
            self.active_runs[run_id] = run_state
            ACTIVE_RUNS.set(len(self.active_runs))
            
            logger.info(
                "Flow run initialized successfully",
                run_id=run_id,
                ready_tasks=len(run_state.ready_tasks)
            )
            
        except Exception as e:
            logger.error("Failed to process flow run event", run_id=run_id, error=str(e))
            # Update run status to failed
            await self._update_run_status(run_id, RunStatus.FAILED, error=str(e))
    
    async def _initialize_task_states(self, run_state: RunState, flow: Flow):
        """Initialize task states for a flow run."""
        for task in flow.tasks:
            task_state = TaskState(
                task_id=task.id,
                handler=task.handler,
                inputs=task.inputs,
                max_retries=task.retries,
                timeout=task.timeout,
                condition=task.condition
            )
            run_state.tasks[task.id] = task_state
            run_state.task_attempts[task.id] = 0
    
    async def _compute_ready_tasks(self, run_state: RunState, flow: Flow):
        """Compute which tasks are ready to execute."""
        ready_tasks = set()
        
        for task in flow.tasks:
            task_state = run_state.tasks[task.id]
            
            # Check if task is already completed or failed
            if task.id in run_state.completed_tasks or task.id in run_state.failed_tasks:
                continue
            
            # Check task condition
            if task.condition:
                if not self._evaluate_condition(task.condition, run_state):
                    continue
            
            # For DAG flows, check dependencies
            if flow.type == "DAG":
                # Simple dependency check - in a real implementation,
                # you'd have a proper dependency graph
                if self._are_dependencies_satisfied(task, run_state):
                    ready_tasks.add(task.id)
            else:
                # For state machine flows, all tasks without conditions are ready
                ready_tasks.add(task.id)
        
        run_state.ready_tasks = ready_tasks
        
        # Update task statuses
        for task_id in ready_tasks:
            run_state.tasks[task_id].status = TaskStatus.READY
    
    def _evaluate_condition(self, condition: str, run_state: RunState) -> bool:
        """Evaluate a task condition."""
        try:
            # Simple condition evaluation - in production, use a proper expression evaluator
            context = {
                'input': run_state.input_data,
                'output': run_state.output_data,
                'completed_tasks': run_state.completed_tasks,
                'failed_tasks': run_state.failed_tasks
            }
            
            # For now, just check if condition is truthy
            return bool(condition.strip())
        except Exception as e:
            logger.warning("Failed to evaluate condition", condition=condition, error=str(e))
            return False
    
    def _are_dependencies_satisfied(self, task: Task, run_state: RunState) -> bool:
        """Check if task dependencies are satisfied."""
        # Simple implementation - in production, implement proper dependency graph
        # For now, assume all tasks can run in parallel
        return True
    
    async def _persist_run_state(self, run_state: RunState):
        """Persist run state to Redis and PostgreSQL."""
        # Persist to Redis
        redis_key = f"run:{run_state.run_id}:state"
        self.redis_client.setex(
            redis_key,
            config.redis_key_ttl,
            json.dumps(run_state.to_dict(), default=str)
        )
        
        # Persist to PostgreSQL
        await self._persist_run_to_postgres(run_state)
    
    async def _persist_run_to_postgres(self, run_state: RunState):
        """Persist run state to PostgreSQL."""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            # Upsert flow run history
            upsert_query = """
            INSERT INTO flow_run_history 
            (run_id, flow_id, tenant_id, user_id, correlation_id, status, 
             input_data, output_data, execution_context, error_message, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) 
            DO UPDATE SET 
                status = EXCLUDED.status,
                output_data = EXCLUDED.output_data,
                execution_context = EXCLUDED.execution_context,
                error_message = EXCLUDED.error_message,
                updated_at = EXCLUDED.updated_at
            """
            
            cursor.execute(upsert_query, (
                run_state.run_id,
                run_state.flow_id,
                run_state.tenant_id,
                run_state.user_id,
                run_state.correlation_id,
                run_state.status.value,
                json.dumps(run_state.input_data),
                json.dumps(run_state.output_data),
                json.dumps(run_state.execution_context),
                None,  # error_message
                run_state.updated_at
            ))
            
            # Upsert task execution history
            for task_state in run_state.tasks.values():
                task_upsert_query = """
                INSERT INTO task_execution_history 
                (run_id, task_id, handler, status, attempts, input_data, 
                 output_data, error_message, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, task_id) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    attempts = EXCLUDED.attempts,
                    output_data = EXCLUDED.output_data,
                    error_message = EXCLUDED.error_message,
                    updated_at = EXCLUDED.updated_at
                """
                
                cursor.execute(task_upsert_query, (
                    run_state.run_id,
                    task_state.task_id,
                    task_state.handler,
                    task_state.status.value,
                    task_state.attempts,
                    json.dumps(task_state.inputs),
                    json.dumps(task_state.output),
                    task_state.error,
                    task_state.updated_at
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to persist run to PostgreSQL", run_id=run_state.run_id, error=str(e))
            raise
    
    async def _schedule_ready_tasks(self, run_state: RunState):
        """Schedule ready tasks for execution."""
        for task_id in run_state.ready_tasks:
            task_state = run_state.tasks[task_id]
            
            # Create task message
            task_message = {
                "run_id": run_state.run_id,
                "task_id": task_id,
                "handler": task_state.handler,
                "inputs": task_state.inputs,
                "attempt": run_state.task_attempts[task_id],
                "max_retries": task_state.max_retries,
                "timeout": task_state.timeout,
                "correlation_id": run_state.correlation_id,
                "tenant_id": run_state.tenant_id,
                "user_id": run_state.user_id,
                "execution_context": run_state.execution_context,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Publish to task queue
            self.task_queue_producer.send(
                'task_queue',
                value=task_message,
                key=task_id
            )
            
            # Update task status
            task_state.status = TaskStatus.RUNNING
            task_state.updated_at = datetime.now(timezone.utc)
            
            TASKS_SCHEDULED.inc()
            ACTIVE_TASKS.inc()
            
            logger.info(
                "Task scheduled for execution",
                run_id=run_state.run_id,
                task_id=task_id,
                handler=task_state.handler,
                attempt=run_state.task_attempts[task_id]
            )
    
    async def _process_task_done_event(self, event: Dict[str, Any]):
        """Process a task completion event."""
        run_id = event.get('run_id')
        task_id = event.get('task_id')
        output = event.get('output', {})
        execution_time_ms = event.get('execution_time_ms', 0)
        
        logger.info(
            "Processing task done event",
            run_id=run_id,
            task_id=task_id,
            execution_time_ms=execution_time_ms
        )
        
        if run_id not in self.active_runs:
            logger.warning("Received task done event for unknown run", run_id=run_id)
            return
        
        run_state = self.active_runs[run_id]
        
        if task_id not in run_state.tasks:
            logger.warning("Received task done event for unknown task", run_id=run_id, task_id=task_id)
            return
        
        task_state = run_state.tasks[task_id]
        
        # Update task state
        task_state.status = TaskStatus.COMPLETED
        task_state.output = output
        task_state.updated_at = datetime.now(timezone.utc)
        
        # Update run state
        run_state.completed_tasks.add(task_id)
        run_state.ready_tasks.discard(task_id)
        run_state.output_data[task_id] = output
        
        # Update metrics
        TASK_EXECUTION_TIME.labels(handler=task_state.handler).observe(execution_time_ms / 1000.0)
        ACTIVE_TASKS.dec()
        
        # Check if run is complete
        await self._check_run_completion(run_state)
        
        # Persist updated state
        await self._persist_run_state(run_state)
        
        logger.info(
            "Task completed successfully",
            run_id=run_id,
            task_id=task_id,
            handler=task_state.handler
        )
    
    async def _process_task_failed_event(self, event: Dict[str, Any]):
        """Process a task failure event."""
        run_id = event.get('run_id')
        task_id = event.get('task_id')
        error = event.get('error', 'Unknown error')
        execution_time_ms = event.get('execution_time_ms', 0)
        
        logger.info(
            "Processing task failed event",
            run_id=run_id,
            task_id=task_id,
            error=error,
            execution_time_ms=execution_time_ms
        )
        
        if run_id not in self.active_runs:
            logger.warning("Received task failed event for unknown run", run_id=run_id)
            return
        
        run_state = self.active_runs[run_id]
        
        if task_id not in run_state.tasks:
            logger.warning("Received task failed event for unknown task", run_id=run_id, task_id=task_id)
            return
        
        task_state = run_state.tasks[task_id]
        current_attempt = run_state.task_attempts[task_id]
        
        # Update task state
        task_state.error = error
        task_state.updated_at = datetime.now(timezone.utc)
        
        # Check if we should retry
        if current_attempt < task_state.max_retries:
            # Schedule retry with exponential backoff
            await self._schedule_task_retry(run_state, task_state, current_attempt + 1)
        else:
            # Move to dead letter queue
            await self._move_task_to_dead_letter(run_state, task_state)
        
        # Update metrics
        TASK_EXECUTION_TIME.labels(handler=task_state.handler).observe(execution_time_ms / 1000.0)
        ACTIVE_TASKS.dec()
        
        # Persist updated state
        await self._persist_run_state(run_state)
        
        logger.info(
            "Task failed",
            run_id=run_id,
            task_id=task_id,
            handler=task_state.handler,
            attempt=current_attempt,
            max_retries=task_state.max_retries
        )
    
    async def _schedule_task_retry(self, run_state: RunState, task_state: TaskState, attempt: int):
        """Schedule a task retry with exponential backoff."""
        # Calculate backoff delay
        delay_seconds = self.retry_backoff_base ** attempt
        
        logger.info(
            "Scheduling task retry",
            run_id=run_state.run_id,
            task_id=task_state.task_id,
            attempt=attempt,
            delay_seconds=delay_seconds
        )
        
        # Update attempt count
        run_state.task_attempts[task_state.task_id] = attempt
        
        # Schedule retry
        asyncio.create_task(self._execute_task_retry(run_state, task_state, delay_seconds))
        
        # Update metrics
        RETRY_ATTEMPTS.labels(task_id=task_state.task_id, handler=task_state.handler).inc()
    
    async def _execute_task_retry(self, run_state: RunState, task_state: TaskState, delay_seconds: int):
        """Execute a task retry after delay."""
        await asyncio.sleep(delay_seconds)
        
        # Create retry task message
        task_message = {
            "run_id": run_state.run_id,
            "task_id": task_state.task_id,
            "handler": task_state.handler,
            "inputs": task_state.inputs,
            "attempt": run_state.task_attempts[task_state.task_id],
            "max_retries": task_state.max_retries,
            "timeout": task_state.timeout,
            "correlation_id": run_state.correlation_id,
            "tenant_id": run_state.tenant_id,
            "user_id": run_state.user_id,
            "execution_context": run_state.execution_context,
            "is_retry": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Publish to task queue
        self.task_queue_producer.send(
            'task_queue',
            value=task_message,
            key=task_state.task_id
        )
        
        # Update task status
        task_state.status = TaskStatus.RETRYING
        task_state.updated_at = datetime.now(timezone.utc)
        
        TASKS_SCHEDULED.inc()
        ACTIVE_TASKS.inc()
        
        logger.info(
            "Task retry scheduled",
            run_id=run_state.run_id,
            task_id=task_state.task_id,
            attempt=run_state.task_attempts[task_state.task_id]
        )
    
    async def _move_task_to_dead_letter(self, run_state: RunState, task_state: TaskState):
        """Move a failed task to the dead letter queue."""
        dead_letter_message = {
            "run_id": run_state.run_id,
            "task_id": task_state.task_id,
            "handler": task_state.handler,
            "inputs": task_state.inputs,
            "attempts": run_state.task_attempts[task_state.task_id],
            "max_retries": task_state.max_retries,
            "error": task_state.error,
            "correlation_id": run_state.correlation_id,
            "tenant_id": run_state.tenant_id,
            "user_id": run_state.user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "moved_to_dlq_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Publish to dead letter queue
        self.dead_letter_producer.send(
            config.dead_letter_queue_topic,
            value=dead_letter_message,
            key=task_state.task_id
        )
        
        # Update task state
        task_state.status = TaskStatus.DEAD_LETTER
        task_state.updated_at = datetime.now(timezone.utc)
        
        # Update run state
        run_state.failed_tasks.add(task_state.task_id)
        run_state.ready_tasks.discard(task_state.task_id)
        
        # Update metrics
        DEAD_LETTER_QUEUE_SIZE.inc()
        
        logger.warning(
            "Task moved to dead letter queue",
            run_id=run_state.run_id,
            task_id=task_state.task_id,
            handler=task_state.handler,
            attempts=run_state.task_attempts[task_state.task_id]
        )
    
    async def _check_run_completion(self, run_state: RunState):
        """Check if a flow run is complete."""
        total_tasks = len(run_state.tasks)
        completed_tasks = len(run_state.completed_tasks)
        failed_tasks = len(run_state.failed_tasks)
        
        if completed_tasks + failed_tasks == total_tasks:
            if failed_tasks == 0:
                run_state.status = RunStatus.COMPLETED
                logger.info("Flow run completed successfully", run_id=run_state.run_id)
            else:
                run_state.status = RunStatus.FAILED
                logger.warning("Flow run failed", run_id=run_state.run_id, failed_tasks=failed_tasks)
            
            # Update completion time
            run_state.updated_at = datetime.now(timezone.utc)
            
            # Remove from active runs
            del self.active_runs[run_state.run_id]
            ACTIVE_RUNS.set(len(self.active_runs))
            
            # Update metrics
            RUN_EXECUTION_TIME.observe(
                (run_state.updated_at - run_state.created_at).total_seconds()
            )
    
    async def _update_run_status(self, run_id: str, status: RunStatus, error: Optional[str] = None):
        """Update run status in all storage systems."""
        try:
            # Update Redis
            redis_key = f"run:{run_id}:state"
            state_data = self.redis_client.get(redis_key)
            
            if state_data:
                run_state = RunState.from_dict(json.loads(state_data))
                run_state.status = status
                run_state.updated_at = datetime.now(timezone.utc)
                
                if error:
                    run_state.execution_context['error'] = error
                
                self.redis_client.setex(
                    redis_key,
                    config.redis_key_ttl,
                    json.dumps(run_state.to_dict(), default=str)
                )
            
            # Update PostgreSQL
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            update_query = """
            UPDATE flow_run_history 
            SET status = %s, error_message = %s, updated_at = %s
            WHERE run_id = %s
            """
            
            cursor.execute(update_query, (
                status.value,
                error,
                datetime.now(timezone.utc),
                run_id
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error("Failed to update run status", run_id=run_id, error=str(e))


async def main():
    """Main function to run the orchestrator service."""
    orchestrator = OrchestratorService(
        kafka_bootstrap_servers=config.kafka_bootstrap_servers,
        redis_url=config.redis_url,
        database_url=config.database_url,
        flow_registry_url=config.flow_registry_url,
        metrics_port=config.metrics_port
    )
    
    try:
        await orchestrator.start()
        
        # Keep the service running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
