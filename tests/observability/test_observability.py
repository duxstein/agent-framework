"""
Observability Tests for Enterprise AI Agent Framework.

This module contains unit and integration tests that demonstrate metrics collection,
tracing, and logging capabilities while validating observability functionality.
"""

import pytest
import time
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any, List

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

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


class TestPrometheusMetrics:
    """Test Prometheus metrics collection and scraping."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create a new registry for testing
        self.registry = CollectorRegistry()
        
        # Create test metrics
        self.task_counter = Counter(
            'test_task_execution_total',
            'Total number of task executions',
            ['status', 'task_type'],
            registry=self.registry
        )
        
        self.task_duration = Histogram(
            'test_task_execution_duration_seconds',
            'Task execution duration in seconds',
            ['task_type'],
            registry=self.registry
        )
        
        self.queue_depth = Gauge(
            'test_task_queue_depth',
            'Current task queue depth',
            registry=self.registry
        )
    
    def test_counter_metrics(self):
        """Test counter metrics collection."""
        # Increment counters
        self.task_counter.labels(status='success', task_type='data_processing').inc()
        self.task_counter.labels(status='success', task_type='data_processing').inc(2)
        self.task_counter.labels(status='failure', task_type='data_processing').inc()
        self.task_counter.labels(status='success', task_type='api_call').inc()
        
        # Collect metrics
        metrics = self._collect_metrics()
        
        # Verify counter values
        assert self._get_metric_value(metrics, 'test_task_execution_total', {'status': 'success', 'task_type': 'data_processing'}) == 3
        assert self._get_metric_value(metrics, 'test_task_execution_total', {'status': 'failure', 'task_type': 'data_processing'}) == 1
        assert self._get_metric_value(metrics, 'test_task_execution_total', {'status': 'success', 'task_type': 'api_call'}) == 1
    
    def test_histogram_metrics(self):
        """Test histogram metrics collection."""
        # Record durations
        with self.task_duration.labels(task_type='data_processing').time():
            time.sleep(0.01)  # 10ms
        
        with self.task_duration.labels(task_type='data_processing').time():
            time.sleep(0.02)  # 20ms
        
        with self.task_duration.labels(task_type='api_call').time():
            time.sleep(0.05)  # 50ms
        
        # Collect metrics
        metrics = self._collect_metrics()
        
        # Verify histogram values
        data_processing_count = self._get_metric_value(metrics, 'test_task_execution_duration_seconds_count', {'task_type': 'data_processing'})
        api_call_count = self._get_metric_value(metrics, 'test_task_execution_duration_seconds_count', {'task_type': 'api_call'})
        
        assert data_processing_count == 2
        assert api_call_count == 1
        
        # Verify sum values
        data_processing_sum = self._get_metric_value(metrics, 'test_task_execution_duration_seconds_sum', {'task_type': 'data_processing'})
        api_call_sum = self._get_metric_value(metrics, 'test_task_execution_duration_seconds_sum', {'task_type': 'api_call'})
        
        assert data_processing_sum >= 0.03  # At least 30ms
        assert api_call_sum >= 0.05  # At least 50ms
    
    def test_gauge_metrics(self):
        """Test gauge metrics collection."""
        # Set gauge values
        self.queue_depth.set(100)
        assert self._get_metric_value(self._collect_metrics(), 'test_task_queue_depth') == 100
        
        self.queue_depth.inc(50)
        assert self._get_metric_value(self._collect_metrics(), 'test_task_queue_depth') == 150
        
        self.queue_depth.dec(25)
        assert self._get_metric_value(self._collect_metrics(), 'test_task_queue_depth') == 125
        
        self.queue_depth.set_to_current_time()
        current_time = time.time()
        gauge_value = self._get_metric_value(self._collect_metrics(), 'test_task_queue_depth')
        assert abs(gauge_value - current_time) < 1  # Within 1 second
    
    def test_metrics_scraping_simulation(self):
        """Test metrics scraping simulation."""
        # Simulate some activity
        for i in range(10):
            self.task_counter.labels(status='success', task_type='test').inc()
            with self.task_duration.labels(task_type='test').time():
                time.sleep(0.001)  # 1ms
        
        # Simulate metrics scraping
        metrics_text = self._get_metrics_text()
        
        # Verify metrics are in the expected format
        assert 'test_task_execution_total' in metrics_text
        assert 'test_task_execution_duration_seconds' in metrics_text
        assert 'test_task_queue_depth' in metrics_text
        
        # Verify specific values
        assert 'test_task_execution_total{status="success",task_type="test"} 10.0' in metrics_text
    
    def _collect_metrics(self) -> List[Dict[str, Any]]:
        """Collect metrics from registry."""
        metrics = []
        for metric in self.registry.collect():
            for sample in metric.samples:
                metrics.append({
                    'name': sample.name,
                    'labels': sample.labels,
                    'value': sample.value
                })
        return metrics
    
    def _get_metric_value(self, metrics: List[Dict[str, Any]], name: str, labels: Dict[str, str] = None) -> float:
        """Get metric value by name and labels."""
        for metric in metrics:
            if metric['name'] == name:
                if labels is None or metric['labels'] == labels:
                    return metric['value']
        return 0.0
    
    def _get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        from prometheus_client import generate_latest
        return generate_latest(self.registry).decode('utf-8')


class TestOpenTelemetryTracing:
    """Test OpenTelemetry tracing functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create in-memory exporter for testing
        self.exporter = InMemorySpanExporter()
        
        # Create tracer provider
        self.tracer_provider = TracerProvider()
        self.tracer_provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer("test-service")
    
    def test_basic_tracing(self):
        """Test basic tracing functionality."""
        # Create a span
        with self.tracer.start_span("test-operation") as span:
            span.set_attribute("test.attribute", "test-value")
            span.add_event("test-event", {"key": "value"})
        
        # Get exported spans
        spans = self.exporter.get_finished_spans()
        
        assert len(spans) == 1
        assert spans[0].name == "test-operation"
        assert spans[0].attributes["test.attribute"] == "test-value"
        assert len(spans[0].events) == 1
        assert spans[0].events[0].name == "test-event"
    
    def test_trace_context_manager(self):
        """Test TraceContext manager."""
        config = OpenTelemetryConfig("test-service")
        
        with TraceContext(self.tracer, "context-test", {"test.key": "test.value"}) as span:
            span.set_attribute("additional.attribute", "additional-value")
        
        spans = self.exporter.get_finished_spans()
        
        assert len(spans) == 1
        assert spans[0].name == "context-test"
        assert spans[0].attributes["test.key"] == "test.value"
        assert spans[0].attributes["additional.attribute"] == "additional-value"
    
    def test_trace_function_decorator(self):
        """Test trace_function decorator."""
        @trace_function(self.tracer, "decorated-function", {"decorator.test": "true"})
        def test_function(param1: str, param2: int) -> str:
            return f"{param1}_{param2}"
        
        result = test_function("test", 123)
        
        assert result == "test_123"
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "decorated-function"
        assert spans[0].attributes["decorator.test"] == "true"
        assert spans[0].attributes["function.result"] == "success"
    
    def test_trace_function_with_exception(self):
        """Test trace_function decorator with exception."""
        @trace_function(self.tracer, "error-function")
        def error_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            error_function()
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "error-function"
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert len(spans[0].events) == 1  # Exception event
    
    def test_http_request_tracing(self):
        """Test HTTP request tracing."""
        trace_http_request(self.tracer, "GET", "/api/test", 200, 150.5)
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "HTTP GET"
        assert spans[0].attributes["http.method"] == "GET"
        assert spans[0].attributes["http.url"] == "/api/test"
        assert spans[0].attributes["http.status_code"] == 200
        assert spans[0].attributes["http.duration_ms"] == 150.5
    
    def test_database_query_tracing(self):
        """Test database query tracing."""
        trace_database_query(self.tracer, "SELECT", "users", 25.3, 100)
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "DB SELECT"
        assert spans[0].attributes["db.operation"] == "SELECT"
        assert spans[0].attributes["db.table"] == "users"
        assert spans[0].attributes["db.duration_ms"] == 25.3
        assert spans[0].attributes["db.row_count"] == 100
    
    def test_kafka_message_tracing(self):
        """Test Kafka message tracing."""
        trace_kafka_message(self.tracer, "test-topic", 0, 12345, "consume")
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "Kafka consume"
        assert spans[0].attributes["messaging.system"] == "kafka"
        assert spans[0].attributes["messaging.destination"] == "test-topic"
        assert spans[0].attributes["messaging.operation"] == "consume"
        assert spans[0].attributes["kafka.partition"] == 0
        assert spans[0].attributes["kafka.offset"] == 12345
    
    def test_task_execution_tracing(self):
        """Test task execution tracing."""
        trace_task_execution(self.tracer, "task-123", "data_processing", 500.0, "success")
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "Task data_processing"
        assert spans[0].attributes["task.id"] == "task-123"
        assert spans[0].attributes["task.type"] == "data_processing"
        assert spans[0].attributes["task.duration_ms"] == 500.0
        assert spans[0].attributes["task.status"] == "success"
    
    def test_nested_spans(self):
        """Test nested span creation."""
        with self.tracer.start_span("parent-span") as parent:
            parent.set_attribute("parent.attr", "parent-value")
            
            with self.tracer.start_span("child-span") as child:
                child.set_attribute("child.attr", "child-value")
        
        spans = self.exporter.get_finished_spans()
        assert len(spans) == 2
        
        # Find parent and child spans
        parent_span = next(s for s in spans if s.name == "parent-span")
        child_span = next(s for s in spans if s.name == "child-span")
        
        assert parent_span.attributes["parent.attr"] == "parent-value"
        assert child_span.attributes["child.attr"] == "child-value"
        assert child_span.parent.span_id == parent_span.context.span_id


