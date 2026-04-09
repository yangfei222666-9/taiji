# Match Analysis MVP

比赛分析资料卡系统 — 输入一场比赛 fixture_id，输出 8 个 section 的结构化资料卡。

当前状态：真实数据链路已跑通，API-Football 5 个方法全部实现，3 场欧战验证通过。

## 快速启动

### 1. 安装依赖

```bash
cd g:\taijios_full_workspace
pip install -r match_analysis/requirements.txt
```

### 2. 设置环境变量（必须）

```bash
export API_FOOTBALL_KEY="你的key"
```

Windows PowerShell:
```powershell
$env:API_FOOTBALL_KEY="你的key"
```

没有 Key？去 https://www.api-football.com/ 注册，免费计划 100 次/天。

如果只想用 mock 数据：
```bash
export DATA_SOURCE=mock
```

### 3. 启动服务

```bash
python -m uvicorn match_analysis.main:app --reload --port 8100
```

### 4. 访问

- API 文档：`http://localhost:8100/docs`
- 健康检查：`GET /health`
- Mock 资料卡：`GET /analyze/mock`
- 缺失门禁测试：`GET /analyze/mock-partial`
- 真实分析：`POST /analyze` body: `{"fixture_id": 1535335}`

## 数据覆盖（8 个 Section）

| Section | 字段 | 数据源 | 状态 |
|---------|------|--------|------|
| match_context | 联赛/赛制/主客场/日期/裁判 | API-Football | 已实现 |
| home_profile | 排名/积分/主客场攻防统计 | API-Football standings | 已实现 |
| away_profile | 同上 | 同上 | 已实现 |
| home_form | 近10场战绩/趋势 | API-Football fixtures | 已实现 |
| away_form | 同上 | 同上 | 已实现 |
| head_to_head | 历史交锋 | API-Football h2h | 已实现 |
| home_availability | 伤停/停赛 | API-Football injuries | 已实现 |
| away_availability | 同上 | 同上 | 已实现 |

## 缺失治理

系统区分"有效空结果"和"真正缺失"：
- API 200 + 空列表 = 有效（如无伤停=全员健康，无交锋=从未交手）
- 网络错误/401/429/超时 = 缺失，标记 `data_missing=True` + `missing_reason`

详见 [DATA_OPS.md](DATA_OPS.md)。

## 后续计划

- [x] API-Football 真实数据接入
- [x] 缺失门禁机制
- [x] 空结果语义修复
- [x] 运算符正确性修复
- [ ] 盘口/赔率第 7 张卡
- [ ] standings 缓存层
- [ ] 热度/机构意图推理
- [ ] 非结构化情报
- [ ] 临场首发修正
