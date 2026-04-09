# Match Analysis 数据层运维手册

## 一、数据源架构

### 主数据源：API-Football (api-sports.io)
- 免费计划：100 次请求/天
- Pro 计划：$9.99/月，7500 次/天
- 覆盖：900+ 联赛，含赛程/积分榜/H2H/伤停/赔率

### 交叉验证源：The Odds API (the-odds-api.com)
- 免费计划：500 次请求/月
- 覆盖：五大联赛 + 欧冠/欧联/欧会杯
- 用途：赔率交叉验证，不替换主源
- 匹配方式：队名模糊匹配 + 日期（无 fixture_id 关联）

### 待接入源
- Understat — 免费 xG（仅6大联赛，需爬虫）
- football-data.org — 免费层，赛程/积分榜备份

## 二、9 个 Section 的空值规则

| Section | 空结果是否有效 | 说明 |
|---------|--------------|------|
| match_context | 否 | fixture_id 查不到 = 真缺失 |
| home_profile | 视情况 | 积分榜无该队 = 缺失（可能联赛不支持） |
| away_profile | 视情况 | 同上 |
| home_form | 是 | 新队/赛季初可能无已完赛比赛 |
| away_form | 是 | 同上 |
| head_to_head | 是 | 两队从未交手 = 有效的0 |
| home_availability | 是 | 0伤停 = 全员健康，不是缺失 |
| away_availability | 是 | 同上 |
| odds | 是 | 小联赛可能无赔率数据 |

核心原则：API 返回 200 + response=[] 是"有效的空"，只有网络错误/认证失败/超时才是"真缺失"。

## 三、赔率交叉验证（P2-A）

### 工作原理

1. 主源（API-Football）提供 match_winner / asian_handicap / over_under
2. 交叉源（The Odds API）提供 h2h（1X2）赔率
3. 系统计算双源平均赔率差值，输出一致性判断

### 一致性判断标准

| agreement_level | max_diff 阈值 | 含义 |
|----------------|--------------|------|
| 一致 | < 0.15 | 双源赔率高度吻合 |
| 轻微分歧 | < 0.40 | 存在差异但在正常范围 |
| 显著分歧 | >= 0.40 | 需要关注，可能有信息不对称 |

### 交叉源字段来源

OddsCard 中的字段来源：

| 字段 | 来源 | 缺失是否正常 |
|------|------|-------------|
| match_winner | API-Football | 小联赛可能为空 |
| asian_handicap | API-Football | 部分联赛无亚盘 |
| over_under | API-Football | 部分联赛无大小球 |
| cross_validation | The Odds API | 无 key / 不支持联赛 / 已结赛 = null |
| cross_validation.cross_bookmakers | The Odds API | 正常时有数十家博彩公司 |
| cross_validation.agreement_level | 计算得出 | 需双源均有数据 |

### 交叉验证降级场景

cross_validation 为 null 的正常情况：
- `THE_ODDS_API_KEY` 未设置 — 跳过交叉验证
- 联赛不在 SPORT_KEY_MAP 中 — `data_missing: true, reason: "league X not supported"`
- 已结束的比赛 — The Odds API 只提供未开赛比赛的赔率
- 队名匹配失败 — `data_missing: true, reason: "no matching fixture"`
- API 请求失败 — `data_missing: true, reason: "request failed: ..."`

以上所有情况不影响主源（API-Football）的 9 个 section 正常返回。

### 队名匹配

两源使用不同队名体系（如 API-Football: "Wolves" vs The Odds API: "Wolverhampton Wanderers"）。
系统通过以下机制匹配：

1. **别名归一化** — 150+ 条常见变体映射（覆盖五大联赛 + 欧战常客）
2. **模糊匹配** — SequenceMatcher 相似度 >= 0.5
3. **子串匹配** — 短名包含在长名中则保底 0.75
4. **日期窗口** — ±1 天容差

## 四、data_missing 触发条件

标记 `data_missing=True` 的情况：
- HTTP 401 — API Key 无效或过期
- HTTP 429 — 超出配额限制
- HTTP 5xx — 上游服务故障
- 超时 — 15秒无响应
- match_context 查不到 fixture — fixture_id 错误

不标记 `data_missing` 的情况：
- API 200 + response=[] — 有效空结果
- 伤停列表为空 — 全员健康
- H2H 为空 — 从未交手
- RecentForm 为空 — 新队/赛季初

## 五、常见 missing_reason 示例

```
# 主源
request failed: 401 Unauthorized
request failed: 429 Too Many Requests
request failed: timed out
fixture 9999999 not found
standings not found for team 42 in league 999

# 交叉源
THE_ODDS_API_KEY not set
league 253 not supported by The Odds API
no matching fixture for X vs Y in soccer_epl
request failed: 401 Unauthorized
```

## 六、配额管理

### 主源 API-Football

一场完整分析消耗的 API 调用：
- fixtures (match_context): 1
- standings (home_profile): 1
- standings (away_profile): 0（同联赛复用缓存）
- fixtures (home_form): 1
- fixtures (away_form): 1
- fixtures/headtohead: 1
- injuries (home): 1
- injuries (away): 1
- odds: 1
- 合计：约 8 次/场

缓存：
- standings — 1 小时内存缓存（按 league_id:season）

### 交叉源 The Odds API

- 按联赛批量获取（一次调用返回全联赛所有赛事赔率）
- 30 分钟内存缓存（按 sport_key）
- 同联赛多场分析只消耗 1 次调用
- 500 次/月，正常使用足够

## 七、已验证的稳定性

### P1 压力测试（2026-04-09）

12/12 PASS，跨级别赛事验证：
- 欧联杯（Bologna vs Aston Villa, Porto vs Nottingham Forest, Freiburg vs Celta Vigo）
- 欧会杯（Crystal Palace vs Fiorentina, Mainz vs Strasbourg, Shakhtar vs AZ）
- 南美解放者杯（Independiente Medellin vs Estudiantes）
- 南美杯（A. Italiano vs Olimpia）
- 尼加拉瓜联赛（Matagalpa vs Diriangén）
- 厄瓜多尔联赛、巴西联赛

关键指标：91 次 API 调用，5/12 standings 缓存命中，平均 4.5s

### P2-A 交叉验证（2026-04-09）

West Ham vs Wolves（EPL）：
- 别名映射成功（Wolves → Wolverhampton Wanderers）
- 40 家博彩公司交叉赔率
- agreement_level: 一致，max_diff: 0.042

## 八、后续数据层扩展路线

- P2-B：Understat xG — 免费补充源，增强状态判断深度
- P3：非结构化情报 / 天气 / 临场首发修正
