-- Fakturenn PostgreSQL Schema

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    language VARCHAR(10) DEFAULT 'fr',
    timezone VARCHAR(50) DEFAULT 'Europe/Paris',
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Automations table
CREATE TABLE automations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    schedule VARCHAR(100),
    from_date_rule VARCHAR(50),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

-- Sources table
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('FreeInvoice', 'FreeMobileInvoice', 'Gmail')),
    email_sender_from VARCHAR(255),
    email_subject_contains VARCHAR(255),
    extraction_params JSONB,
    max_results INTEGER DEFAULT 30,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Exports table (supports multiple types: Paheko, LocalStorage, GoogleDrive)
CREATE TABLE exports (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('Paheko', 'LocalStorage', 'GoogleDrive')),
    configuration JSONB NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Source-Export mappings (many-to-many)
CREATE TABLE source_export_mappings (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    export_id INTEGER NOT NULL REFERENCES exports(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 1,
    conditions JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, export_id)
);

-- Jobs table (execution tracking)
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    from_date DATE,
    max_results INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    stats JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Export history (audit trail)
CREATE TABLE export_history (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    export_id INTEGER REFERENCES exports(id) ON DELETE SET NULL,
    export_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'duplicate_skipped')),
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    context JSONB,
    external_reference VARCHAR(255)
);

-- Audit log
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    details JSONB
);

-- Indexes for better query performance
CREATE INDEX idx_automations_user ON automations(user_id);
CREATE INDEX idx_sources_automation ON sources(automation_id);
CREATE INDEX idx_exports_automation ON exports(automation_id);
CREATE INDEX idx_mappings_source ON source_export_mappings(source_id);
CREATE INDEX idx_mappings_export ON source_export_mappings(export_id);
CREATE INDEX idx_jobs_automation ON jobs(automation_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_export_history_job ON export_history(job_id);
CREATE INDEX idx_export_history_export ON export_history(export_id);
CREATE INDEX idx_export_history_status ON export_history(status);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);
