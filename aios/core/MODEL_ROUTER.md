# 智能模型路由系统使用指南

## 功能

自动选择最合适的模型处理任务：
- **简单任务** → Ollama 本地模型（免费、快速）
- **复杂任务** → Claude API（效果好）

## 快速开始

### 1. Python API

```python
from aios.core.model_router import route_model

# 自动路由
result = route_model(
    task_type="greeting",
    prompt="你好，介绍一下自己"
)

print(f"使用模型: {result['model']}")
print(f"回复: {result['response']}")
print(f"成本: ${result['cost']}")
```

### 2. 强制使用指定模型

```python
# 强制使用本地模型
result = route_model(
    task_type="greeting",
    prompt="你好",
    force_model="ollama"
)

# 强制使用 Claude
result = route_model(
    task_type="reasoning",
    prompt="分析这个问题...",
    force_model="claude"
)
```

## 任务类型分类

### 简单任务（优先本地）
- `greeting` - 打招呼
- `translation` - 简单翻译
- `summarize_short` - 短文本摘要
- `classification` - 文本分类
- `keyword_extraction` - 关键词提取
- `simple_qa` - 简单问答

**策略**：优先用 Ollama，失败时降级到 Claude

### 中等任务（尝试本地）
- `code_completion` - 代码补全
- `text_generation` - 文本生成
- `data_analysis` - 数据分析
- `summarize_long` - 长文本摘要

**策略**：尝试 Ollama，质量不够时降级到 Claude

### 复杂任务（直接 Claude）
- `reasoning` - 复杂推理
- `planning` - 任务规划
- `code_review` - 代码审查
- `creative_writing` - 创意写作
- `decision_making` - 决策支持

**策略**：直接使用 Claude

## 返回值

```python
{
    "model": "ollama" | "claude",  # 实际使用的模型
    "response": str,                # 模型回复
    "success": bool,                # 是否成功
    "fallback": bool,               # 是否使用了降级
    "cost": float                   # 成本（美元）
}
```

## 成本对比

### 使用本地模型
```python
result = route_model("greeting", "你好")
# cost: $0.00
```

### 使用 Claude
```python
result = route_model("reasoning", "分析...")
# cost: ~$0.01
```

### 自动路由（混合使用）
假设每天：
- 10 次简单任务 → Ollama → $0.00
- 5 次中等任务 → Ollama → $0.00
- 3 次复杂任务 → Claude → $0.03

**每天成本：$0.03（vs 全用 Claude $0.18）**
**节约：83%**

## 集成到 AIOS

### 在 Pipeline 中使用

```python
# aios/pipeline.py
from core.model_router import route_model

def analyze_with_ai(text: str):
    result = route_model(
        task_type="data_analysis",
        prompt=f"分析以下数据：{text}"
    )
    return result['response']
```

### 在 Alerts 中使用

```python
# aios/scripts/alerts.py
from core.model_router import route_model

def generate_alert_summary(alerts: list):
    prompt = f"总结以下告警：{alerts}"
    result = route_model(
        task_type="summarize_short",
        prompt=prompt
    )
    return result['response']
```

## 配置

### 修改任务分类

编辑 `model_router.py` 中的 `TASK_COMPLEXITY` 字典：

```python
TASK_COMPLEXITY = {
    "simple": [
        "greeting",
        "your_custom_task",  # 添加自定义任务
    ],
    # ...
}
```

### 修改模型选择

```python
# 默认本地模型
DEFAULT_LOCAL_MODEL = "qwen2.5:3b"

# 可以改成其他模型
DEFAULT_LOCAL_MODEL = "llama3.2:3b"
```

## 监控和统计

### 查看使用统计

```python
from aios.core.model_router import get_model_stats

stats = get_model_stats()
print(f"Ollama 调用: {stats['ollama_calls']}")
print(f"Claude 调用: {stats['claude_calls']}")
print(f"总成本: ${stats['total_cost']}")
print(f"节约成本: ${stats['cost_saved']}")
```

## 最佳实践

### 1. 优先本地
对于日常简单任务，优先使用本地模型：
```python
result = route_model("simple_qa", "今天天气怎么样？")
```

### 2. 重要任务用 Claude
对于重要决策，强制使用 Claude：
```python
result = route_model(
    "decision_making",
    "是否应该投资这个项目？",
    force_model="claude"
)
```

### 3. 混合使用
让系统自动选择，平衡成本和效果：
```python
result = route_model("code_completion", "补全这段代码...")
# 系统会先尝试本地，不行再用 Claude
```

## 故障处理

### Ollama 不可用
系统会自动降级到 Claude，不影响使用。

### Claude API 失败
需要手动处理，或者实现重试逻辑。

### 本地模型效果不好
可以调整任务分类，把该任务移到 "complex" 类别。

## 下一步

- [ ] 实现 Claude API 调用（当前是占位）
- [ ] 添加使用统计日志
- [ ] 实现质量评估（自动判断本地模型效果）
- [ ] 支持更多本地模型
- [ ] 添加成本预算控制

---

**当前状态**：✅ 基础路由可用  
**Ollama 状态**：✅ 已安装并运行  
**模型**：Qwen2.5 3B（1.9 GB）
