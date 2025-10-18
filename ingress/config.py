"""
Configuration module for the Enterprise AI Agent Framework Ingress API.

This module handles environment variable configuration and provides
default values for development and testing.
"""

import os
from typing import List


class Config:
    """Configuration class for the ingress API."""
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://user:password@localhost:5432/agent_framework"
    )
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "300"))  # 5 minutes
    
    # Kafka Configuration
    KAFKA_BOOTSTRAP_SERVERS: List[str] = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", 
        "localhost:9092"
    ).split(",")
    KAFKA_TOPIC_FLOW_RUNS: str = os.getenv("KAFKA_TOPIC_FLOW_RUNS", "flow_runs")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_WORKERS: int = int(os.getenv("API_WORKERS", "1"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", 
        "*"
    ).split(",")
    
    # Security Configuration
    ALLOWED_HOSTS: List[str] = os.getenv(
        "ALLOWED_HOSTS", 
        "*"
    ).split(",")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration values."""
        required_vars = [
            "JWT_SECRET_KEY",
            "DATABASE_URL",
            "REDIS_URL"
        ]
        
        for var in required_vars:
            if not getattr(cls, var):
                raise ValueError(f"Required configuration variable {var} is not set")
        
        return True
    
    @classmethod
    def get_database_config(cls) -> dict:
        """Get database configuration as dictionary."""
        return {
            "url": cls.DATABASE_URL,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600"))
        }
    
    @classmethod
    def get_redis_config(cls) -> dict:
        """Get Redis configuration as dictionary."""
        return {
            "url": cls.REDIS_URL,
            "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            "socket_connect_timeout": int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
            "retry_on_timeout": os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true"
        }
    
    @classmethod
    def get_kafka_config(cls) -> dict:
        """Get Kafka configuration as dictionary."""
        return {
            "bootstrap_servers": cls.KAFKA_BOOTSTRAP_SERVERS,
            "topic_flow_runs": cls.KAFKA_TOPIC_FLOW_RUNS,
            "acks": os.getenv("KAFKA_ACKS", "all"),
            "retries": int(os.getenv("KAFKA_RETRIES", "3")),
            "batch_size": int(os.getenv("KAFKA_BATCH_SIZE", "16384")),
            "linger_ms": int(os.getenv("KAFKA_LINGER_MS", "10")),
            "buffer_memory": int(os.getenv("KAFKA_BUFFER_MEMORY", "33554432"))
        }


# Global configuration instance
config = Config()

