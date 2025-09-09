-- Create Agents Table for Job Scheduler
-- This table stores registered agents and their status

CREATE TABLE agents (
    id INT IDENTITY(1,1) PRIMARY KEY,
    agent_id NVARCHAR(100) UNIQUE NOT NULL,
    agent_name NVARCHAR(200),
    hostname NVARCHAR(200),
    ip_address NVARCHAR(50),
    agent_pool NVARCHAR(100) DEFAULT 'default',
    capabilities NVARCHAR(MAX), -- JSON array of capabilities
    max_parallel_jobs INT DEFAULT 2,
    agent_version NVARCHAR(50),
    status NVARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected, inactive
    is_approved BIT DEFAULT 0,
    last_heartbeat DATETIME,
    registered_at DATETIME DEFAULT GETDATE(),
    approved_at DATETIME,
    approved_by NVARCHAR(100),
    notes NVARCHAR(MAX),
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE()
);

-- Create index for faster queries
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pool ON agents(agent_pool);
CREATE INDEX idx_agents_approved ON agents(is_approved);

-- Sample insert for testing
/*
INSERT INTO agents (agent_id, agent_name, hostname, ip_address, agent_pool, capabilities, status, is_approved)
VALUES 
    ('test-agent-001', 'Test Agent 01', 'TEST-SERVER', '192.168.1.100', 'default', '["powershell","python","shell"]', 'approved', 1),
    ('win-prod-001', 'Windows Production 01', 'PROD-WIN-01', '192.168.1.101', 'production', '["powershell","python","shell"]', 'pending', 0);
*/