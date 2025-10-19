"""
OpenTelemetry initialization and configuration for Enterprise AI Agent Framework.

This module provides OpenTelemetry setup for distributed tracing across all services
including ingress, orchestrator, and executor components.
"""

import os
import logging
from typing import Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagators.ot_trace import OTTracePropagator
from opentelemetry.propagators.xray import AWSXRayPropagator
from opentelemetry.trace import Status, StatusCode
import structlog

logger = structlog.get_logger()


class OpenTelemetryConfig:
    """Configuration for OpenTelemetry tracing."""
    
    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version
        self.endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:14268/api/traces")
        self.enabled = os.getenv("OTEL_ENABLED", "true").lower() == "true"
        self.sampling_ratio = float(os.getenv("OTEL_SAMPLING_RATIO", "1.0"))
        self.exporter_type = os.getenv("OTEL_EXPORTER_TYPE", "jaeger")  # jaeger, otlp, console
        
        # Resource attributes
        self.resource_attributes = {
            "service.name": service_name,
            "service.version": service_version,
            "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "agent-framework"),
            "deployment.environment": os.getenv("OTEL_DEPLOYMENT_ENVIRONMENT", "production"),
            "host.name": os.getenv("HOSTNAME", "unknown"),
            "container.name": os.getenv("CONTAINER_NAME", "unknown"),
        }
        
        # Add custom attributes
        custom_attrs = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "")
        if custom_attrs:
            for attr in custom_attrs.split(","):
                if "=" in attr:
                    key, value = attr.split("=", 1)
                    self.resource_attributes[key.strip()] = value.strip()


def setup_opentelemetry(config: OpenTelemetryConfig) -> Optional[trace.Tracer]:
    """
    Initialize OpenTelemetry tracing for the service.
    
    Args:
        config: OpenTelemetry configuration
        
    Returns:
        Tracer instance if enabled, None otherwise
    """
    if not config.enabled:
        logger.info("OpenTelemetry tracing disabled")
        return None
    
    try:
        # Create resource
        resource = Resource.create(config.resource_attributes)
        
        # Create tracer provider
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=trace.sampling.TraceIdRatioBased(config.sampling_ratio)
        )
        
        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Create and configure exporter
        if config.exporter_type == "jaeger":
            exporter = JaegerExporter(
                agent_host_name=os.getenv("JAEGER_AGENT_HOST", "jaeger"),
                agent_port=int(os.getenv("JAEGER_AGENT_PORT", "6831")),
            )
        elif config.exporter_type == "otlp":
            exporter = OTLPSpanExporter(
                endpoint=config.endpoint,
                insecure=True,
            )
        else:  # console
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
        
        # Create span processor
        span_processor = BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            export_timeout_millis=30000,
            schedule_delay_millis=5000,
        )
        
        # Add span processor to tracer provider
        tracer_provider.add_span_processor(span_processor)
        
        # Set up propagators
        propagator = CompositeHTTPPropagator([
            B3MultiFormat(),
            JaegerPropagator(),
            OTTracePropagator(),
            AWSXRayPropagator(),
        ])
        
        # Configure instrumentation
        _setup_instrumentation()
        
        # Get tracer
        tracer = trace.get_tracer(config.service_name, config.service_version)
        
        logger.info(
            "OpenTelemetry tracing initialized",
            service_name=config.service_name,
            exporter_type=config.exporter_type,
            sampling_ratio=config.sampling_ratio
        )
        
        return tracer
        
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry", error=str(e))
        return None


def _setup_instrumentation():
    """Set up OpenTelemetry instrumentation for common libraries."""
    try:
        # HTTP libraries
        RequestsInstrumentor().instrument()
        URLLib3Instrumentor().instrument()
        
        # Database libraries
        Psycopg2Instrumentor().instrument()
        RedisInstrumentor().instrument()
        
        # Message queue
        KafkaInstrumentor().instrument()
        
        # Web framework
        FastAPIInstrumentor().instrument()
        
        # Async support
        AsyncioInstrumentor().instrument()
        
        logger.info("OpenTelemetry instrumentation configured")
        
    except Exception as e:
        logger.warning("Failed to configure some OpenTelemetry instrumentation", error=str(e))


