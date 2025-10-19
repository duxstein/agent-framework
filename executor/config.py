"""
Configuration for the Executor Worker.

This module provides configuration management for the executor worker,
including environment variable handling and default values.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class ExecutorConfig(BaseSettings):
    """Configuration for the Executor Worker."""
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated)"
    )
    kafka_consumer_group: str = Field(
        default="executor-worker",
        description="Kafka consumer group ID"
    )
    kafka_auto_offset_reset: str = Field(
        default="latest",
        description="Kafka auto offset reset policy"
    )
    kafka_enable_auto_commit: bool = Field(
        default=True,
        description="Enable Kafka auto commit"
    )
    
    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    idempotency_ttl: int = Field(
        default=3600,
        description="Idempotency key TTL in seconds"
    )
    
    # PostgreSQL Configuration
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_framework",
        description="PostgreSQL connection URL"
    )
    
    # Connector Registry Configuration
    connector_registry_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_framework",
        description="Connector registry connection URL"
    )
    
    # Execution Configuration
    max_workers: int = Field(
        default=10,
        description="Maximum number of worker threads/processes"
    )
    task_timeout_default: int = Field(
        default=300,
        description="Default task timeout in seconds"
    )
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum number of retry attempts"
    )
    
    # Metrics Configuration
    metrics_port: int = Field(
        default=9091,
        description="Prometheus metrics server port"
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )
    
    # Performance Configuration
    max_concurrent_tasks: int = Field(
        default=100,
        description="Maximum number of concurrent tasks"
    )
    thread_pool_size: int = Field(
        default=20,
        description="Thread pool size for sync tasks"
    )
    process_pool_size: int = Field(
        default=4,
        description="Process pool size for CPU-intensive tasks"
    )
    
    # Dead Letter Queue Configuration
    dead_letter_queue_enabled: bool = Field(
        default=True,
        description="Enable dead letter queue"
    )
    dead_letter_queue_topic: str = Field(
        default="dead_letter_queue",
        description="Dead letter queue topic name"
    )
    
    # Health Check Configuration
    health_check_interval: int = Field(
        default=30,
        description="Health check interval in seconds"
    )
    health_check_timeout: int = Field(
        default=5,
        description="Health check timeout in seconds"
    )
    
    # Connector Configuration
    connector_cache_size: int = Field(
        default=100,
        description="Maximum number of connectors to cache"
    )
    connector_cache_ttl: int = Field(
        default=3600,
        description="Connector cache TTL in seconds"
    )
    
    class Config:
        env_prefix = "EXECUTOR_"
        case_sensitive = False


def get_config() -> ExecutorConfig:
    """Get executor configuration."""
    return ExecutorConfig()


# Global configuration instance
config = get_config()
