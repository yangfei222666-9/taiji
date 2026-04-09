# 足球比赛 AI 分析系统 — 技术指南

## 这是什么

一套基于真实数据的比赛赛前分析系统。输入一场比赛，输出完整的结构化资料卡 + 赔率交叉验证。

**不是预测系统，是决策支持系统** — 它把信息整理成专业分析师能直接用的格式。

---

## 系统能力

### 9 张结构化资料卡

| # | 卡片 | 内容 |
|---|------|------|
| 1 | MatchContext | 联赛、轮次、主客场、场地、裁判 |
| 2 | HomeProfile | 主队排名、积分、主客场拆分、攻防数据 |
| 3 | AwayProfile | 客队同上 |
| 4 | HomeForm | 主队近 10 场战绩、胜平负、趋势 |
| 5 | AwayForm | 客队同上 |
| 6 | HeadToHead | 近 5 次交锋记录 |
| 7 | HomeAvailability | 主队伤停名单 |
| 8 | AwayAvailability | 客队伤停名单 |
| 9 | OddsCard | 欧赔 + 亚盘 + 大小球 + 赔率交叉验证 |

### 赔率交叉验证（P2-A）

- 主源：API-Football（14 家博彩公司）
- 交叉源：The Odds API（40 家博彩公司）
- 自动计算双源赔率差值
- 输出三档一致性判断：**一致 / 轻微分歧 / 显著分歧**

### 稳定性

- 12/12 跨级别赛事压力测试通过（欧联/欧会杯/南美解放者杯/尼加拉瓜联赛）
- 不支持的联赛自动降级，不崩不报错
- 150+ 队名别名映射（五大联赛 + 欧战常客）

---

## 技术架构

```
match_analysis/
├── main.py                    # FastAPI 入口
├── config.py                  # 配置（环境变量读取）
├── models.py                  # Pydantic 数据模型（9 张卡）
├── adapters/
│   ├── base.py                # 抽象基类
│   ├── api_football.py        # 主数据源适配器
│   ├── mock_adapter.py        # Mock 数据（开发用）
│   └── the_odds_api.py        # 交叉验证源（队名模糊匹配 + 缓存）
├── services/
│   └── match_analyzer.py      # 核心分析服务
├── stress_test.py             # 自动化压力测试
├── mock_data/
│   └── sample_match.json      # Mock 数据
├── DATA_OPS.md                # 数据层运维手册
└── requirements.txt
```

### 核心设计

1. **Adapter 模式** — 抽象基类定义 6 个方法，Mock 和真实 API 可切换
2. **缺失语义区分** — API 200+空结果 = 有效空（如无伤停=全员健康），网络错误/401/超时 = 真缺失
3. **交叉源不替换主源** — The Odds API 只做增强层，拿不到不影响主流程
4. **内存缓存** — standings 1小时 TTL，odds 30分钟 TTL，按联赛批量缓存

---

## 快速开始

### 1. 安装依赖

```bash
cd match_analysis
pip install -r requirements.txt
```

### 2. 设置 API Key

```bash
# 必须（主数据源）
export API_FOOTBALL_KEY="your_key"

# 可选（交叉验证源）
export THE_ODDS_API_KEY="your_key"
```

API-Football 注册：https://www.api-football.com
The Odds API 注册：https://the-odds-api.com（免费 500 次/月）

### 3. 启动服务

```bash
python -m uvicorn match_analysis.main:app --reload
```

### 4. 使用

```bash
# 健康检查
curl http://localhost:8000/health

# Mock 数据测试
curl http://localhost:8000/analyze/mock

# 真实比赛分析（需要 fixture_id）
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"fixture_id": 1379288}'
```

### 5. 压力测试

```bash
python -m match_analysis.stress_test
```

自动拉取当日赛程，跑 12 场分析，输出 PASS/WARN/FAIL 报告。

---

## 实战输出示例

### West Ham vs Wolves（英超第 32 轮，2026-04-10）

**联赛位置**
- West Ham：18 名 / 29 分 / 7W-8D-16L / 净胜球 -21
- Wolves：20 名 / 17 分 / 3W-8D-20L / 净胜球 -30

**关键数据**
- Wolves 客场赛季 **0 胜**（15 场 0W-5D-10L，场均 0.47 球）
- 近 5 次交锋 Wolves 4 胜，但多为主场
- West Ham 两名门将同时受伤
- 赔率双源交叉验证：**一致**（max_diff 仅 0.042）

**赔率**
- 欧赔均值：主胜 1.84 / 平 3.70 / 客胜 4.18
- 亚盘主线：West Ham -0.75
- 大小球主线：2.5 球

**分析判断**
- 保级生死战，West Ham 更绝望但主场相对优势
- Wolves 客场零胜是最硬的事实
- 赔率市场高度收敛，无信息不对称信号
- 关注门将伤情对后防的影响

---

## 代码仓库

https://github.com/${GITHUB_REPO_OWNER}/aios/tree/main/match_analysis

---

## 当前阶段

| 阶段 | 状态 | 内容 |
|------|------|------|
| P1 | ✅ 封板 | 9-section 资料卡 + 真实数据 + 压力验证 |
| P2-A | ✅ 完成 | 赔率交叉验证（The Odds API） |
| P2-B | 待启动 | xG 增强（Understat） |
| P3 | 规划中 | 情报采集 + 热度推理 + 临场修正 |

---

## 技术栈

- Python 3.12 + FastAPI + Pydantic v2
- httpx（异步 HTTP）
- API-Football（主数据源，Pro 计划）
- The Odds API（交叉验证源，免费计划）
- difflib（队名模糊匹配）
- 150+ 队名别名表（五大联赛 + 欧战）
