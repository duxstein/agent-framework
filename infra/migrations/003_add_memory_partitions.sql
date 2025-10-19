-- Migration: 003_add_memory_partitions.sql
-- Description: Add table partitioning for better performance on large datasets
-- Created: 2024-01-01
-- Author: Enterprise AI Agent Framework Team

-- Note: This migration adds partitioning support for tables that may grow large
-- It's optional and should only be applied if you expect high volume data

-- Create partitioned audit_log table (if not exists)
-- This will partition by month for better query performance
DO $$
BEGIN
    -- Check if audit_log is already partitioned
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c 
        JOIN pg_namespace n ON n.oid = c.relnamespace 
        WHERE c.relname = 'audit_log' 
        AND c.relkind = 'p'
    ) THEN
        -- Create new partitioned table
        CREATE TABLE audit_log_partitioned (
            LIKE audit_log INCLUDING ALL
        ) PARTITION BY RANGE (created_at);
        
        -- Create partitions for the next 12 months
        FOR i IN 0..11 LOOP
            EXECUTE format('
                CREATE TABLE audit_log_%s PARTITION OF audit_log_partitioned
                FOR VALUES FROM (%L) TO (%L)',
                to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
                date_trunc('month', CURRENT_DATE + (i || ' months')::interval),
                date_trunc('month', CURRENT_DATE + ((i+1) || ' months')::interval)
            );
        END LOOP;
        
        -- Copy data from old table to new partitioned table
        INSERT INTO audit_log_partitioned SELECT * FROM audit_log;
        
        -- Drop old table and rename new one
        DROP TABLE audit_log;
        ALTER TABLE audit_log_partitioned RENAME TO audit_log;
        
        -- Recreate indexes on the partitioned table
        CREATE INDEX idx_audit_log_entity_type ON audit_log(entity_type);
        CREATE INDEX idx_audit_log_entity_id ON audit_log(entity_id);
        CREATE INDEX idx_audit_log_action ON audit_log(action);
        CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
        CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
        CREATE INDEX idx_audit_log_entity_action ON audit_log(entity_type, entity_id, action);
        CREATE INDEX idx_audit_log_entity_created ON audit_log(entity_type, entity_id, created_at DESC);
        CREATE INDEX idx_audit_log_data_gin ON audit_log USING GIN (data);
        CREATE INDEX idx_audit_log_created_brin ON audit_log USING BRIN (created_at);
        
        RAISE NOTICE 'audit_log table partitioned successfully';
    ELSE
        RAISE NOTICE 'audit_log table is already partitioned';
    END IF;
END $$;

-- Create partitioned memory_events table (if not exists)
DO $$
BEGIN
    -- Check if memory_events is already partitioned
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c 
        JOIN pg_namespace n ON n.oid = c.relnamespace 
        WHERE c.relname = 'memory_events' 
        AND c.relkind = 'p'
    ) THEN
        -- Create new partitioned table
        CREATE TABLE memory_events_partitioned (
            LIKE memory_events INCLUDING ALL
        ) PARTITION BY RANGE (created_at);
        
        -- Create partitions for the next 6 months
        FOR i IN 0..5 LOOP
            EXECUTE format('
                CREATE TABLE memory_events_%s PARTITION OF memory_events_partitioned
                FOR VALUES FROM (%L) TO (%L)',
                to_char(CURRENT_DATE + (i || ' months')::interval, 'YYYY_MM'),
                date_trunc('month', CURRENT_DATE + (i || ' months')::interval),
                date_trunc('month', CURRENT_DATE + ((i+1) || ' months')::interval)
            );
        END LOOP;
        
        -- Copy data from old table to new partitioned table
        INSERT INTO memory_events_partitioned SELECT * FROM memory_events;
        
        -- Drop old table and rename new one
        DROP TABLE memory_events;
        ALTER TABLE memory_events_partitioned RENAME TO memory_events;
        
        -- Recreate indexes on the partitioned table
        CREATE INDEX idx_memory_events_context_id ON memory_events(context_id);
        CREATE INDEX idx_memory_events_event_id ON memory_events(event_id);
        CREATE INDEX idx_memory_events_created_at ON memory_events(created_at);
        CREATE INDEX idx_memory_events_context_created ON memory_events(context_id, created_at DESC);
        CREATE INDEX idx_memory_events_data_gin ON memory_events USING GIN (event_data);
        CREATE INDEX idx_memory_events_created_brin ON memory_events USING BRIN (created_at);
        
        RAISE NOTICE 'memory_events table partitioned successfully';
    ELSE
        RAISE NOTICE 'memory_events table is already partitioned';
    END IF;
