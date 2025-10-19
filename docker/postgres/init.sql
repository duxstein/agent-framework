-- PostgreSQL initialization script for Enterprise AI Agent Framework
-- This script creates the necessary tables and indexes

-- Create flow_runs_audit table
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

-- Create webhook_configs table
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

-- Create flows table (for Flow Registry)
CREATE TABLE IF NOT EXISTS flows (
    flow_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    tenant_id VARCHAR(255),
    description TEXT,
    tags JSONB,
    flow_data JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for flow_runs_audit
CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_run_id ON flow_runs_audit(run_id);
CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_tenant_id ON flow_runs_audit(tenant_id);
CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_flow_id ON flow_runs_audit(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_status ON flow_runs_audit(status);
CREATE INDEX IF NOT EXISTS idx_flow_runs_audit_created_at ON flow_runs_audit(created_at);

-- Create indexes for webhook_configs
CREATE INDEX IF NOT EXISTS idx_webhook_configs_webhook_id ON webhook_configs(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_configs_tenant_id ON webhook_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_webhook_configs_enabled ON webhook_configs(enabled);

-- Create indexes for flows
CREATE INDEX IF NOT EXISTS idx_flows_tenant_id ON flows(tenant_id);
CREATE INDEX IF NOT EXISTS idx_flows_name ON flows(name);
CREATE INDEX IF NOT EXISTS idx_flows_version ON flows(version);
CREATE INDEX IF NOT EXISTS idx_flows_tags ON flows USING GIN(tags);

-- Insert sample webhook configuration
INSERT INTO webhook_configs (webhook_id, flow_id, tenant_id, user_id, webhook_config, enabled) 
VALUES (
    'sample-webhook-1',
    'sample-flow-1',
    'tenant-1',
    'user-1',
    '{"transform": {"input_mapping": {"message": "webhook_payload.message", "source": "webhook_source"}}}',
    true
) ON CONFLICT (webhook_id) DO NOTHING;

-- Insert sample flow
INSERT INTO flows (flow_id, name, version, tenant_id, description, tags, flow_data, metadata) 
VALUES (
    'sample-flow-1',
    'Sample Flow',
    '1.0.0',
    'tenant-1',
    'A sample flow for testing',
    '["sample", "test"]',
    '{"id": "sample-flow-1", "version": "1.0.0", "tasks": [{"id": "task-1", "handler": "test-handler", "inputs": {"param1": "value1"}, "retries": 3, "timeout": 300}], "type": "DAG", "tenant_id": "tenant-1"}',
    '{"author": "system", "category": "sample"}'
) ON CONFLICT (flow_id) DO NOTHING;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_flow_runs_audit_updated_at 
    BEFORE UPDATE ON flow_runs_audit 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_webhook_configs_updated_at 
    BEFORE UPDATE ON webhook_configs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_flows_updated_at 
    BEFORE UPDATE ON flows 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
