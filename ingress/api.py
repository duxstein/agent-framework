"""
FastAPI service for Enterprise AI Agent Framework Ingress API.

This module provides REST API endpoints for managing flow runs with JWT authentication,
tenant scoping, audit logging, and Kafka message publishing.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncio

import structlog
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from kafka import KafkaProducer
import httpx

from sdk.models import Flow, Task
from sdk.policy import PolicyResult, FlowPolicy, TenantIsolationPolicy, RetryLimitPolicy, TimeoutPolicy
from sdk.registry import FlowRegistry, RegistryError


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

# Security scheme
security = HTTPBearer()

# Import configuration
from .config import config


# Pydantic models for API requests/responses
class FlowRunRequest(BaseModel):
    """Request model for creating a flow run."""
    flow_id: str = Field(..., description="Flow identifier")
    flow_definition: Optional[Dict[str, Any]] = Field(None, description="Optional flow definition")
    input: Dict[str, Any] = Field(..., description="Input data for the flow")
    tenant_id: str = Field(..., description="Tenant identifier")
    request_id: Optional[str] = Field(None, description="Optional request identifier")


class WebhookRequest(BaseModel):
    """Request model for webhook-triggered flow runs."""
    webhook_id: str = Field(..., description="Webhook identifier")
    payload: Dict[str, Any] = Field(..., description="Webhook payload data")
    headers: Optional[Dict[str, str]] = Field(None, description="Webhook headers")
    source: Optional[str] = Field(None, description="Source system identifier")


class FlowRunResponse(BaseModel):
    """Response model for flow run creation."""
    run_id: str = Field(..., description="Unique run identifier")
    correlation_id: str = Field(..., description="Correlation identifier for tracking")


class FlowRunStatus(BaseModel):
    """Response model for flow run status."""
    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Current run status")
    created_at: datetime = Field(..., description="Run creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    tenant_id: str = Field(..., description="Tenant identifier")
    flow_id: str = Field(..., description="Flow identifier")
    input: Dict[str, Any] = Field(..., description="Input data")
    output: Optional[Dict[str, Any]] = Field(None, description="Output data")
    error: Optional[str] = Field(None, description="Error message if any")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# Dependency injection classes
class DatabaseClient:
    """PostgreSQL database client."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._connection = None
    
    async def get_connection(self):
        """Get database connection."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(
                self.database_url,
                cursor_factory=RealDictCursor
            )
        return self._connection
    
    async def execute_query(self, query: str, params: tuple = None):
        """Execute a query and return results."""
        conn = await self.get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:
                return cursor.fetchall()
            conn.commit()
            return cursor.rowcount
    
    async def close(self):
        """Close database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()


class RedisClient:
    """Redis client for caching."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client = None
    
    async def get_client(self):
        """Get Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client
    
    async def get(self, key: str):
        """Get value from Redis."""
        client = await self.get_client()
        return client.get(key)
    
    async def set(self, key: str, value: str, expire: int = None):
        """Set value in Redis."""
        client = await self.get_client()
        return client.set(key, value, ex=expire)
    
    async def delete(self, key: str):
        """Delete key from Redis."""
        client = await self.get_client()
        return client.delete(key)


class KafkaClient:
    """Kafka producer client."""
    
    def __init__(self, bootstrap_servers: List[str]):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
    
    async def get_producer(self):
        """Get Kafka producer."""
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
        return self._producer
    
    async def send_message(self, topic: str, message: Dict[str, Any], key: str = None):
        """Send message to Kafka topic."""
        producer = await self.get_producer()
        future = producer.send(topic, value=message, key=key)
        return await asyncio.wrap_future(future)
    
    async def close(self):
        """Close Kafka producer."""
        if self._producer:
            self._producer.close()


