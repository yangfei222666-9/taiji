-- AIOS Storage Manager SQL Queries
-- 使用 aiosql 加载这些查询

-- ==================== Agent States ====================

-- name: create_agent_states_table#
-- Create agent_states table
CREATE TABLE IF NOT EXISTS agent_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    state TEXT NOT NULL,
    timestamp REAL NOT NULL,
    active INTEGER DEFAULT 1
);

-- name: save_agent_state<!
-- Save agent state to database
INSERT INTO agent_states (agent_id, state, timestamp)
VALUES (:agent_id, :state, :timestamp);

-- name: get_agent_state^
-- Get latest agent state by id
SELECT state FROM agent_states
WHERE agent_id = :agent_id
ORDER BY timestamp DESC
LIMIT 1;

-- name: get_all_active_agents
-- Get all active agents
SELECT agent_id, state, timestamp
FROM agent_states
WHERE active = 1
ORDER BY timestamp DESC;

-- name: deactivate_agent<!
-- Mark agent as inactive
UPDATE agent_states
SET active = 0
WHERE agent_id = :agent_id;

-- ==================== Contexts ====================

-- name: create_contexts_table#
-- Create contexts table
CREATE TABLE IF NOT EXISTS contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    context TEXT NOT NULL,
    timestamp REAL NOT NULL
);

-- name: save_context<!
-- Save agent context
INSERT INTO contexts (agent_id, context, timestamp)
VALUES (:agent_id, :context, :timestamp);

-- name: get_latest_context^
-- Get latest context for agent
SELECT context FROM contexts
WHERE agent_id = :agent_id
ORDER BY timestamp DESC
LIMIT 1;

-- name: get_context_history
-- Get context history for agent
SELECT context, timestamp FROM contexts
WHERE agent_id = :agent_id
ORDER BY timestamp DESC
LIMIT :limit;

-- ==================== Events ====================

-- name: create_events_table#
-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    data TEXT,
    timestamp REAL NOT NULL
);

-- name: save_event<!
-- Save event to database
INSERT INTO events (type, level, message, data, timestamp)
VALUES (:type, :level, :message, :data, :timestamp);

-- name: get_recent_events
-- Get recent events
SELECT type, level, message, data, timestamp
FROM events
ORDER BY timestamp DESC
LIMIT :limit;

-- name: get_events_by_type
-- Get events by type
SELECT type, level, message, data, timestamp
FROM events
WHERE type = :type
ORDER BY timestamp DESC
LIMIT :limit;

-- name: get_error_events
-- Get error events
SELECT type, level, message, data, timestamp
FROM events
WHERE level = 'error'
ORDER BY timestamp DESC
LIMIT :limit;

-- name: count_events_by_type^
-- Count events by type
SELECT COUNT(*) FROM events
WHERE type = :type;

-- ==================== Cleanup ====================

-- name: delete_old_events<!
-- Delete events older than timestamp
DELETE FROM events
WHERE timestamp < :before_timestamp;

-- name: delete_old_contexts<!
-- Delete contexts older than timestamp
DELETE FROM contexts
WHERE timestamp < :before_timestamp;