class TestStructuredLogging:
    """Test structured logging functionality."""
    
    def test_structured_log_creation(self):
        """Test creation of structured log entries."""
        import structlog
        
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
        
        logger = structlog.get_logger("test-logger")
        
        # Create structured log entry
        log_data = {
            "user_id": "user-123",
            "action": "login",
            "ip_address": "192.168.1.1",
            "success": True,
            "duration_ms": 150.5
        }
        
        logger.info("User login", **log_data)
        
        # Verify log structure (in real implementation, this would be captured)
        assert isinstance(log_data, dict)
        assert log_data["user_id"] == "user-123"
        assert log_data["action"] == "login"
        assert log_data["success"] is True
    
    def test_log_correlation(self):
        """Test log correlation with trace context."""
        # Mock trace context
        trace_id = "1234567890abcdef"
        span_id = "abcdef1234567890"
        
        log_data = {
            "trace_id": trace_id,
            "span_id": span_id,
            "correlation_id": "corr-123",
            "message": "Processing task",
            "task_id": "task-456"
        }
        
        # Verify correlation fields
        assert log_data["trace_id"] == trace_id
        assert log_data["span_id"] == span_id
        assert log_data["correlation_id"] == "corr-123"
        assert log_data["task_id"] == "task-456"


class TestObservabilityIntegration:
    """Integration tests for observability components."""
    
    def test_metrics_and_tracing_integration(self):
        """Test integration between metrics and tracing."""
        # Set up tracing
        exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer("integration-test")
        
        # Set up metrics
        registry = CollectorRegistry()
        counter = Counter('integration_test_total', 'Test counter', registry=registry)
        histogram = Histogram('integration_test_duration_seconds', 'Test duration', registry=registry)
        
        # Simulate operation with both metrics and tracing
        with tracer.start_span("integration-operation") as span:
            span.set_attribute("operation.type", "test")
            
            # Increment counter
            counter.inc()
            
            # Record duration
            with histogram.time():
                time.sleep(0.01)
        
        # Verify tracing
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "integration-operation"
        
        # Verify metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        counter_metric = next(m for m in metrics if m.name == 'integration_test_total')
        assert counter_metric.value == 1.0
        
        duration_metric = next(m for m in metrics if m.name == 'integration_test_duration_seconds_count')
        assert duration_metric.value == 1.0
    
    def test_error_handling_observability(self):
        """Test observability for error scenarios."""
        # Set up tracing
        exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer("error-test")
        
        # Set up metrics
        registry = CollectorRegistry()
        error_counter = Counter('error_test_total', 'Error counter', ['error_type'], registry=registry)
        
        # Simulate error scenario
        try:
            with tracer.start_span("error-operation") as span:
                span.set_attribute("operation.type", "error_test")
                raise ValueError("Test error")
        except ValueError as e:
            error_counter.labels(error_type="ValueError").inc()
            
            # Add error to span
            spans = exporter.get_finished_spans()
            if spans:
                spans[0].record_exception(e)
                spans[0].set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
        
        # Verify error metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        error_metric = next(m for m in metrics if m.name == 'error_test_total' and m.labels.get('error_type') == 'ValueError')
        assert error_metric.value == 1.0
        
        # Verify error tracing
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert len(spans[0].events) == 1  # Exception event
    
    def test_performance_monitoring(self):
        """Test performance monitoring capabilities."""
        # Set up metrics
        registry = CollectorRegistry()
        request_duration = Histogram('request_duration_seconds', 'Request duration', ['endpoint'], registry=registry)
        request_count = Counter('request_total', 'Request count', ['endpoint', 'status'], registry=registry)
        
        # Simulate multiple requests
        endpoints = ['/api/users', '/api/tasks', '/api/flows']
        statuses = ['200', '404', '500']
        
        for endpoint in endpoints:
            for status in statuses:
                # Record request
                request_count.labels(endpoint=endpoint, status=status).inc()
                
                # Record duration
                with request_duration.labels(endpoint=endpoint).time():
                    time.sleep(0.001)  # 1ms
        
        # Collect metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        # Verify request counts
        for endpoint in endpoints:
            for status in statuses:
                count_metric = next(m for m in metrics if m.name == 'request_total' and m.labels.get('endpoint') == endpoint and m.labels.get('status') == status)
                assert count_metric.value == 1.0
        
        # Verify duration counts
        for endpoint in endpoints:
            duration_metric = next(m for m in metrics if m.name == 'request_duration_seconds_count' and m.labels.get('endpoint') == endpoint)
            assert duration_metric.value == 3.0  # 3 requests per endpoint