END $$;

-- Create function to automatically create new partitions
CREATE OR REPLACE FUNCTION create_monthly_partition(
    table_name TEXT,
    start_date DATE
)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    end_date DATE;
BEGIN
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');
    end_date := start_date + INTERVAL '1 month';
    
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
        FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        table_name,
        start_date,
        end_date
    );
    
    RAISE NOTICE 'Created partition % for table %', partition_name, table_name;
END;
$$ LANGUAGE plpgsql;

-- Create function to create future partitions
CREATE OR REPLACE FUNCTION create_future_partitions(
    table_name TEXT,
    months_ahead INTEGER DEFAULT 3
)
RETURNS VOID AS $$
DECLARE
    i INTEGER;
    start_date DATE;
BEGIN
    FOR i IN 1..months_ahead LOOP
        start_date := date_trunc('month', CURRENT_DATE + (i || ' months')::interval);
        PERFORM create_monthly_partition(table_name, start_date);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create function to drop old partitions
CREATE OR REPLACE FUNCTION drop_old_partitions(
    table_name TEXT,
    months_to_keep INTEGER DEFAULT 12
)
RETURNS VOID AS $$
DECLARE
    partition_record RECORD;
    cutoff_date DATE;
BEGIN
    cutoff_date := date_trunc('month', CURRENT_DATE - (months_to_keep || ' months')::interval);
    
    FOR partition_record IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE tablename LIKE table_name || '_%'
        AND tablename ~ '^\d{4}_\d{2}$'
        AND to_date(replace(tablename, table_name || '_', ''), 'YYYY_MM') < cutoff_date
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE',
            partition_record.schemaname, partition_record.tablename);
        RAISE NOTICE 'Dropped old partition %', partition_record.tablename;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create function to maintain partitions automatically
CREATE OR REPLACE FUNCTION maintain_partitions()
RETURNS VOID AS $$
BEGIN
    -- Create future partitions for audit_log
    PERFORM create_future_partitions('audit_log', 3);
    
    -- Create future partitions for memory_events
    PERFORM create_future_partitions('memory_events', 3);
    
    -- Drop old partitions (keep 12 months)
    PERFORM drop_old_partitions('audit_log', 12);
    PERFORM drop_old_partitions('memory_events', 6);
    
    RAISE NOTICE 'Partition maintenance completed';
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job function (requires pg_cron extension)
-- This is optional and only works if pg_cron is installed
DO $$
BEGIN
    -- Check if pg_cron extension exists
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        -- Schedule partition maintenance to run monthly
        PERFORM cron.schedule('maintain-memory-partitions', '0 2 1 * *', 'SELECT maintain_partitions();');
        RAISE NOTICE 'Scheduled partition maintenance job';
    ELSE
        RAISE NOTICE 'pg_cron extension not available - partition maintenance must be run manually';
    END IF;
END $$;

-- Add comments to new functions
COMMENT ON FUNCTION create_monthly_partition(TEXT, DATE) IS 'Creates a monthly partition for the specified table';
COMMENT ON FUNCTION create_future_partitions(TEXT, INTEGER) IS 'Creates future partitions for the specified table';
COMMENT ON FUNCTION drop_old_partitions(TEXT, INTEGER) IS 'Drops old partitions older than the specified number of months';
COMMENT ON FUNCTION maintain_partitions() IS 'Maintains partitions by creating future ones and dropping old ones';

-- Create view to show partition information
CREATE OR REPLACE VIEW memory_partition_info AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_stat_get_tuples_returned(c.oid) as tuples_returned,
    pg_stat_get_tuples_fetched(c.oid) as tuples_fetched,
    pg_stat_get_tuples_inserted(c.oid) as tuples_inserted,
    pg_stat_get_tuples_updated(c.oid) as tuples_updated,
    pg_stat_get_tuples_deleted(c.oid) as tuples_deleted
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
WHERE tablename LIKE '%_%' 
AND tablename ~ '^\d{4}_\d{2}$'
AND (tablename LIKE 'audit_log_%' OR tablename LIKE 'memory_events_%')
ORDER BY tablename;

COMMENT ON VIEW memory_partition_info IS 'Shows information about memory table partitions';
