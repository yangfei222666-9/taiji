-- AIOS Storage Schema
-- 创建时间：2026-02-26
-- 版本：v1.0

-- Agent 状态表
CREATE TABLE IF NOT EXISTS agent_states (
    agent_id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    goal TEXT,
    backstory TEXT,
    state TEXT NOT NULL,  -- idle/busy/failed/archived
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    last_task_id TEXT,
    stats_json TEXT  -- JSON 格式的统计数据
);

-- 上下文表
CREATE TABLE IF NOT EXISTS contexts (
    context_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    session_id TEXT,
    context_data TEXT NOT NULL,  -- JSON 格式
    created_at REAL NOT NULL,
    expires_at REAL,
    FOREIGN KEY (agent_id) REFERENCES agent_states(agent_id)
);

-- 事件表（替代 events.jsonl）
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,  -- task_start/task_complete/task_failed/agent_created/etc.
    agent_id TEXT,
    timestamp REAL NOT NULL,
    data_json TEXT NOT NULL,  -- JSON 格式的事件数据
    severity TEXT,  -- info/warning/error/critical
    FOREIGN KEY (agent_id) REFERENCES agent_states(agent_id)
);

-- 任务历史表
CREATE TABLE IF NOT EXISTS task_history (
    task_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    priority TEXT,
    status TEXT NOT NULL,  -- pending/running/completed/failed
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    duration REAL,
    result_json TEXT,  -- JSON 格式的结果
    error_message TEXT,
    FOREIGN KEY (agent_id) REFERENCES agent_states(agent_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_contexts_agent_id ON contexts(agent_id);
CREATE INDEX IF NOT EXISTS idx_contexts_expires_at ON contexts(expires_at);
CREATE INDEX IF NOT EXISTS idx_task_history_agent_id ON task_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_task_history_status ON task_history(status);
CREATE INDEX IF NOT EXISTS idx_task_history_created_at ON task_history(created_at);
