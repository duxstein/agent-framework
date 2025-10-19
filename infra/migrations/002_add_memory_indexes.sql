-- Migration: 002_add_memory_indexes.sql
-- Description: Add additional indexes for performance optimization
-- Created: 2024-01-01
-- Author: Enterprise AI Agent Framework Team

-- Add composite indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_flow_run_history_flow_created ON flow_run_history(flow_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_outputs_created_desc ON task_outputs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_action ON audit_log(entity_type, entity_id, action);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity_created ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_context_expires ON memory_context(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_events_context_created ON memory_events(context_id, created_at DESC);

-- Add partial indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_flow_run_history_recent ON flow_run_history(created_at DESC) WHERE created_at > NOW() - INTERVAL '30 days';
CREATE INDEX IF NOT EXISTS idx_audit_log_recent ON audit_log(created_at DESC) WHERE created_at > NOW() - INTERVAL '90 days';
CREATE INDEX IF NOT EXISTS idx_memory_context_active ON memory_context(context_id) WHERE expires_at IS NULL OR expires_at > NOW();

-- Add GIN indexes for JSONB columns to improve JSON query performance
CREATE INDEX IF NOT EXISTS idx_flow_run_history_data_gin ON flow_run_history USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_task_outputs_output_gin ON task_outputs USING GIN (output);
CREATE INDEX IF NOT EXISTS idx_task_outputs_metadata_gin ON task_outputs USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_audit_log_data_gin ON audit_log USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_memory_context_data_gin ON memory_context USING GIN (context_data);
CREATE INDEX IF NOT EXISTS idx_memory_events_data_gin ON memory_events USING GIN (event_data);
CREATE INDEX IF NOT EXISTS idx_vector_embeddings_metadata_gin ON vector_embeddings USING GIN (metadata);

-- Add BRIN indexes for large tables with time-series data
CREATE INDEX IF NOT EXISTS idx_flow_run_history_created_brin ON flow_run_history USING BRIN (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_brin ON audit_log USING BRIN (created_at);
CREATE INDEX IF NOT EXISTS idx_memory_events_created_brin ON memory_events USING BRIN (created_at);

-- Create materialized view for frequently accessed flow run statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS flow_run_stats AS
SELECT 
    flow_id,
    COUNT(*) as total_runs,
    COUNT(DISTINCT run_id) as unique_runs,
    MIN(created_at) as first_run,
    MAX(created_at) as last_run,
    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_duration_seconds
FROM flow_run_history
GROUP BY flow_id;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_flow_run_stats_flow_id ON flow_run_stats(flow_id);

-- Create function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_flow_run_stats()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW flow_run_stats;
END;
$$ LANGUAGE plpgsql;

-- Create function to get context statistics
CREATE OR REPLACE FUNCTION get_context_stats()
RETURNS TABLE (
    total_contexts BIGINT,
    active_contexts BIGINT,
    expired_contexts BIGINT,
    total_events BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM memory_context) as total_contexts,
        (SELECT COUNT(*) FROM memory_context WHERE expires_at IS NULL OR expires_at > NOW()) as active_contexts,
        (SELECT COUNT(*) FROM memory_context WHERE expires_at IS NOT NULL AND expires_at <= NOW()) as expired_contexts,
        (SELECT COUNT(*) FROM memory_events) as total_events;
END;
$$ LANGUAGE plpgsql;

-- Create function to cleanup old data
CREATE OR REPLACE FUNCTION cleanup_old_data(
    flow_history_days INTEGER DEFAULT 90,
    audit_log_days INTEGER DEFAULT 365,
    expired_context_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    table_name TEXT,
    deleted_count BIGINT
) AS $$
DECLARE
    flow_count BIGINT;
    audit_count BIGINT;
    context_count BIGINT;
BEGIN
    -- Clean up old flow run history
    DELETE FROM flow_run_history 
    WHERE created_at < NOW() - INTERVAL '1 day' * flow_history_days;
    GET DIAGNOSTICS flow_count = ROW_COUNT;
    
    -- Clean up old audit log entries
    DELETE FROM audit_log 
    WHERE created_at < NOW() - INTERVAL '1 day' * audit_log_days;
    GET DIAGNOSTICS audit_count = ROW_COUNT;
    
    -- Clean up expired contexts that are older than specified days
    DELETE FROM memory_context 
    WHERE expires_at IS NOT NULL 
    AND expires_at < NOW() - INTERVAL '1 day' * expired_context_days;
    GET DIAGNOSTICS context_count = ROW_COUNT;
    
    -- Return results
    RETURN QUERY VALUES 
        ('flow_run_history', flow_count),
        ('audit_log', audit_count),
        ('memory_context', context_count);
END;
$$ LANGUAGE plpgsql;

-- Create function to get memory usage statistics
CREATE OR REPLACE FUNCTION get_memory_usage_stats()
RETURNS TABLE (
    table_name TEXT,
    row_count BIGINT,
    table_size TEXT,
    index_size TEXT,
    total_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname||'.'||tablename as table_name,
        n_tup_ins - n_tup_del as row_count,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as table_size,
        pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as index_size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
    FROM pg_stat_user_tables 
    WHERE tablename IN ('flow_run_history', 'task_outputs', 'audit_log', 'memory_context', 'memory_events', 'vector_embeddings')
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
END;
$$ LANGUAGE plpgsql;

-- Add comments to new functions
COMMENT ON FUNCTION refresh_flow_run_stats() IS 'Refreshes the flow run statistics materialized view';
COMMENT ON FUNCTION get_context_stats() IS 'Returns statistics about memory contexts and events';
COMMENT ON FUNCTION cleanup_old_data(INTEGER, INTEGER, INTEGER) IS 'Cleans up old data from memory tables';
COMMENT ON FUNCTION get_memory_usage_stats() IS 'Returns memory usage statistics for all memory tables';
