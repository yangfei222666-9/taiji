# Self-Improving Loop

> 让 AI Agent 自动进化 - 完整的自我改进闭环，包含自动回滚、自适应阈值和实时通知

[![Tests](https://img.shields.io/badge/tests-17%2F17%20passing-brightgreen)](tests/)
[![Performance](https://img.shields.io/badge/overhead-%3C1%25-brightgreen)](docs/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🌟 核心特性

- 🔄 **完整的 7 步改进闭环** - 执行 → 记录 → 分析 → 生成 → 应用 → 验证 → 更新
- 🛡️ **自动回滚** - 效果变差自动回滚，保护生产环境
- 🧠 **自适应阈值** - 根据 Agent 特性动态调整触发条件
- 📱 **实时通知** - Telegram 推送改进和回滚事件
- ✅ **高测试覆盖** - 17/17 测试用例全部通过
- ⚡ **低性能开销** - <1% 性能影响

## 🚀 快速开始

### 安装

```bash
pip install self-improving-loop
```

### 基础使用

```python
from self_improving_loop import SelfImprovingLoop

# 创建实例
loop = SelfImprovingLoop()

# 包装任务执行
result = loop.execute_with_improvement(
    agent_id="my-agent",
    task="处理用户请求",
    execute_fn=lambda: agent.run_task(task)
)

# 检查结果
if result["improvement_triggered"]:
    print(f"应用了 {result['improvement_applied']} 项改进")

if result["rollback_executed"]:
    print(f"已回滚: {result['rollback_executed']['reason']}")
```

## 📖 工作原理

### 完整闭环

```
执行任务 → 记录结果 → 分析失败模式 → 生成改进建议 
    ↓                                          ↑
更新配置 ← 验证效果 ← 自动应用 ← ─────────────┘
```

### 自动回滚

当检测到以下情况时自动回滚：
- 成功率下降 >10%
- 平均耗时增加 >20%
- 连续失败 ≥5 次

### 自适应阈值

根据 Agent 特性自动调整：

| Agent 类型 | 失败阈值 | 分析窗口 | 冷却期 |
|-----------|---------|---------|--------|
| 高频      | 5 次    | 48 小时 | 3 小时 |
| 中频      | 3 次    | 24 小时 | 6 小时 |
| 低频      | 2 次    | 72 小时 | 12 小时 |
| 关键      | 1 次    | 24 小时 | 6 小时 |

## 🎯 使用场景

### 1. AI Agent 系统
```python
class MyAgent:
    def __init__(self):
        self.loop = SelfImprovingLoop()
    
    def run_task(self, task):
        return self.loop.execute_with_improvement(
            agent_id=self.id,
            task=task,
            execute_fn=lambda: self._do_task(task)
        )
```

### 2. 微服务监控
```python
@with_self_improvement("api-service")
def handle_request(request):
    # 自动监控和改进
    return process_request(request)
```

### 3. 批量任务处理
```python
for task in task_queue:
    result = loop.execute_with_improvement(
        agent_id=f"worker-{task.type}",
        task=task.description,
        execute_fn=lambda: process_task(task)
    )
```

## 📊 性能指标

- **追踪记录**: ~5ms
- **失败分析**: ~100ms（仅触发时）
- **改进应用**: ~200ms（仅触发时）
- **回滚执行**: ~10ms
- **总体开销**: <1%

## 🔧 高级配置

### 手动设置阈值

```python
from adaptive_threshold import AdaptiveThreshold

adaptive = AdaptiveThreshold()
adaptive.set_manual_threshold(
    "critical-agent",
    failure_threshold=1,
    analysis_window_hours=12,
    cooldown_hours=1,
    is_critical=True
)
```

### 自定义通知

```python
from telegram_notifier import TelegramNotifier

notifier = TelegramNotifier(enabled=True)
notifier.notify_improvement(
    agent_id="my-agent",
    improvements_applied=2,
    details={"timeout": "30s → 45s"}
)
```

### 查看统计

```python
# 单个 Agent
stats = loop.get_improvement_stats("my-agent")
print(f"成功率: {stats['agent_stats']['success_rate']:.1%}")
print(f"回滚次数: {stats['rollback_count']}")

# 全局统计
global_stats = loop.get_improvement_stats()
print(f"总改进次数: {global_stats['total_improvements']}")
print(f"总回滚次数: {global_stats['total_rollbacks']}")
```

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python test_self_improving_loop.py
python test_auto_rollback.py
python test_adaptive_threshold.py
```

## 📚 文档

- [集成指南](docs/INTEGRATION.md)
- [架构设计](docs/ARCHITECTURE.md)
- [API 参考](docs/API.md)
- [最佳实践](docs/BEST_PRACTICES.md)

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

### 开发设置

```bash
# 克隆仓库
git clone https://github.com/yourusername/self-improving-loop.git
cd self-improving-loop

# 安装依赖
pip install -r requirements-dev.txt

# 运行测试
pytest
```

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md)

## 📄 许可证

[MIT License](LICENSE)

## 🙏 致谢

灵感来源于 AIOS 项目，感谢所有贡献者。

## 🔗 相关项目

- [AIOS](https://github.com/yourusername/aios) - AI 操作系统
- [Agent Evolution](https://github.com/yourusername/agent-evolution) - Agent 进化框架

## 📧 联系

- Issues: [GitHub Issues](https://github.com/yourusername/self-improving-loop/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/self-improving-loop/discussions)

---

**"Safety first, then automation."**

Made with ❤️ by the Self-Improving Loop team
