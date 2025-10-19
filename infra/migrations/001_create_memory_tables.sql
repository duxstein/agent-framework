-- Migration: 001_create_memory_tables.sql
-- Description: Create tables for memory adapter layer including flow run history, task outputs, and audit log
-- Created: 2024-01-01
-- Author: Enterprise AI Agent Framework Team

-- Create flow_run_history table for storing flow execution history
CREATE TABLE IF NOT EXISTS flow_run_history (
    id SERIAL PRIMARY KEY,
    flow_id VARCHAR(255) NOT NULL,
    run_id VARCHAR(255) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for flow_run_history
CREATE INDEX IF NOT EXISTS idx_flow_run_history_flow_id ON flow_run_history(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_run_history_run_id ON flow_run_history(run_id);
CREATE INDEX IF NOT EXISTS idx_flow_run_history_created_at ON flow_run_history(created_at);
CREATE INDEX IF NOT EXISTS idx_flow_run_history_flow_run ON flow_run_history(flow_id, run_id);

-- Create task_outputs table for storing task execution outputs
CREATE TABLE IF NOT EXISTS task_outputs (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL UNIQUE,
    output JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for task_outputs
CREATE INDEX IF NOT EXISTS idx_task_outputs_task_id ON task_outputs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_outputs_created_at ON task_outputs(created_at);

-- Create audit_log table for storing audit trail entries
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for audit_log
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_type ON audit_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_id ON audit_log(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);

-- Create memory_context table for storing context data (alternative to Redis)
CREATE TABLE IF NOT EXISTS memory_context (
    id SERIAL PRIMARY KEY,
    context_id VARCHAR(255) NOT NULL UNIQUE,
    context_data JSONB NOT NULL,
    ttl_seconds INTEGER,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for memory_context
CREATE INDEX IF NOT EXISTS idx_memory_context_context_id ON memory_context(context_id);
CREATE INDEX IF NOT EXISTS idx_memory_context_expires_at ON memory_context(expires_at);
CREATE INDEX IF NOT EXISTS idx_memory_context_created_at ON memory_context(created_at);

-- Create memory_events table for storing context events
CREATE TABLE IF NOT EXISTS memory_events (
    id SERIAL PRIMARY KEY,
    context_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for memory_events
CREATE INDEX IF NOT EXISTS idx_memory_events_context_id ON memory_events(context_id);
CREATE INDEX IF NOT EXISTS idx_memory_events_event_id ON memory_events(event_id);
CREATE INDEX IF NOT EXISTS idx_memory_events_created_at ON memory_events(created_at);

-- Create vector_embeddings table for storing vector embeddings (placeholder for vector DB)
CREATE TABLE IF NOT EXISTS vector_embeddings (
    id SERIAL PRIMARY KEY,
    embedding_id VARCHAR(255) NOT NULL UNIQUE,
    embedding_vector REAL[] NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for vector_embeddings
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_embedding_id ON vector_embeddings(embedding_id);
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_created_at ON vector_embeddings(created_at);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at timestamp
CREATE TRIGGER update_flow_run_history_updated_at 
    BEFORE UPDATE ON flow_run_history 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_outputs_updated_at 
    BEFORE UPDATE ON task_outputs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_context_updated_at 
    BEFORE UPDATE ON memory_context 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vector_embeddings_updated_at 
    BEFORE UPDATE ON vector_embeddings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function to clean up expired context data
CREATE OR REPLACE FUNCTION cleanup_expired_context()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM memory_context 
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to get context with events
CREATE OR REPLACE FUNCTION get_context_with_events(p_context_id VARCHAR(255))
RETURNS TABLE (
    context_data JSONB,
    events JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mc.context_data,
        COALESCE(
            (SELECT jsonb_agg(
                jsonb_build_object(
                    'event', me.event_data,
                    'timestamp', me.created_at,
                    'event_id', me.event_id
                )
            ) FROM memory_events me WHERE me.context_id = p_context_id),
            '[]'::jsonb
        ) as events
    FROM memory_context mc
    WHERE mc.context_id = p_context_id
    AND (mc.expires_at IS NULL OR mc.expires_at > NOW());
END;
$$ LANGUAGE plpgsql;

-- Create function to search vector embeddings by similarity (cosine similarity)
CREATE OR REPLACE FUNCTION search_similar_embeddings(
    query_vector REAL[],
    similarity_threshold REAL DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    embedding_id VARCHAR(255),
    similarity REAL,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ve.embedding_id,
        (1 - (ve.embedding_vector <-> query_vector)) as similarity,
        ve.metadata
    FROM vector_embeddings ve
    WHERE (1 - (ve.embedding_vector <-> query_vector)) >= similarity_threshold
    ORDER BY ve.embedding_vector <-> query_vector
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Add comments to tables
COMMENT ON TABLE flow_run_history IS 'Stores execution history for flows';
COMMENT ON TABLE task_outputs IS 'Stores output data from task executions';
COMMENT ON TABLE audit_log IS 'Stores audit trail entries for all operations';
COMMENT ON TABLE memory_context IS 'Stores context data for agent memory';
COMMENT ON TABLE memory_events IS 'Stores events associated with context';
COMMENT ON TABLE vector_embeddings IS 'Stores vector embeddings for similarity search';

-- Add comments to columns
COMMENT ON COLUMN flow_run_history.flow_id IS 'Unique identifier for the flow';
COMMENT ON COLUMN flow_run_history.run_id IS 'Unique identifier for the flow run';
COMMENT ON COLUMN flow_run_history.data IS 'JSON data containing flow run information';

COMMENT ON COLUMN task_outputs.task_id IS 'Unique identifier for the task';
COMMENT ON COLUMN task_outputs.output IS 'JSON data containing task output';
COMMENT ON COLUMN task_outputs.metadata IS 'Optional metadata for the task output';

COMMENT ON COLUMN audit_log.entity_type IS 'Type of entity being audited (flow, task, etc.)';
COMMENT ON COLUMN audit_log.entity_id IS 'Unique identifier of the entity';
COMMENT ON COLUMN audit_log.action IS 'Action performed on the entity';
COMMENT ON COLUMN audit_log.data IS 'JSON data containing audit information';

COMMENT ON COLUMN memory_context.context_id IS 'Unique identifier for the context';
COMMENT ON COLUMN memory_context.context_data IS 'JSON data containing context information';
COMMENT ON COLUMN memory_context.ttl_seconds IS 'Time to live in seconds';
COMMENT ON COLUMN memory_context.expires_at IS 'Expiration timestamp';

COMMENT ON COLUMN memory_events.context_id IS 'Context identifier this event belongs to';
COMMENT ON COLUMN memory_events.event_id IS 'Unique identifier for the event';
COMMENT ON COLUMN memory_events.event_data IS 'JSON data containing event information';

COMMENT ON COLUMN vector_embeddings.embedding_id IS 'Unique identifier for the embedding';
COMMENT ON COLUMN vector_embeddings.embedding_vector IS 'Vector embedding data';
COMMENT ON COLUMN vector_embeddings.metadata IS 'Optional metadata for the embedding';
