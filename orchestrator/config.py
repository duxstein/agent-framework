"""
Configuration for the Orchestrator Service.

This module provides configuration management for the orchestrator service,
including environment variable handling and default values.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class OrchestratorConfig(BaseSettings):
    """Configuration for the Orchestrator Service."""
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated)"
    )
    kafka_consumer_group: str = Field(
        default="orchestrator-service",
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
    redis_key_ttl: int = Field(
        default=3600,
        description="Redis key TTL in seconds"
    )
    
    # PostgreSQL Configuration
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_framework",
        description="PostgreSQL connection URL"
    )
    
    # Flow Registry Configuration
    flow_registry_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_framework",
        description="Flow registry connection URL"
    )
    
    # Retry Configuration
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum number of retry attempts"
    )
    retry_backoff_base: int = Field(
        default=2,
        description="Exponential backoff base multiplier"
    )
    task_timeout_default: int = Field(
        default=300,
        description="Default task timeout in seconds"
    )
    
    # Metrics Configuration
    metrics_port: int = Field(
        default=9090,
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
    max_concurrent_runs: int = Field(
        default=1000,
        description="Maximum number of concurrent runs"
    )
    max_concurrent_tasks: int = Field(
        default=10000,
        description="Maximum number of concurrent tasks"
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
    
    class Config:
        env_prefix = "ORCHESTRATOR_"
        case_sensitive = False


def get_config() -> OrchestratorConfig:
    """Get orchestrator configuration."""
    return OrchestratorConfig()


# Global configuration instance
config = get_config()
