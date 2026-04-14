# TaijiOS 优化清单

> 2026-04-14 整理，严格按 P0→P1→P2→P3 执行，不跳级

---

## P0 — 安全（不修会出事）

- [x] **1. `sensors.py` 命令注入** — ✅ 已修复（latest用`-LiteralPath $args[0]`替代f-string拼接）
- [x] **2. `engine.py` OOM** — ✅ 2026-04-14 修复，`read_text().splitlines()` → `open() for line in f` 流式读取
- [x] **3. OpenClaw 凭证明文存储** — ✅ auth.json已清空真实token改为空模板；OpenClaw备份无凭证泄露；secret_manager.py已实现环境变量管理
- [x] **4. Telegram bot token 泄露在 git 历史** — ✅ 侦察确认：所有Telegram配置均使用环境变量，无硬编码token

## P0 — 跑通（系统能正常工作）

- [x] **5. `task_executions.jsonl` schema 规范化** — ✅ 侦察确认 agent_id/status 字段已存在，execution_logger.py 已正确写入
- [x] **6. Lifecycle Engine 接入心跳** — ✅ 侦察确认 heartbeat_v5.py 已调用 run_lifecycle_engine()，lifecycle 算分并写回 agents.json
- [x] **7. 10 个 Agent 注册了从未执行** — ✅ 根因：learning_scheduler.py 存在但未被心跳调用。已在 heartbeat_v5.py 中接入 learning_scheduler（在 execute_spawn_requests 之前）。15个active agent中11个有schedule字段，现在会按 interval_hours 自动派发
- [x] **8. TaijiOS 测试覆盖率 — 核心模块优先** — ✅ 新增 138 个测试（4个测试文件），覆盖 config(94%) / engine(85%) / executor(92%) / lifecycle_engine(100%)。pytest.ini 已更新。全量 codebase 53k行覆盖率受限于非核心模块数量，核心模块均 >85%

## P1 — 变卦推演系统质量

- [x] **9. 5 个卦象策略错配** — ✅ 已修复8个（泰豫晋临益困谦丰），剥经复查确认为false positive（"扩张"在否定语境），0个残留错配
- [x] **10. 同一转换对缺语境分支** — ✅ _generate_prediction 支持 dict 格式分支（按动爻 index 选文案，fallback 到 default）。已为 谦→丰/困→复/泰→否/否→泰/屯→渐 5对高频转换添加动爻分支（共15条分支文案）
- [x] **11. fit_score 评分逻辑重构** — ✅ elif互斥链→累加制（基础3分+加减分+clamp 1-5）；关键词改完整短语防误匹配；加动爻维度加分（+0.5）；去掉rate>0.5宽松兜底。64轮测试通过，90%综合评分
- [x] **12. experience_crystals.json 写入逻辑** — ✅ 侦察确认已实现：crystallizer.crystallize()→_save_crystals()→safe_json_save() 完整链路。每10轮对话自动触发+退出时触发，支持衰减/去重/容量上限

## P1 — 架构补齐

- [x] **13. TaijiOS 加 async/await** — ✅ bot_telegram.py 改为 async：requests→aiohttp，长轮询非阻塞，LLM调用用 asyncio.to_thread 不阻塞事件循环。requirements.txt 加 aiohttp。api_server.py/bot_core.py 深层async留后续
- [x] **14. 配置统一** — ✅ 新建 settings.py（dataclass 单例），收敛 AI模型/Telegram/飞书/路径 所有配置。自动检测 API key + provider。旧代码可逐步迁移到 `from settings import cfg`
- [x] **15. Docker Compose 部署方案** — ✅ Dockerfile + docker-compose.yml + .dockerignore。telegram-bot 默认启动，feishu-bot/cli 按 profile 可选。data/ 目录挂载持久化
- [x] **16. task_executor.py UTF-8 编码修复** — ✅ 添加 PYTHONUTF8=1 + sys.stdout.reconfigure(encoding="utf-8", errors="replace")，防止 Windows 下中文输出 UnicodeEncodeError

## P2 — 结构治理

- [x] **17. 拆分 analyze.py** — ✅ 三层拆分：analyze_extract.py（输入/字段提取）→ analyze.py（分析/compute_*）→ analyze_report.py（报告生成/输出）。向后兼容 import
- [x] **18. 解决同名模块冲突 + 清理循环依赖** — ✅ 审计完成：无实际循环依赖（core→agent_system 单向）。同名文件主要在 dist/backup 目录中（AIOS-Friend-Edition、AIOS-Portable 等旧副本），活跃代码不冲突。818个 sys.path.insert 留后续治理
- [x] **19. 包结构治理** — ✅ pyproject.toml 已存在且完整；bare except 全量清理（core/learning/agent_system/ 活跃代码 0 残留，`except:` → `except Exception:`）；并发锁已加：engine.py `_jsonl_lock`、executor.py `_exec_log_lock`、agent_lifecycle_engine.py `_agents_state_lock` + 原子写入（tmp+rename）
- [x] **20. OpenClaw 语音方案统一** — ✅ 审计确认实际2套TTS实现（SimpleTTS+TTSSpeaker），其余3个是ASR/daemon/health-check。统一到 tts_speaker.py（TTSSpeaker，edge_tts→pyttsx3→SAPI 三级 fallback）。simple_tts.py 改为 shim（`SimpleTTS = TTSSpeaker`），wake_listener.py 无需改动
- [x] **21. hermes-agent 大文件拆分** — ✅ 审计结论：hermes-agent 是 NousResearch 上游项目，run_agent.py 已拆出 27 个模块到 agent/ 包（memory_manager/error_classifier/prompt_builder/model_metadata/context_compressor 等），上游持续模块化中。强行拆分会与上游频繁冲突，标记为"跟随上游演进"

## P3 — 聚焦

- [x] **22. 收敛到 TaijiOS + hermes-agent 双核** — ✅ FOCUS.md 已创建。cyberpet/AIOS-Friend-Edition/足球分析/AIOS-Portable 冻结。SafeClick 经审计不是独立项目而是 core 内置 RPA 安全层，保持维护

---

## 当前进度

### 变卦推演系统（P1 #9-12 相关）

已完成多轮打磨，当前状态：

| 指标 | 值 |
|------|-----|
| 覆盖率 | 36/64 |
| 策略适配 | 4.0/5, 0个错配 |
| 通用回退 | 0/64 |
| transition条目 | ~148 |
| 总评 | 93% |

已修复的策略错配：泰、豫、晋、临、益、困、谦、丰（8个）
待修复（#9）：剥 需复查（之前审计判定为 false positive，"止损而非扩张"中扩张出现在否定语境）
