# Storage Manager 使用指南

## 概述

Storage Manager 是 AIOS 的持久化存储层，使用 **aiosqlite** 实现异步数据库操作。

**核心功能：**
1. Agent 状态持久化
2. 上下文持久化
3. 事件存储（替代 events.jsonl）
4. 任务历史记录
5. 查询和索引

**技术栈：**
- **aiosqlite** - 异步 SQLite 接口
- **零依赖** - SQLite 内置
- **原生 SQL** - 灵活、高效

---

## 快速开始

### 1. 初始化

```python
from storage import get_storage_manager, close_storage_manager

# 获取全局实例
storage = await get_storage_manager("aios.db")

# 使用完毕后关闭
await close_storage_manager()
```

### 2. Agent 状态管理

```python
# 保存 Agent 状态
await storage.save_agent_state(
    agent_id="coder_1",
    role="coder",
    state="idle",
    goal="Write clean code",
    backstory="Expert Python developer",
    stats={"tasks_completed": 10, "success_rate": 0.9}
)

# 获取 Agent 状态
agent = await storage.get_agent_state("coder_1")
print(agent)  # {'agent_id': 'coder_1', 'role': 'coder', ...}

# 列出所有 Agent
agents = await storage.list_agent_states(active_only=True)

# 删除 Agent
await storage.delete_agent_state("coder_1")
```

### 3. 上下文管理

```python
# 保存上下文
context_id = await storage.save_context(
    agent_id="coder_1",
    context_data={"current_task": "refactor", "variables": {"x": 1}},
    session_id="session_123",
    expires_at=time.time() + 3600  # 1小时后过期
)

# 获取上下文
context = await storage.get_context(context_id)
print(context['context_data'])  # {'current_task': 'refactor', ...}

# 列出 Agent 的所有上下文
contexts = await storage.list_contexts_by_agent("coder_1")

# 清理过期上下文
await storage.cleanup_expired_contexts()
```

### 4. 事件记录

```python
# 记录事件
await storage.log_event(
    event_type="task_start",
    data={"task_id": "task_1", "description": "Refactor code"},
    agent_id="coder_1",
    severity="info"
)

# 列出事件（支持过滤）
events = await storage.list_events(
    agent_id="coder_1",
    event_type="task_start",
    start_time=time.time() - 86400,  # 最近24小时
    limit=100
)

# 统计事件
count = await storage.count_events(agent_id="coder_1")

# 清理旧事件
await storage.cleanup_old_events(days=30)
```

### 5. 任务历史

```python
# 记录任务
await storage.log_task(
    task_id="task_1",
    agent_id="coder_1",
    task_type="code",
    priority="high",
    status="pending"
)

# 更新任务状态
await storage.update_task_status(
    task_id="task_1",
    status="running",
    started_at=time.time()
)

# 任务完成
await storage.update_task_status(
    task_id="task_1",
    status="completed",
    completed_at=time.time(),
    duration=10.5,
    result={"output": "Success"}
)

# 获取任务
task = await storage.get_task("task_1")

# 列出 Agent 的任务
tasks = await storage.list_tasks_by_agent("coder_1", limit=100)

# 列出指定状态的任务
pending_tasks = await storage.list_tasks_by_status("pending")

# 获取 Agent 统计
stats = await storage.get_agent_stats("coder_1")
print(stats)  # {'total_tasks': 10, 'completed_tasks': 8, ...}
```

---

## 数据库 Schema

### agent_states 表

| 字段 | 类型 | 说明 |
|------|------|------|
| agent_id | TEXT | Agent ID（主键） |
| role | TEXT | 角色（coder/analyst/monitor） |
| goal | TEXT | 目标 |
| backstory | TEXT | 背景故事 |
| state | TEXT | 状态（idle/busy/failed/archived） |
| created_at | REAL | 创建时间 |
| updated_at | REAL | 更新时间 |
| last_task_id | TEXT | 最后任务 ID |
| stats_json | TEXT | 统计数据（JSON） |

### contexts 表

| 字段 | 类型 | 说明 |
|------|------|------|
| context_id | TEXT | 上下文 ID（主键） |
| agent_id | TEXT | Agent ID |
| session_id | TEXT | 会话 ID |
| context_data | TEXT | 上下文数据（JSON） |
| created_at | REAL | 创建时间 |
| expires_at | REAL | 过期时间 |

### events 表

| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | TEXT | 事件 ID（主键） |
| event_type | TEXT | 事件类型 |
| agent_id | TEXT | Agent ID |
| timestamp | REAL | 时间戳 |
| data_json | TEXT | 事件数据（JSON） |
| severity | TEXT | 严重程度（info/warning/error/critical） |