# Policy Engine
class PolicyEngine:
    """Policy engine for enforcing business rules and security constraints."""
    
    def __init__(self):
        """Initialize the policy engine with default policies."""
        self.policies = [
            TenantIsolationPolicy(),
            RetryLimitPolicy(max_retries=10),
            TimeoutPolicy(max_timeout=7200)  # 2 hours
        ]
    
    def evaluate_flow(self, flow: Flow, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate all policies against a flow.
        
        Args:
            flow: Flow to evaluate
            context: Additional context for policy evaluation
            
        Returns:
            Dictionary containing evaluation results
        """
        results = {
            'valid': True,
            'policies_evaluated': [],
            'violations': [],
            'modifications': {}
        }
        
        for policy in self.policies:
            if not policy.is_enabled():
                continue
                
            try:
                policy_result = policy.evaluate(flow, context or {})
                results['policies_evaluated'].append({
                    'policy': policy.name,
                    'result': policy_result['result'].value,
                    'message': policy_result['message'],
                    'metadata': policy_result.get('metadata', {})
                })
                
                if policy_result['result'] == PolicyResult.DENY:
                    results['valid'] = False
                    results['violations'].append({
                        'policy': policy.name,
                        'message': policy_result['message'],
                        'metadata': policy_result.get('metadata', {})
                    })
                elif policy_result['result'] == PolicyResult.MODIFY:
                    modifications = policy_result.get('modifications', {})
                    if modifications:
                        results['modifications'].update(modifications)
                        
            except Exception as e:
                logger.error("Policy evaluation failed", policy=policy.name, error=str(e))
                results['valid'] = False
                results['violations'].append({
                    'policy': policy.name,
                    'message': f"Policy evaluation failed: {str(e)}",
                    'metadata': {}
                })
        
        return results


# Global clients
db_client = DatabaseClient(config.DATABASE_URL)
redis_client = RedisClient(config.REDIS_URL)
kafka_client = KafkaClient(config.KAFKA_BOOTSTRAP_SERVERS)
flow_registry = FlowRegistry(connection_string=config.DATABASE_URL)
policy_engine = PolicyEngine()


# Authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT token and extract user information."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        
        # Extract user information
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id or tenant_id"
            )
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "payload": payload
        }
    except JWTError as e:
        logger.error("JWT verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# Tenant scope validation
async def validate_tenant_scope(
    request_tenant_id: str,
    user_info: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """Validate that the user has access to the requested tenant."""
    user_tenant_id = user_info["tenant_id"]
    
    if request_tenant_id != user_tenant_id:
        logger.warning(
            "Tenant scope violation",
            user_tenant_id=user_tenant_id,
            request_tenant_id=request_tenant_id,
            user_id=user_info["user_id"]
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: tenant scope violation"
        )
    
    return user_info


# Create FastAPI app
app = FastAPI(
    title="Enterprise AI Agent Framework Ingress API",
    description="REST API for managing AI agent flow runs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Enterprise AI Agent Framework Ingress API")
    
    # Initialize database schema if needed
    await init_database_schema()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Enterprise AI Agent Framework Ingress API")
    await db_client.close()
    await kafka_client.close()


async def init_database_schema():
    """Initialize database schema."""
    try:
        # Create flow_runs_audit table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS flow_runs_audit (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(255) UNIQUE NOT NULL,
            correlation_id VARCHAR(255) NOT NULL,
            flow_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            request_id VARCHAR(255),
            input_data JSONB NOT NULL,
            flow_definition JSONB,
            status VARCHAR(50) DEFAULT 'PENDING',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            output_data JSONB,
            error_message TEXT
        );
        
        CREATE TABLE IF NOT EXISTS webhook_configs (
            id SERIAL PRIMARY KEY,
            webhook_id VARCHAR(255) UNIQUE NOT NULL,
            flow_id VARCHAR(255) NOT NULL,
            tenant_id VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            webhook_config JSONB,
            enabled BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_run_id ON flow_runs_audit(run_id);
        CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_tenant_id ON flow_runs_audit(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_flow_id ON flow_runs_audit(flow_id);
        CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_status ON flow_runs_audit(status);
        CREATE INDEX IF NOT EXISTS idx_webhook_configs_webhook_id ON webhook_configs(webhook_id);
        CREATE INDEX IF NOT EXISTS idx_webhook_configs_tenant_id ON webhook_configs(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_webhook_configs_enabled ON webhook_configs(enabled);
        """
        
        await db_client.execute_query(create_table_query)
        logger.info("Database schema initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize database schema", error=str(e))
        raise


@app.post("/v1/runs", response_model=FlowRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_flow_run(
    request: FlowRunRequest,
    user_info: Dict[str, Any] = Depends(validate_tenant_scope)
):
    """
    Create a new flow run.
    
    This endpoint accepts a flow run request, validates it against the Flow model,
    enforces JWT authentication and tenant scope, generates run and correlation IDs,
    saves an audit entry to Postgres, and publishes a message to Kafka.
    """
    try:
        # Generate unique identifiers
        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        logger.info(
            "Creating flow run",
            run_id=run_id,
            correlation_id=correlation_id,
            flow_id=request.flow_id,
            tenant_id=request.tenant_id,
            user_id=user_info["user_id"]
        )
        
        # Load flow definition from registry or validate provided definition
        flow_definition = None
        if request.flow_definition:
            # Use provided flow definition
            flow_definition = request.flow_definition
        else:
            # Load from flow registry
            try:
                flow = flow_registry.get_flow(request.flow_id)
                if not flow:
                    logger.warning("Flow not found in registry", run_id=run_id, flow_id=request.flow_id)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Flow {request.flow_id} not found in registry"
                    )
                flow_definition = flow.to_dict()
            except RegistryError as e:
                logger.error("Failed to load flow from registry", run_id=run_id, error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to load flow from registry"
                )
        
        # Validate flow definition with SDK validation
        try:
            flow = Flow(**flow_definition)
            validation_result = flow.validate()
            if not validation_result["valid"]:
                logger.warning(
                    "Flow SDK validation failed",
                    run_id=run_id,
                    errors=validation_result["errors"]
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid flow definition: {', '.join(validation_result['errors'])}"
                )
        except Exception as e:
            logger.warning("Flow SDK validation error", run_id=run_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid flow definition: {str(e)}"
            )
        
        # Apply policy engine validation
        policy_context = {
            'user_id': user_info["user_id"],
            'tenant_id': request.tenant_id,
            'run_id': run_id,
            'request_id': request.request_id
        }
        
        policy_result = policy_engine.evaluate_flow(flow, policy_context)
        
        if not policy_result["valid"]:
            logger.warning(
                "Flow policy validation failed",
                run_id=run_id,
                violations=policy_result["violations"]
            )
            violation_messages = [v["message"] for v in policy_result["violations"]]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Flow violates policies: {'; '.join(violation_messages)}"
            )
        
        # Apply policy modifications if any
        if policy_result["modifications"]:
            logger.info(
                "Applying policy modifications",
                run_id=run_id,
                modifications=policy_result["modifications"]
            )
            # Apply modifications to flow (this would need to be implemented in the Flow class)
            # For now, we'll log the modifications
        
        logger.info(
            "Flow validation successful",
            run_id=run_id,
            policies_evaluated=len(policy_result["policies_evaluated"])
        )
        
        # Save audit entry to Postgres
        audit_query = """
        INSERT INTO flow_runs_audit 
        (run_id, correlation_id, flow_id, tenant_id, user_id, request_id, input_data, flow_definition, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        audit_params = (
            run_id,
            correlation_id,
            request.flow_id,
            request.tenant_id,
            user_info["user_id"],
            request.request_id,
            json.dumps(request.input),
            json.dumps(request.flow_definition) if request.flow_definition else None,
            "PENDING"
        )
        
        await db_client.execute_query(audit_query, audit_params)
        
        # Publish message to Kafka with orchestrator-compatible format
        kafka_message = {
            "event_type": "flow_run_requested",
            "run_id": run_id,
            "correlation_id": correlation_id,
            "flow_id": request.flow_id,
            "tenant_id": request.tenant_id,
            "user_id": user_info["user_id"],
            "request_id": request.request_id,
            "input": request.input,
            "flow_definition": flow_definition,
            "status": "PENDING",
            "priority": "normal",  # Could be configurable based on tenant/user
            "execution_context": {
                "user_id": user_info["user_id"],
                "tenant_id": request.tenant_id,
                "request_id": request.request_id,
                "source": "ingress_api",
                "policies_applied": policy_result["policies_evaluated"]
            },
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "api_version": "v1",
                "client_ip": "unknown",  # Would be extracted from request in production
                "user_agent": "unknown"  # Would be extracted from request in production
            }
        }
        
        await kafka_client.send_message(config.KAFKA_TOPIC_FLOW_RUNS, kafka_message, key=run_id)
        
        logger.info(
            "Flow run created successfully",
            run_id=run_id,
            correlation_id=correlation_id
        )
        
        return FlowRunResponse(
            run_id=run_id,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create flow run", error=str(e), run_id=run_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get("/v1/runs/{run_id}", response_model=FlowRunStatus)
async def get_flow_run_status(
    run_id: str,
    user_info: Dict[str, Any] = Depends(verify_token)
):
    """
    Get the status of a flow run.
    
    This endpoint retrieves the run state from Postgres/Redis.
    If the run is not found, it returns a 404 error.
    """
    try:
        logger.info("Retrieving flow run status", run_id=run_id, user_id=user_info["user_id"])
        
        # First try to get from Redis cache
        cache_key = f"flow_run:{run_id}"
        cached_data = await redis_client.get(cache_key)
        
        if cached_data:
            try:
                cached_run = json.loads(cached_data)
                # Validate tenant access
                if cached_run["tenant_id"] != user_info["tenant_id"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: tenant scope violation"
                    )
                
                logger.info("Flow run status retrieved from cache", run_id=run_id)
                return FlowRunStatus(**cached_run)
            except json.JSONDecodeError:
                # Cache data is corrupted, fall back to database
                pass
        
        # Get from database
        query = """
        SELECT run_id, status, created_at, updated_at, tenant_id, flow_id, 
               input_data, output_data, error_message
        FROM flow_runs_audit 
        WHERE run_id = %s
        """
        
        results = await db_client.execute_query(query, (run_id,))
        
        if not results:
            logger.warning("Flow run not found", run_id=run_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flow run not found"
            )
        
        run_data = results[0]
        
        # Validate tenant access
        if run_data["tenant_id"] != user_info["tenant_id"]:
            logger.warning(
                "Tenant scope violation for run status",
                run_id=run_id,
                user_tenant_id=user_info["tenant_id"],
                run_tenant_id=run_data["tenant_id"]
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: tenant scope violation"
            )
        
        # Prepare response
        response_data = {
            "run_id": run_data["run_id"],
            "status": run_data["status"],
            "created_at": run_data["created_at"],
            "updated_at": run_data["updated_at"],
            "tenant_id": run_data["tenant_id"],
            "flow_id": run_data["flow_id"],
            "input": run_data["input_data"],
            "output": run_data["output_data"],
            "error": run_data["error_message"]
        }
        
        # Cache the result for future requests
        await redis_client.set(
            cache_key,
            json.dumps(response_data, default=str),
            expire=config.REDIS_CACHE_TTL
        )
        
        logger.info("Flow run status retrieved from database", run_id=run_id)
        return FlowRunStatus(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve flow run status", error=str(e), run_id=run_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/v1/webhooks/{webhook_id}", response_model=FlowRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def webhook_trigger(
    webhook_id: str,
    request: WebhookRequest,
    http_request: Request
):
    """
    Webhook endpoint for external system integrations.
    
    This endpoint allows external systems to trigger flow runs via webhooks,
    providing a simple integration point for systems like n8n, Zapier, etc.
    """
    try:
        # Generate unique identifiers
        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        # Extract client information
        client_ip = http_request.client.host if http_request.client else "unknown"
        user_agent = http_request.headers.get("user-agent", "unknown")
        
        logger.info(
            "Webhook triggered",
            webhook_id=webhook_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source=request.source,
            client_ip=client_ip
        )
        
        # Load webhook configuration from database
        webhook_query = """
        SELECT flow_id, tenant_id, user_id, webhook_config
        FROM webhook_configs 
        WHERE webhook_id = %s AND enabled = true
        """
        
        webhook_results = await db_client.execute_query(webhook_query, (webhook_id,))
        
        if not webhook_results:
            logger.warning("Webhook not found or disabled", webhook_id=webhook_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook {webhook_id} not found or disabled"
            )
        
        webhook_config = webhook_results[0]
        flow_id = webhook_config["flow_id"]
        tenant_id = webhook_config["tenant_id"]
        user_id = webhook_config["user_id"]
        webhook_config_data = webhook_config["webhook_config"]
        
        # Transform webhook payload to flow input
        input_data = {
            "webhook_payload": request.payload,
            "webhook_headers": request.headers or {},
            "webhook_source": request.source,
            "webhook_id": webhook_id
        }
        
        # Apply webhook-specific transformations if configured
        if webhook_config_data and "transform" in webhook_config_data:
            # Apply transformation logic (simplified for now)
            transform_config = webhook_config_data["transform"]
            if "input_mapping" in transform_config:
                # Map webhook payload fields to flow input fields
                input_mapping = transform_config["input_mapping"]
                for flow_field, webhook_field in input_mapping.items():
                    if webhook_field in request.payload:
                        input_data[flow_field] = request.payload[webhook_field]
        
        # Load flow from registry
        try:
            flow = flow_registry.get_flow(flow_id)
            if not flow:
                logger.warning("Flow not found in registry", webhook_id=webhook_id, flow_id=flow_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Flow {flow_id} not found in registry"
                )
            flow_definition = flow.to_dict()
        except RegistryError as e:
            logger.error("Failed to load flow from registry", webhook_id=webhook_id, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to load flow from registry"
            )
        
        # Validate flow with policy engine
        policy_context = {
            'user_id': user_id,
            'tenant_id': tenant_id,
            'webhook_id': webhook_id,
            'source': request.source or 'webhook'
        }
        
        policy_result = policy_engine.evaluate_flow(flow, policy_context)
        
        if not policy_result["valid"]:
            logger.warning(
                "Webhook flow policy validation failed",
                webhook_id=webhook_id,
                violations=policy_result["violations"]
            )
            violation_messages = [v["message"] for v in policy_result["violations"]]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Flow violates policies: {'; '.join(violation_messages)}"
            )
        
        # Save audit entry
        audit_query = """
        INSERT INTO flow_runs_audit 
        (run_id, correlation_id, flow_id, tenant_id, user_id, request_id, input_data, flow_definition, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        audit_params = (
            run_id,
            correlation_id,
            flow_id,
            tenant_id,
            user_id,
            f"webhook:{webhook_id}",
            json.dumps(input_data),
            json.dumps(flow_definition),
            "PENDING"
        )
        
        await db_client.execute_query(audit_query, audit_params)
        
        # Publish message to Kafka
        kafka_message = {
            "event_type": "flow_run_requested",
            "run_id": run_id,
            "correlation_id": correlation_id,
            "flow_id": flow_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "request_id": f"webhook:{webhook_id}",
            "input": input_data,
            "flow_definition": flow_definition,
            "status": "PENDING",
            "priority": "normal",
            "execution_context": {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "webhook_id": webhook_id,
                "source": request.source or "webhook",
                "policies_applied": policy_result["policies_evaluated"]
            },
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "api_version": "v1",
                "client_ip": client_ip,
                "user_agent": user_agent,
                "webhook_source": request.source
            }
        }
        
        await kafka_client.send_message(config.KAFKA_TOPIC_FLOW_RUNS, kafka_message, key=run_id)
        
        logger.info(
            "Webhook flow run created successfully",
            webhook_id=webhook_id,
            run_id=run_id,
            correlation_id=correlation_id
        )
        
        return FlowRunResponse(
            run_id=run_id,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process webhook", webhook_id=webhook_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Enterprise AI Agent Framework Ingress API",
        "version": "1.0.0",
        "description": "REST API for managing AI agent flow runs",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "create_run": "/v1/runs",
            "get_run_status": "/v1/runs/{run_id}",
            "webhook": "/v1/webhooks/{webhook_id}"
        },
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        await db_client.execute_query("SELECT 1")
        
        # Check Redis connection
        await redis_client.get("health_check")
        
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=config.API_HOST, 
        port=config.API_PORT,
        workers=config.API_WORKERS
    )
