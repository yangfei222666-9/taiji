# TaijiOS 聚焦声明

> 2026-04-14 起生效

## 双核架构

| 核心 | 定位 |
| ---- | ---- |
| TaijiOS (taijios-lite + aios/) | 变卦推演 + 自学习 + Agent 生命周期 |
| hermes-agent | 通用 AI Agent 执行层（跟随 NousResearch 上游） |

## 暂停项目

以下项目进入维护冻结状态，不再投入新功能开发：

- **cyberpet** (`aios/patterns/cyberpet*.html`) — 像素桌宠，纯前端，无依赖
- **AIOS-Friend-Edition** (`aios/AIOS-Friend-Edition/`) — 旧版分发副本，与主干代码不同步
- **足球分析** (`match_analysis/`) — 比赛数据卡片，soul_api.py 已有优雅降级
- **AIOS-Portable** (`aios/AIOS-Portable/`) — 旧版便携包，同上

## 不暂停（误判澄清）

- **SafeClick** (`aios/core/safe_click.py`) — 不是独立项目，是 core 内置的 RPA 安全层，safe_hotkey/safe_type 依赖它，保持维护
