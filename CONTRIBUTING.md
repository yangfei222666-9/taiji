# Contributing to TaijiOS 贡献指南

感谢你对太极OS的兴趣！以下是参与贡献的完整指南。

## 从哪里下手？

| 难度 | 推荐方向 | 说明 |
|------|----------|------|
| 🟢 入门 | `good first issue` 标签 | 文档修正、类型标注、测试补全 |
| 🟡 中级 | 新增 Agent 模板 | 在 `aios/agent_system/` 下新增一个 Agent，复用现有生命周期 |
| 🟡 中级 | HUD 面板扩展 | 给 `taijios_hud.html` 加新的可视化面板 |
| 🔴 高级 | 引擎级贡献 | 五引擎（情势/震卦/师卦/人格/颐卦）的核心逻辑改进 |

## Getting Started 快速上手

```bash
# 1. Fork & Clone
git clone https://github.com/<your-username>/TaijiOS.git
cd TaijiOS

# 2. 创建分支
git checkout -b feature/your-feature

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 跑测试，确保基线通过
python -m pytest tests/ -v

# 5. 写代码 + 写测试

# 6. 提交
git add <files>
git commit -m "feat: 你的改动描述"

# 7. 推送 & 开 PR
git push origin feature/your-feature
```

## Code Guidelines 代码规范

- **路径**: 用 `Path(__file__).parent` 做相对路径，禁止硬编码绝对路径
- **密钥**: 用 `os.environ.get()` 或 `secret_manager.py`，禁止明文提交
- **Python**: 用 `sys.executable`，不硬编码 Python 路径
- **风格**: 遵循你修改的模块的现有风格
- **日志**: 可观测操作加结构化日志（`logging.info` + JSON payload）
- **测试**: 新功能需附带测试，修 bug 需附带回归测试

## Commit Convention 提交约定

```
feat: 新功能
fix: 修 bug
docs: 文档
test: 测试
refactor: 重构（不改行为）
chore: 构建/工具链
```

## PR Checklist

提交 PR 前请确认：

- [ ] `python -m pytest tests/` 全部通过
- [ ] 没有提交 API Key / Token / 密钥
- [ ] 新功能有对应测试
- [ ] 改动有清晰的 commit message

## 五引擎贡献须知

五引擎的职责由卦象严格划分，贡献时请遵守边界：

| 引擎 | 只管 | 不要碰 |
|------|------|--------|
| 情势 | 态势感知、维度评估、张力检测 | 故障恢复、任务调度 |
| 震卦 | 故障检测、熔断器、恢复流程 | 任务分配、学习 |
| 师卦 | 集群调度、阵型、任务分配 | 故障处理、人格切换 |
| 人格 | Persona 匹配、切换、风格适配 | 经验沉淀、调度 |
| 颐卦 | 经验学习、知识消化、命中追踪 | 故障恢复、调度 |

跨引擎通信统一走 EventBus，不要直接调用其他引擎的内部方法。

## Security 安全

- 禁止提交任何密钥、凭证、Token
- 密钥访问统一走 `secret_manager.py`
- 安全问题请私信报告，不要开公开 Issue（详见 [SECURITY.md](SECURITY.md)）

## License

贡献即表示同意以 [Apache License 2.0](LICENSE) 授权你的代码。

---

**太极生两仪** — 每一行代码都是太极OS演化的一部分。