def create_span(tracer: trace.Tracer, name: str, attributes: Optional[Dict[str, Any]] = None) -> trace.Span:
    """
    Create a new span with the given name and attributes.
    
    Args:
        tracer: OpenTelemetry tracer
        name: Span name
        attributes: Optional span attributes
        
    Returns:
        Span instance
    """
    span = tracer.start_span(name)
    
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    
    return span


def add_span_event(span: trace.Span, name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Add an event to the current span.
    
    Args:
        span: Current span
        name: Event name
        attributes: Optional event attributes
    """
    if attributes:
        span.add_event(name, attributes)
    else:
        span.add_event(name)


def set_span_status(span: trace.Span, status_code: StatusCode, description: Optional[str] = None):
    """
    Set the status of the current span.
    
    Args:
        span: Current span
        status_code: Status code (OK, ERROR, UNSET)
        description: Optional status description
    """
    span.set_status(Status(status_code, description))


def add_span_error(span: trace.Span, exception: Exception):
    """
    Add error information to the current span.
    
    Args:
        span: Current span
        exception: Exception to record
    """
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


# Context managers for automatic span management
class TraceContext:
    """Context manager for automatic span management."""
    
    def __init__(self, tracer: trace.Tracer, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.tracer = tracer
        self.name = name
        self.attributes = attributes
        self.span = None
    
    def __enter__(self):
        self.span = create_span(self.tracer, self.name, self.attributes)
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            add_span_error(self.span, exc_val)
        self.span.end()


# Decorator for automatic tracing
def trace_function(tracer: trace.Tracer, span_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to automatically trace function execution.
    
    Args:
        tracer: OpenTelemetry tracer
        span_name: Optional span name (defaults to function name)
        attributes: Optional span attributes
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = span_name or f"{func.__module__}.{func.__name__}"
            
            with TraceContext(tracer, name, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    add_span_error(span, e)
                    raise
        
        return wrapper
    return decorator


# Utility functions for common tracing patterns
def trace_http_request(tracer: trace.Tracer, method: str, url: str, status_code: int, duration_ms: float):
    """
    Create a span for HTTP request tracing.
    
    Args:
        tracer: OpenTelemetry tracer
        method: HTTP method
        url: Request URL
        status_code: Response status code
        duration_ms: Request duration in milliseconds
    """
    with TraceContext(tracer, f"HTTP {method}") as span:
        span.set_attribute("http.method", method)
        span.set_attribute("http.url", url)
        span.set_attribute("http.status_code", status_code)
        span.set_attribute("http.duration_ms", duration_ms)
        
        if status_code >= 400:
            span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))


def trace_database_query(tracer: trace.Tracer, operation: str, table: str, duration_ms: float, row_count: Optional[int] = None):
    """
    Create a span for database query tracing.
    
    Args:
        tracer: OpenTelemetry tracer
        operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_ms: Query duration in milliseconds
        row_count: Optional number of affected rows
    """
    with TraceContext(tracer, f"DB {operation}") as span:
        span.set_attribute("db.operation", operation)
        span.set_attribute("db.table", table)
        span.set_attribute("db.duration_ms", duration_ms)
        
        if row_count is not None:
            span.set_attribute("db.row_count", row_count)


def trace_kafka_message(tracer: trace.Tracer, topic: str, partition: int, offset: int, operation: str = "consume"):
    """
    Create a span for Kafka message tracing.
    
    Args:
        tracer: OpenTelemetry tracer
        topic: Kafka topic
        partition: Partition number
        offset: Message offset
        operation: Operation type (consume, produce)
    """
    with TraceContext(tracer, f"Kafka {operation}") as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", topic)
        span.set_attribute("messaging.operation", operation)
        span.set_attribute("kafka.partition", partition)
        span.set_attribute("kafka.offset", offset)


def trace_task_execution(tracer: trace.Tracer, task_id: str, task_type: str, duration_ms: float, status: str):
    """
    Create a span for task execution tracing.
    
    Args:
        tracer: OpenTelemetry tracer
        task_id: Task identifier
        task_type: Type of task
        duration_ms: Execution duration in milliseconds
        status: Task status (success, failure, timeout)
    """
    with TraceContext(tracer, f"Task {task_type}") as span:
        span.set_attribute("task.id", task_id)
        span.set_attribute("task.type", task_type)
        span.set_attribute("task.duration_ms", duration_ms)
        span.set_attribute("task.status", status)
        
        if status == "failure":
            span.set_status(Status(StatusCode.ERROR, "Task execution failed"))


# Service-specific initialization functions
def init_ingress_tracing() -> Optional[trace.Tracer]:
    """Initialize tracing for ingress service."""
    config = OpenTelemetryConfig("agent-framework-ingress")
    return setup_opentelemetry(config)


def init_orchestrator_tracing() -> Optional[trace.Tracer]:
    """Initialize tracing for orchestrator service."""
    config = OpenTelemetryConfig("agent-framework-orchestrator")
    return setup_opentelemetry(config)


def init_executor_tracing() -> Optional[trace.Tracer]:
    """Initialize tracing for executor service."""
    config = OpenTelemetryConfig("agent-framework-executor")
    return setup_opentelemetry(config)


# Example usage snippets for each service
def get_ingress_tracing_snippet():
    """Get code snippet for ingress service tracing."""
    return '''
# Add to ingress/api.py
from observability.opentelemetry_init import init_ingress_tracing, trace_http_request, TraceContext

# Initialize tracing at startup
tracer = init_ingress_tracing()

# In your FastAPI route handlers:
@app.post("/flows/{flow_id}/runs")
async def create_flow_run(flow_id: str, request: Request):
    with TraceContext(tracer, f"create_flow_run_{flow_id}") as span:
        span.set_attribute("flow.id", flow_id)
        span.set_attribute("user.tenant", request.headers.get("X-Tenant-ID"))
        
        # Your existing code here
        result = await process_flow_run(flow_id)
        
        span.set_attribute("flow.run_id", result["run_id"])
        return result
'''


def get_orchestrator_tracing_snippet():
    """Get code snippet for orchestrator service tracing."""
    return '''
# Add to orchestrator/service.py
from observability.opentelemetry_init import init_orchestrator_tracing, trace_task_execution, trace_kafka_message

# Initialize tracing at startup
tracer = init_orchestrator_tracing()

# In your task processing:
async def process_task(task_data):
    with TraceContext(tracer, "process_task") as span:
        span.set_attribute("task.id", task_data["task_id"])
        span.set_attribute("task.type", task_data["type"])
        
        # Trace Kafka message consumption
        trace_kafka_message(tracer, task_data["topic"], task_data["partition"], task_data["offset"])
        
        # Your existing task processing code
        result = await execute_task(task_data)
        
        # Trace task execution
        trace_task_execution(tracer, task_data["task_id"], task_data["type"], result["duration_ms"], result["status"])
        
        return result
'''


def get_executor_tracing_snippet():
    """Get code snippet for executor service tracing."""
    return '''
# Add to executor/worker.py
from observability.opentelemetry_init import init_executor_tracing, trace_task_execution, trace_database_query

# Initialize tracing at startup
tracer = init_executor_tracing()

# In your worker processing:
async def execute_task(task_data):
    with TraceContext(tracer, f"execute_task_{task_data['type']}") as span:
        span.set_attribute("task.id", task_data["task_id"])
        span.set_attribute("connector.type", task_data["connector_type"])
        
        # Trace database operations
        trace_database_query(tracer, "SELECT", "tasks", 15.5, 1)
        
        # Your existing execution code
        result = await run_connector_action(task_data)
        
        # Trace task execution
        trace_task_execution(tracer, task_data["task_id"], task_data["type"], result["duration_ms"], result["status"])
        
        return result
'''


if __name__ == "__main__":
    # Example usage
    config = OpenTelemetryConfig("test-service")
    tracer = setup_opentelemetry(config)
    
    if tracer:
        with TraceContext(tracer, "example_operation") as span:
            span.set_attribute("example.attribute", "example_value")
            add_span_event(span, "example_event", {"key": "value"})
            print("Tracing example completed")