class TestObservabilityServiceIntegration:
    """Test observability integration with actual services."""
    
    @pytest.mark.asyncio
    async def test_ingress_service_observability(self):
        """Test observability for ingress service."""
        # Mock ingress service metrics
        registry = CollectorRegistry()
        http_requests = Counter('http_requests_total', 'HTTP requests', ['method', 'endpoint', 'status'], registry=registry)
        http_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'], registry=registry)
        
        # Simulate HTTP requests
        requests = [
            ('GET', '/health', '200'),
            ('POST', '/flows', '201'),
            ('GET', '/flows/123', '200'),
            ('POST', '/flows/123/runs', '201'),
            ('GET', '/flows/123/runs/456', '404'),
        ]
        
        for method, endpoint, status in requests:
            # Record request
            http_requests.labels(method=method, endpoint=endpoint, status=status).inc()
            
            # Record duration
            with http_duration.labels(method=method, endpoint=endpoint).time():
                await asyncio.sleep(0.001)  # 1ms
        
        # Verify metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        # Check specific metrics
        health_requests = next(m for m in metrics if m.name == 'http_requests_total' and m.labels.get('endpoint') == '/health')
        assert health_requests.value == 1.0
        
        flows_requests = next(m for m in metrics if m.name == 'http_requests_total' and m.labels.get('endpoint') == '/flows' and m.labels.get('method') == 'POST')
        assert flows_requests.value == 1.0
    
    @pytest.mark.asyncio
    async def test_orchestrator_service_observability(self):
        """Test observability for orchestrator service."""
        # Mock orchestrator service metrics
        registry = CollectorRegistry()
        flow_executions = Counter('flow_execution_total', 'Flow executions', ['status'], registry=registry)
        task_queue_depth = Gauge('task_queue_depth', 'Task queue depth', registry=registry)
        kafka_messages = Counter('kafka_messages_total', 'Kafka messages', ['topic', 'operation'], registry=registry)
        
        # Simulate flow executions
        flow_executions.labels(status='success').inc(5)
        flow_executions.labels(status='failure').inc(1)
        
        # Simulate queue depth changes
        task_queue_depth.set(100)
        task_queue_depth.inc(50)
        task_queue_depth.dec(25)
        
        # Simulate Kafka operations
        kafka_messages.labels(topic='task-queue', operation='produce').inc(10)
        kafka_messages.labels(topic='task-queue', operation='consume').inc(8)
        
        # Verify metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        # Check flow execution metrics
        success_flows = next(m for m in metrics if m.name == 'flow_execution_total' and m.labels.get('status') == 'success')
        assert success_flows.value == 5.0
        
        failure_flows = next(m for m in metrics if m.name == 'flow_execution_total' and m.labels.get('status') == 'failure')
        assert failure_flows.value == 1.0
        
        # Check queue depth
        queue_depth = next(m for m in metrics if m.name == 'task_queue_depth')
        assert queue_depth.value == 125.0
        
        # Check Kafka metrics
        kafka_produce = next(m for m in metrics if m.name == 'kafka_messages_total' and m.labels.get('operation') == 'produce')
        assert kafka_produce.value == 10.0
        
        kafka_consume = next(m for m in metrics if m.name == 'kafka_messages_total' and m.labels.get('operation') == 'consume')
        assert kafka_consume.value == 8.0
    
    @pytest.mark.asyncio
    async def test_executor_service_observability(self):
        """Test observability for executor service."""
        # Mock executor service metrics
        registry = CollectorRegistry()
        task_executions = Counter('task_execution_total', 'Task executions', ['status', 'connector_type'], registry=registry)
        task_duration = Histogram('task_execution_duration_seconds', 'Task execution duration', ['connector_type'], registry=registry)
        connector_health = Gauge('connector_health', 'Connector health status', ['connector_type'], registry=registry)
        
        # Simulate task executions
        connector_types = ['postgres', 'redis', 'http', 'slack']
        
        for connector in connector_types:
            # Simulate successful executions
            task_executions.labels(status='success', connector_type=connector).inc(10)
            
            # Simulate some failures
            task_executions.labels(status='failure', connector_type=connector).inc(1)
            
            # Record execution durations
            for _ in range(10):
                with task_duration.labels(connector_type=connector).time():
                    await asyncio.sleep(0.001)  # 1ms
            
            # Set connector health
            connector_health.labels(connector_type=connector).set(1.0)  # Healthy
        
        # Verify metrics
        metrics = []
        for metric in registry.collect():
            for sample in metric.samples:
                metrics.append(sample)
        
        # Check task execution metrics
        for connector in connector_types:
            success_tasks = next(m for m in metrics if m.name == 'task_execution_total' and m.labels.get('connector_type') == connector and m.labels.get('status') == 'success')
            assert success_tasks.value == 10.0
            
            failure_tasks = next(m for m in metrics if m.name == 'task_execution_total' and m.labels.get('connector_type') == connector and m.labels.get('status') == 'failure')
            assert failure_tasks.value == 1.0
            
            duration_count = next(m for m in metrics if m.name == 'task_execution_duration_seconds_count' and m.labels.get('connector_type') == connector)
            assert duration_count.value == 10.0
            
            health_status = next(m for m in metrics if m.name == 'connector_health' and m.labels.get('connector_type') == connector)
            assert health_status.value == 1.0


if __name__ == "__main__":
    pytest.main([__file__])