### task_history 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | TEXT | 任务 ID（主键） |
| agent_id | TEXT | Agent ID |
| task_type | TEXT | 任务类型 |
| priority | TEXT | 优先级 |
| status | TEXT | 状态（pending/running/completed/failed） |
| created_at | REAL | 创建时间 |
| started_at | REAL | 开始时间 |
| completed_at | REAL | 完成时间 |
| duration | REAL | 耗时（秒） |
| result_json | TEXT | 结果（JSON） |
| error_message | TEXT | 错误信息 |

---

## 索引

为了提高查询性能，Storage Manager 创建了以下索引：

- `idx_events_timestamp` - 事件时间戳索引
- `idx_events_agent_id` - 事件 Agent ID 索引
- `idx_events_type` - 事件类型索引
- `idx_contexts_agent_id` - 上下文 Agent ID 索引
- `idx_contexts_expires_at` - 上下文过期时间索引
- `idx_task_history_agent_id` - 任务 Agent ID 索引
- `idx_task_history_status` - 任务状态索引
- `idx_task_history_created_at` - 任务创建时间索引

---

## 最佳实践

### 1. 使用全局实例

```python
# ✅ 推荐：使用全局实例
storage = await get_storage_manager()

# ❌ 不推荐：每次创建新实例
storage = StorageManager()
await storage.initialize()
```

### 2. 及时清理过期数据

```python
# 定期清理过期上下文
await storage.cleanup_expired_contexts()

# 定期清理旧事件（保留30天）
await storage.cleanup_old_events(days=30)
```

### 3. 使用事务

```python
# 批量操作时使用事务
async with storage._db.execute("BEGIN"):
    await storage.save_agent_state(...)
    await storage.log_event(...)
    await storage._db.commit()
```

### 4. 合理设置过期时间

```python
# 短期上下文（1小时）
await storage.save_context(
    agent_id="coder_1",
    context_data={...},
    expires_at=time.time() + 3600
)

# 长期上下文（不过期）
await storage.save_context(
    agent_id="coder_1",
    context_data={...},
    expires_at=None
)
```

---

## 性能优化

### 1. 批量查询

```python
# ✅ 推荐：一次查询多个 Agent
agents = await storage.list_agent_states()

# ❌ 不推荐：循环查询
for agent_id in agent_ids:
    agent = await storage.get_agent_state(agent_id)
```

### 2. 使用索引

```python
# ✅ 推荐：使用索引字段过滤
events = await storage.list_events(
    agent_id="coder_1",  # 使用索引
    start_time=time.time() - 86400  # 使用索引
)

# ❌ 不推荐：全表扫描
events = await storage.list_events(limit=10000)
```

### 3. 限制结果数量

```python
# ✅ 推荐：使用 limit
events = await storage.list_events(limit=100)

# ❌ 不推荐：不限制结果
events = await storage.list_events(limit=999999)
```

---

## 测试

运行测试：

```bash
cd ${TAIJIOS_HOME}/.openclaw\workspace\aios
python test_storage_manager.py
```

**测试覆盖：**
- ✅ Agent 状态管理（3个测试）
- ✅ 上下文管理（3个测试）
- ✅ 事件记录（3个测试）
- ✅ 任务历史（6个测试）

**总计：15/15 测试通过**

---

## 常见问题

### Q: 为什么选择 SQLite？

A: SQLite 是零依赖、嵌入式数据库，非常适合 AIOS 的场景：
- 无需安装额外服务
- 单文件存储，易于备份
- 支持并发读写
- 性能足够（每秒数千次查询）

### Q: 如何迁移现有数据？

A: 可以编写迁移脚本，从 events.jsonl 导入到 SQLite：

```python
import json
import asyncio
from storage import get_storage_manager

async def migrate():
    storage = await get_storage_manager()
    
    with open("events.jsonl") as f:
        for line in f:
            event = json.loads(line)
            await storage.log_event(
                event_type=event['type'],
                data=event,
                agent_id=event.get('agent_id'),
                severity=event.get('severity', 'info')
            )
    
    await close_storage_manager()

asyncio.run(migrate())
```

### Q: 如何备份数据库？

A: 直接复制 `aios.db` 文件即可：

```bash
cp aios.db aios.db.backup
```

或使用 SQLite 的备份命令：

```bash
sqlite3 aios.db ".backup aios.db.backup"
```

---

**版本：** v1.0  
**创建时间：** 2026-02-26  
**维护者：** 小九 + 珊瑚海
