-- AIOS Storage Queries
-- 创建时间：2026-02-26
-- 版本：v1.0

-- name: get_agent_state$
-- Get agent state by ID
SELECT * FROM agent_states WHERE agent_id = :agent_id;

-- name: list_agent_states$
-- List all agent states
SELECT * FROM agent_states ORDER BY updated_at DESC;

-- name: list_active_agents$
-- List active agents (not archived)
SELECT * FROM agent_states WHERE state != 'archived' ORDER BY updated_at DESC;

-- name: upsert_agent_state!
-- Insert or update agent state
INSERT INTO agent_states (agent_id, role, goal, backstory, state, created_at, updated_at, last_task_id, stats_json)
VALUES (:agent_id, :role, :goal, :backstory, :state, :created_at, :updated_at, :last_task_id, :stats_json)
ON CONFLICT(agent_id) DO UPDATE SET
    role = :role,
    goal = :goal,
    backstory = :backstory,
    state = :state,
    updated_at = :updated_at,
    last_task_id = :last_task_id,
    stats_json = :stats_json;

-- name: delete_agent_state!
-- Delete agent state
DELETE FROM agent_states WHERE agent_id = :agent_id;

-- name: get_context$
-- Get context by ID
SELECT * FROM contexts WHERE context_id = :context_id;

-- name: list_contexts_by_agent$
-- List contexts for an agent
SELECT * FROM contexts WHERE agent_id = :agent_id ORDER BY created_at DESC;

-- name: insert_context!
-- Insert new context
INSERT INTO contexts (context_id, agent_id, session_id, context_data, created_at, expires_at)
VALUES (:context_id, :agent_id, :session_id, :context_data, :created_at, :expires_at);

-- name: update_context!
-- Update context data
UPDATE contexts SET context_data = :context_data, updated_at = :updated_at WHERE context_id = :context_id;

-- name: delete_context!
-- Delete context
DELETE FROM contexts WHERE context_id = :context_id;

-- name: delete_expired_contexts!
-- Delete expired contexts
DELETE FROM contexts WHERE expires_at IS NOT NULL AND expires_at < :current_time;

-- name: insert_event!
-- Insert new event
INSERT INTO events (event_id, event_type, agent_id, timestamp, data_json, severity)
VALUES (:event_id, :event_type, :agent_id, :timestamp, :data_json, :severity);

-- name: list_events$
-- List events with optional filters
SELECT * FROM events
WHERE (:agent_id IS NULL OR agent_id = :agent_id)
  AND (:event_type IS NULL OR event_type = :event_type)
  AND (:start_time IS NULL OR timestamp >= :start_time)
  AND (:end_time IS NULL OR timestamp <= :end_time)
ORDER BY timestamp DESC
LIMIT :limit OFFSET :offset;

-- name: count_events^
-- Count events with optional filters
SELECT COUNT(*) as count FROM events
WHERE (:agent_id IS NULL OR agent_id = :agent_id)
  AND (:event_type IS NULL OR event_type = :event_type)
  AND (:start_time IS NULL OR timestamp >= :start_time)
  AND (:end_time IS NULL OR timestamp <= :end_time);

-- name: delete_old_events!
-- Delete events older than a certain timestamp
DELETE FROM events WHERE timestamp < :cutoff_time;

-- name: insert_task!
-- Insert new task
INSERT INTO task_history (task_id, agent_id, task_type, priority, status, created_at, started_at, completed_at, duration, result_json, error_message)
VALUES (:task_id, :agent_id, :task_type, :priority, :status, :created_at, :started_at, :completed_at, :duration, :result_json, :error_message);

-- name: update_task_status!
-- Update task status
UPDATE task_history SET
    status = :status,
    started_at = :started_at,
    completed_at = :completed_at,
    duration = :duration,
    result_json = :result_json,
    error_message = :error_message
WHERE task_id = :task_id;

-- name: get_task$
-- Get task by ID
SELECT * FROM task_history WHERE task_id = :task_id;

-- name: list_tasks_by_agent$
-- List tasks for an agent
SELECT * FROM task_history WHERE agent_id = :agent_id ORDER BY created_at DESC LIMIT :limit;

-- name: list_tasks_by_status$
-- List tasks by status
SELECT * FROM task_history WHERE status = :status ORDER BY created_at DESC LIMIT :limit;

-- name: get_agent_stats^
-- Get agent statistics
SELECT
    agent_id,
    COUNT(*) as total_tasks,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
    AVG(CASE WHEN duration IS NOT NULL THEN duration ELSE NULL END) as avg_duration
FROM task_history
WHERE agent_id = :agent_id
GROUP BY agent_id;
