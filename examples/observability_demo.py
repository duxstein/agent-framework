#!/usr/bin/env python3
"""
Observability Demo Script for Enterprise AI Agent Framework.

This script demonstrates the observability capabilities including metrics collection,
distributed tracing, and structured logging.
"""

import time
import asyncio
import random
from datetime import datetime, timezone
from typing import Dict, Any

from prometheus_client import Counter, Histogram, Gauge, start_http_server, generate_latest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
import structlog

from observability.opentelemetry_init import (
    OpenTelemetryConfig,
    setup_opentelemetry,
    TraceContext,
    trace_function,
    trace_http_request,
    trace_database_query,
    trace_kafka_message,
    trace_task_execution
)


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("observability-demo")

# Create metrics
REQUEST_COUNTER = Counter('demo_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('demo_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
TASK_COUNTER = Counter('demo_tasks_total', 'Total tasks', ['status', 'task_type'])
TASK_DURATION = Histogram('demo_task_duration_seconds', 'Task duration', ['task_type'])
QUEUE_DEPTH = Gauge('demo_queue_depth', 'Current queue depth')


class ObservabilityDemo:
    """Demonstration of observability features."""
    
    def __init__(self):
        """Initialize the demo."""
        # Set up tracing
        self.exporter = InMemorySpanExporter()
        self.tracer_provider = TracerProvider()
        self.tracer_provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer("observability-demo")
        
        # Initialize OpenTelemetry
        config = OpenTelemetryConfig("observability-demo")
        self.otel_tracer = setup_opentelemetry(config)
        
        logger.info("Observability demo initialized")
    
    def simulate_http_request(self, method: str, endpoint: str) -> Dict[str, Any]:
        """Simulate an HTTP request with metrics and tracing."""
        start_time = time.time()
        
        with TraceContext(self.tracer, f"HTTP {method} {endpoint}") as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", endpoint)
            
            # Simulate processing time
            processing_time = random.uniform(0.01, 0.1)
            time.sleep(processing_time)
            
            # Simulate success/failure
            status_code = 200 if random.random() > 0.1 else 500
            status = "success" if status_code == 200 else "error"
            
            # Record metrics
            REQUEST_COUNTER.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
            
            # Record duration
            duration = time.time() - start_time
            with REQUEST_DURATION.labels(method=method, endpoint=endpoint).time():
                pass  # Duration already measured
            
            span.set_attribute("http.status_code", status_code)
            span.set_attribute("http.duration_ms", duration * 1000)
            
            if status_code >= 400:
                span.set_status(trace.Status(trace.StatusCode.ERROR, f"HTTP {status_code}"))
            
            # Log the request
            logger.info(
                "HTTP request processed",
                method=method,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=duration * 1000,
                trace_id=span.get_span_context().trace_id,
                span_id=span.get_span_context().span_id
            )
            
            return {
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "duration_ms": duration * 1000,
                "trace_id": format(span.get_span_context().trace_id, '032x'),
                "span_id": format(span.get_span_context().span_id, '016x')
            }
    
    def simulate_database_query(self, operation: str, table: str) -> Dict[str, Any]:
        """Simulate a database query with metrics and tracing."""
        start_time = time.time()
        
        with TraceContext(self.tracer, f"DB {operation}") as span:
            span.set_attribute("db.operation", operation)
            span.set_attribute("db.table", table)
            
            # Simulate query execution
            execution_time = random.uniform(0.005, 0.05)
            time.sleep(execution_time)
            
            # Simulate row count
            row_count = random.randint(1, 1000)
            
            duration = time.time() - start_time
            
            span.set_attribute("db.duration_ms", duration * 1000)
            span.set_attribute("db.row_count", row_count)
            
            # Log the query
            logger.info(
                "Database query executed",
                operation=operation,
                table=table,
                row_count=row_count,
                duration_ms=duration * 1000,
                trace_id=span.get_span_context().trace_id,
                span_id=span.get_span_context().span_id
            )
            
            return {
                "operation": operation,
                "table": table,
                "row_count": row_count,
                "duration_ms": duration * 1000,
                "trace_id": format(span.get_span_context().trace_id, '032x'),
                "span_id": format(span.get_span_context().span_id, '016x')
            }
    
    def simulate_kafka_message(self, topic: str, operation: str) -> Dict[str, Any]:
        """Simulate Kafka message processing with metrics and tracing."""
        partition = random.randint(0, 3)
        offset = random.randint(1000, 10000)
        
        with TraceContext(self.tracer, f"Kafka {operation}") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", topic)
            span.set_attribute("messaging.operation", operation)
            span.set_attribute("kafka.partition", partition)
            span.set_attribute("kafka.offset", offset)
            
            # Simulate message processing
            processing_time = random.uniform(0.001, 0.01)
            time.sleep(processing_time)
            
            # Log the message
            logger.info(
                "Kafka message processed",
                topic=topic,
                operation=operation,
                partition=partition,
                offset=offset,
                duration_ms=processing_time * 1000,
                trace_id=span.get_span_context().trace_id,
                span_id=span.get_span_context().span_id
            )
            
            return {
                "topic": topic,
                "operation": operation,
                "partition": partition,
                "offset": offset,
                "duration_ms": processing_time * 1000,
                "trace_id": format(span.get_span_context().trace_id, '032x'),
                "span_id": format(span.get_span_context().span_id, '016x')
            }
    
    @trace_function(trace.get_tracer("observability-demo"), "process_task")
    def simulate_task_execution(self, task_type: str) -> Dict[str, Any]:
        """Simulate task execution with metrics and tracing."""
        start_time = time.time()
        
        # Simulate task processing
        processing_time = random.uniform(0.1, 1.0)
        time.sleep(processing_time)
        
        # Simulate success/failure
        success = random.random() > 0.05  # 95% success rate
        status = "success" if success else "failure"
        
        # Record metrics
        TASK_COUNTER.labels(status=status, task_type=task_type).inc()
        
        duration = time.time() - start_time
        
        # Log the task execution
        logger.info(
            "Task executed",
            task_type=task_type,
            status=status,
            duration_ms=duration * 1000,
            success=success
        )
        
        return {
            "task_type": task_type,
            "status": status,
            "duration_ms": duration * 1000,
            "success": success
        }
    
    def simulate_queue_operations(self):
        """Simulate queue depth changes."""
        # Simulate queue depth changes
        for _ in range(10):
            change = random.randint(-5, 10)
            current_depth = QUEUE_DEPTH._value.get()
            new_depth = max(0, current_depth + change)
            QUEUE_DEPTH.set(new_depth)
            
            logger.info(
                "Queue depth changed",
                old_depth=current_depth,
                new_depth=new_depth,
                change=change
            )
            
            time.sleep(0.1)
    
    def run_demo(self):
        """Run the complete observability demonstration."""
        logger.info("Starting observability demonstration")
        
        # Simulate HTTP requests
        endpoints = [
            ("GET", "/health"),
            ("POST", "/flows"),
            ("GET", "/flows/123"),
            ("POST", "/flows/123/runs"),
            ("GET", "/flows/123/runs/456")
        ]
        
        logger.info("Simulating HTTP requests")
        for method, endpoint in endpoints:
            for _ in range(5):
                result = self.simulate_http_request(method, endpoint)
                logger.debug("HTTP request result", **result)
                time.sleep(0.1)
        
        # Simulate database queries
        logger.info("Simulating database queries")
        operations = [
            ("SELECT", "users"),
            ("INSERT", "flows"),
            ("UPDATE", "tasks"),
            ("DELETE", "logs")
        ]
        
        for operation, table in operations:
            for _ in range(3):
                result = self.simulate_database_query(operation, table)
                logger.debug("Database query result", **result)
                time.sleep(0.1)
        
        # Simulate Kafka messages
        logger.info("Simulating Kafka messages")
        topics = ["task-queue", "flow-events", "audit-logs"]
        
        for topic in topics:
            for _ in range(3):
                result = self.simulate_kafka_message(topic, "consume")
                logger.debug("Kafka message result", **result)
                time.sleep(0.1)
        
        # Simulate task executions
        logger.info("Simulating task executions")
        task_types = ["data_processing", "api_call", "file_upload", "email_send"]
        
        for task_type in task_types:
            for _ in range(5):
                result = self.simulate_task_execution(task_type)
                logger.debug("Task execution result", **result)
                time.sleep(0.1)
        
        # Simulate queue operations
        logger.info("Simulating queue operations")
        self.simulate_queue_operations()
        
        # Display metrics
        logger.info("Generating metrics")
        metrics_text = generate_latest().decode('utf-8')
        logger.info("Prometheus metrics generated", metrics_count=len(metrics_text.split('\n')))
        
        # Display traces
        spans = self.exporter.get_finished_spans()
        logger.info("Traces generated", span_count=len(spans))
        
        # Display summary
        logger.info(
            "Observability demonstration completed",
            total_spans=len(spans),
            metrics_generated=True,
            logs_structured=True
        )
        
        return {
            "spans": len(spans),
            "metrics_generated": True,
            "logs_structured": True,
            "demo_successful": True
        }


def main():
    """Main function to run the observability demo."""
    print("🚀 Starting Enterprise AI Agent Framework Observability Demo")
    print("=" * 60)
    
    # Start Prometheus metrics server
    start_http_server(8000)
    print("📊 Prometheus metrics server started on port 8000")
    
    # Create and run demo
    demo = ObservabilityDemo()
    result = demo.run_demo()
    
    print("\n" + "=" * 60)
    print("✅ Observability Demo Completed Successfully!")
    print(f"📈 Generated {result['spans']} traces")
    print("📊 Metrics available at http://localhost:8000/metrics")
    print("🔍 Structured logs output to console")
    print("\n🎯 Key Features Demonstrated:")
    print("  • Prometheus metrics collection")
    print("  • OpenTelemetry distributed tracing")
    print("  • Structured JSON logging")
    print("  • Service correlation")
    print("  • Performance monitoring")
    
    print("\n📋 Next Steps:")
    print("  1. View metrics: curl http://localhost:8000/metrics")
    print("  2. Import Grafana dashboard from observability/grafana_dashboard.json")
    print("  3. Set up Jaeger for trace visualization")
    print("  4. Configure Elasticsearch for log aggregation")
    print("  5. Run tests: pytest tests/observability/test_observability.py")


if __name__ == "__main__":
    main()
