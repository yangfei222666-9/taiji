<p align="center">
  <img src="docs/hud_screenshot.png" alt="TaijiOS HUD — Five Engine Real-time Monitor" width="700" />
</p>

<p align="center">
  <img src="docs/logo.png" alt="TaijiOS" width="120" />
</p>

<h1 align="center">TaijiOS 太极OS</h1>

<p align="center">
  融合易经哲学的自学型 AI 操作系统<br>
  <em>A self-learning AI operating system inspired by I Ching philosophy</em>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License" /></a>
  <a href="https://github.com/yangfei222666-9/taiji/stargazers"><img src="https://img.shields.io/github/stars/yangfei222666-9/taiji?style=social" alt="Stars" /></a>
  <a href="https://github.com/yangfei222666-9/taiji/issues"><img src="https://img.shields.io/github/issues/yangfei222666-9/taiji" alt="Issues" /></a>
</p>

<p align="center">
  <a href="#quick-start-快速开始">快速开始</a> · <a href="#why-i-ching-为什么用易经">易经状态机</a> · <a href="#architecture-架构">架构</a> · <a href="#features-核心能力">能力</a> · <a href="#modules-模块">模块</a>
</p>

---

## Public entry 公开入口

This is the main TaijiOS repository.

- Live demo: [taijios-hud.netlify.app](https://taijios-hud.netlify.app)
- Legacy prototype: [TaijiOS](https://github.com/yangfei222666-9/TaijiOS)
- Lite prototype / example pack: [TaijiOS-Lite](https://github.com/yangfei222666-9/TaijiOS-Lite)
- Standalone reliability spin-off: [self-improving-loop](https://github.com/yangfei222666-9/self-improving-loop)
- Standalone reasoning skill: [zhuge-skill](https://github.com/yangfei222666-9/zhuge-skill)

If you are new here, start with the live HUD demo, then read this repository. The other repos are either spin-offs or historical prototypes.

---

This is the canonical TaijiOS engineering entrypoint. Start by running the minimal local demo below; the larger I Ching / Ising architecture is documented after the runnable path.

---

## Quick Start 快速开始

```bash
# 克隆主仓
git clone https://github.com/yangfei222666-9/taiji.git
cd taiji

# 安装依赖
pip install -e .

# 运行最小示例（无需 API Key、无需 GPU）
python examples/quickstart_minimal.py
```

你会看到：

```text
--- Task: quickstart-001 ---
  Status: succeeded
  Attempts: 2
  Final score: 0.9
  Self-healed: YES

  Results: 3/3 succeeded
  Self-healed: 3/3
  Events logged: 18
```

发生了什么：3 个任务进入系统 → 首次验证失败(0.35) → 自动注入修复指导 → 重试成功(0.90) → 生成证据链。

这就是太极OS的核心循环：**任务 → 验证 → 失败 → 指导 → 重试 → 交付 → 证据**。

## Why I Ching? 为什么用易经

太极OS 的五引擎不是随便取的名字——每个引擎对应一个卦象，卦象定义了它的**职责边界**和**行为哲学**。

| 引擎 | 卦象 | 卦义 | 系统职责 |
|------|------|------|----------|
| 情势引擎 | ☰ 乾卦 | 天行健，自强不息 | 6维态势感知（时机/资源/主动/位置/关系/能量），张力检测与干预决策 |
| 震卦引擎 | ⚡ 震卦 | 震来虩虩，笑言哑哑 | 故障恢复：爻位逐级升级，熔断器三级保护，惊后自愈 |
| 师卦引擎 | 🏴 师卦 | 地中有水，师 | 集群调度：小队编组、阵型切换、任务分配，治众如治寡 |
| 人格引擎 | 🎭 随卦 | 泽中有雷，随 | Persona 热切换：根据任务匹配最佳人格，随时而动 |
| 颐卦引擎 | 📚 颐卦 | 山下有雷，颐 | 经验学习：高权重经验沉淀、命中率追踪、知识消化，慎言语节饮食 |

**卦象不是装饰，是约束。** 震卦引擎只管恢复不管调度，师卦引擎只管集群不管学习——卦义划定了每个引擎"能做什么"和"不该做什么"的边界。系统运行时，后端实时计算六爻卦象，将18维系统指标映射为卦辞和爻变，HUD 前端只做展示。

---

## Architecture 架构

```mermaid
graph TB
    subgraph Core["Core 核心层"]
        EB[EventBus 事件总线]
        SC[Scheduler 调度器]
        RE[Reactor 反应器]
        MEM[Memory 记忆]
        CB[CircuitBreaker 熔断器]
    end

    subgraph Gateway["LLM Gateway 统一网关"]
        AUTH[Auth 认证]
        POLICY[Policy 策略]
        ROUTE[Router 路由]
        FAIL[Failover 故障转移]
        AUDIT[Audit 审计]
    end

    subgraph Agent["Agent System 智能体框架"]
        TQ[TaskQueue 任务队列]
        EX[Executor 执行器]
        LC[Lifecycle 生命周期]
        EXP[Experience 经验引擎]
        META[MetaAgent 元智能体]
    end

    subgraph SafeClick["Safe Click 受控点击"]
        G1[窗口绑定]
        G2[高风险区域禁点]
        G3[目标白名单]
        G4[OCR置信度]
    end

    subgraph Learning["Self-Improving 自进化"]
        FB[Feedback 反馈环]
        EVO[Evolution 进化]
        PL[PolicyLearner 策略学习]
        RB[Rollback 安全回滚]
    end

    subgraph GitHub["GitHub Learning 学习管道"]
        DISC[Discover 发现]
        ANA[Analyze 分析]
        DIG[Digest 提炼]
        GATE[Gate 人工门控]
        SOL[Solidify 固化]
    end

    Core --> Gateway
    Core --> Agent
    Agent --> SafeClick
    Agent --> Learning
    Learning --> GitHub
```

## Features 核心能力

| 能力 | 说明 | Status |
|------|------|--------|
| Event-Driven Core 事件驱动核心 | EventBus + Scheduler + Reactor，所有行为由事件触发 | ✅ |
| LLM Gateway 统一网关 | 认证、限流、多 Provider 故障转移、审计，12/12 极端场景通过 | ✅ |
| Agent System 智能体框架 | 任务队列（原子状态转换）、生命周期管理、经验收割 | ✅ |
| MetaAgent 元智能体 | 自动检测系统缺口 → 设计新 Agent → 沙箱测试 → 动态注册 | ✅ |
| Self-Improving Loop 自进化环 | 反馈环 + 进化评分 + 策略学习 + 安全回滚 | ✅ |
| Circuit Breaker 熔断器 | 故障隔离，防止级联崩溃 | ✅ |
| Safe Click 受控点击 | 四闸门安全点击执行器（窗口绑定 + 区域禁点 + 白名单 + OCR 置信度） | ✅ |
| GitHub Learning 学习管道 | 从开源项目学习：发现 → 分析 → 提炼 → 人工门控 → 固化 | ✅ |
| Match Analysis 赔率交叉验证 | 多数据源比赛分析 + 赔率交叉验证框架 | ✅ |
| Pattern Recognition 模式识别 | 从运行数据中识别可优化模式 | ✅ |
| Ising Heartbeat 物理心跳引擎 | 统计物理 Ising 模型 + 六爻映射，追踪系统状态动力学，346 次心跳实验验证 | ✅ |
| Multi-LLM Router 多模型路由 | DeepSeek / Gemini / GPT / Claude 四路调用 + 自动降级 + 交叉验证 | ✅ |
| FastAPI Server REST 接口 | `/api/chat` `/api/hexagram` `/api/cognitive_map` 等，TaijiBot 接入 | ✅ |

> Roadmap items are tracked below instead of being mixed into the completed feature table.

## Ising Heartbeat 物理心跳引擎

> 用物理学中的 Ising 模型，给 AI 操作系统装一颗会演化的"心脏"。

TaijiOS 将 6 个系统维度映射为 6 个量子自旋（σ = ±1），用 Ising 模型追踪系统状态动力学：

| 爻位 | 系统维度 | σ=+1（阳）| σ=-1（阴）|
|------|---------|----------|----------|
| 初爻 | infra（基础设施）| 稳定 | 不稳定 |
| 二爻 | exec（执行层）| 高效 | 滞后 |
| 三爻 | learn（学习层）| 活跃 | 停滞 |
| 四爻 | route（路由层）| 准确 | 混乱 |
| 五爻 | collab（协作层）| 顺畅 | 阻塞 |
| 上爻 | govern（治理层）| 收敛 | 失控 |

6 个自旋的组合 = 64 种可能 = 正好对应易经 64 卦。

**Hebbian 学习**使耦合矩阵 J 随时间自适应：
```
ΔJᵢⱼ = η · reward · σᵢ · (σⱼ - σⱼ_prev)
```

**18.8 小时 / 346 次心跳实验结论：**
- 系统在第 37 tick 经历一次干净的相变（ΔH = +0.30），之后 99% 时间锁定新稳态
- 外场自适应自发学出"抑刚强流通"格局，与易经坤德高度吻合
- 易经"应"关系（初↔四等）在 Hebbian 学习中**未**自发增强——物理邻近性比功能对应性更强

```bash
# 启动心跳引擎
cd aios/agent_system
python ising_heartbeat.py --loop --interval 60

# 查看实时状态
python ising_heartbeat.py --status
```

## Tech Stack 技术栈

```
Python 3.12 · FastAPI · SQLite · pyautogui · edge-tts · Whisper
```

### 启动 LLM Gateway

```bash
export TAIJIOS_GATEWAY_ENABLED=1
python -m aios.gateway --port 9200
```

### 启动 GitHub 学习管道

```bash
export GITHUB_TOKEN=your-github-token
python -m github_learning discover --limit 10
python -m github_learning analyze
python -m github_learning digest
python -m github_learning gate list
python -m github_learning gate approve <id>
python -m github_learning solidify
```

## Modules 模块

```
TaijiOS/
├── aios/
│   ├── core/              # 事件引擎、调度器、反应器、记忆、熔断器、Safe Click
│   ├── gateway/           # LLM 统一网关（认证、路由、故障转移、审计）
│   ├── agent_system/      # 智能体框架（任务队列、执行器、经验引擎、元智能体）
│   └── storage/           # SQLite 存储层
├── self_improving_loop/   # 自进化环（反馈、进化、策略学习、回滚）
├── github_learning/       # GitHub 学习管道（发现→分析→提炼→门控→固化）
├── match_analysis/        # 赔率交叉验证框架
├── rpa_vision/            # Safe Click 受控点击验证器
├── skill_auto_creation/   # 技能自动创建（检测→草案→验证→反馈→注册）
├── examples/              # 快速开始示例
├── tests/                 # 测试套件
└── docs/                  # 架构文档
```

| Module | Description | 说明 |
|--------|-------------|------|
| `aios/core/` | Event engine, scheduler, reactor, memory, circuit breaker, model router, Safe Click | 事件引擎、调度器、反应器、记忆、熔断器、模型路由、安全点击 |
| `aios/gateway/` | Unified LLM Gateway — auth, rate limiting, provider failover, audit, streaming | 统一 LLM 网关 — 认证、限流、故障转移、审计、流式传输 |
| `aios/agent_system/` | Task queue, agent lifecycle, experience harvesting, meta-agent, evolution, Ising heartbeat | 任务队列、智能体生命周期、经验收割、元智能体、进化、Ising 心跳引擎 |
| `taijios-lite/` | Lightweight server — FastAPI `/api/chat`, multi-LLM router, Feishu/Telegram bot | 轻量服务 — FastAPI 接口、多模型路由、飞书/Telegram Bot |
| `self_improving_loop/` | Safe self-modification with rollback and threshold gates | 安全自修改 + 回滚 + 阈值门控 |
| `github_learning/` | Learn from GitHub: discover, analyze, digest, gate, solidify | 从 GitHub 学习：发现、分析、提炼、门控、固化 |
| `match_analysis/` | Multi-source match analysis with odds cross-validation | 多数据源比赛分析 + 赔率交叉验证 |
| `rpa_vision/` | Safe Click validator — 4-gate controlled click executor | 安全点击验证器 — 四闸门受控点击执行器 |
| `skill_auto_creation/` | Auto-detect patterns → draft skills → 3-layer validation | 自动检测模式 → 生成技能草案 → 三层验证 |

## Configuration 配置

所有敏感信息通过环境变量配置（参考 `taijios-lite/.env.example`）：

```bash
# ── AI 模型（选填，至少配一个）──────────────────────
# DeepSeek（推荐，便宜）
DEEPSEEK_API_KEY=sk-...

# Gemini
GEMINI_API_KEY=AIza...

# Claude（官方 Anthropic 保底）
ANTHROPIC_API_KEY=sk-ant-...

# Claude 中转站（可选，比官方便宜）
CLAUDE_RELAY_KEY=sk-...
CLAUDE_RELAY_BASE=https://your-relay.com/v1

# ── 飞书 Bot（可选）──────────────────────────────
FEISHU_APP_ID=cli_...
FEISHU_APP_SECRET=...

# ── LLM Gateway ──────────────────────────────────
TAIJIOS_GATEWAY_ENABLED=1
TAIJIOS_API_TOKEN=your-token

# ── GitHub Learning ───────────────────────────────
GITHUB_TOKEN=ghp_...
```

## Design Principles 设计原则

| Principle | 原则 | Description |
|-----------|------|-------------|
| Self-healing | 自愈优先 | 验证失败自动重试，注入修复指导 |
| Experience-driven | 经验驱动 | 每次执行产生经验数据，改进未来运行 |
| Gate everything | 门控一切 | 外部机制经人工审核后才进入主线 |
| Evidence-first | 证据先行 | 每个决策、失败、恢复都有结构化证据 |
| Graceful degradation | 优雅降级 | 组件降级到兜底方案，永不崩溃系统 |
| Default deny | 默认拒绝 | Safe Click 四闸门全过才允许执行 |

## Live Demo 在线演示

> **不想跑代码？直接看效果：**

| Demo | 说明 |
|------|------|
| [HUD 五引擎监控面板](https://taijios-hud.netlify.app) | CRT 像素风实时仪表盘，模拟模式可直接体验 |
| [CyberPet 赛博宠物](https://taijios-cyberpet.netlify.app) | 太极OS 内置的 AI 像素宠物，双击 HTML 也能跑 |

> Netlify 托管，纯前端，零依赖，无需安装。HUD 连接后端后自动从 SIM 切换为 LIVE 真实数据。

## Screenshots 截图

<p align="center">
  <img src="docs/hud_screenshot.png" alt="TaijiOS HUD — CRT pixel五引擎监控" width="700" />
  <br><em>HUD 五引擎实时监控面板 — 情势/震卦/师卦/人格/颐卦 + 系统层</em>
</p>

<p align="center">
  <img src="docs/dashboard_demo.png" alt="TaijiOS Dashboard" width="400" />
  <br><em>Dashboard 任务执行流：提交 → 验证 → 卦象决策 → 交付</em>
</p>

## Private Modules 私有模块

以下模块由合作伙伴提供，未包含在开源版本中：

| 模块 | 说明 | 状态 |
|------|------|------|
| 神针引擎 | 高精度决策引擎 | 🔒 私有 |
| EchoCore 智驱系统 | 智能驱动核心 | 🔒 私有 |

相关接口已预留抽象基类，开发者可自行实现替代方案。

开源版可独立完整运行；私有模块只用于特定部署的性能增强，不是运行主流程的必需依赖。

## Roadmap 路线图

| Item | Status |
|------|--------|
| Skill Auto-Creation 技能自动创建 | 检测模块已完成；草案生成和三层验证（语法/沙箱/回归）仍在推进 |

## Background 背景

TaijiOS was built through multi-AI collaboration. That origin explains the execution style, but it is not the product claim. The claim is the runnable evidence chain above.

## Contributing 贡献

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT License](LICENSE)

---

<p align="center">
  <strong>太极生两仪，两仪生四象，四象生万物。</strong><br>
  <em>From Taiji comes Yin and Yang; from Yin and Yang come all things.</em>
</p>
