"""
AIOS Tools Module - 工具管理系统

实现标准 Agent 的 Tool Use 能力：
1. 工具注册表 - 统一管理所有工具
2. 自动工具选择 - 根据任务自动选择最合适的工具
3. 统一执行接口 - 标准化的工具调用方式
4. 观察反馈 - 工具执行结果的标准化反馈

Author: 小九 + 珊瑚海
Date: 2026-02-26
"""

import json
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any
    observation: str  # 人类可读的观察结果
    error: Optional[str] = None
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class Tool:
    """工具基类"""
    
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        keywords: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.func = func
        self.keywords = keywords or self._extract_keywords(description)
        self.usage_count = 0
        self.success_count = 0
        self.total_time = 0.0
    
    def _extract_keywords(self, description: str) -> List[str]:
        """从描述中提取关键词"""
        return description.split()
    
    def matches(self, task: str) -> bool:
        """判断工具是否匹配任务"""
        task_lower = task.lower()
        return any(kw.lower() in task_lower for kw in self.keywords)
    
    def execute(self, **params) -> ToolResult:
        """执行工具"""
        start_time = time.time()
        self.usage_count += 1
        
        try:
            # 执行工具函数
            output = self.func(**params)
            
            # 记录成功
            self.success_count += 1
            execution_time = time.time() - start_time
            self.total_time += execution_time
            
            return ToolResult(
                success=True,
                output=output,
                observation=f"工具 {self.name} 执行成功",
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            self.total_time += execution_time
            
            return ToolResult(
                success=False,
                output=None,
                observation=f"工具 {self.name} 执行失败",
                error=str(e),
                execution_time=execution_time
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        return {
            "name": self.name,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / self.usage_count if self.usage_count > 0 else 0,
            "avg_time": self.total_time / self.usage_count if self.usage_count > 0 else 0
        }


class ToolManager:
    """工具管理器"""
    
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or Path.cwd()
        self.tools: Dict[str, Tool] = {}
        self.tool_history: List[Dict] = []
        
        # 注册默认工具
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 1. Web 搜索
        self.register(Tool(
            name="web_search",
            description="搜索 查找 Google 互联网 网页",
            func=self._web_search,
            keywords=["搜索", "查找", "Google", "网页"]
        ))
        
        # 2. 计算器
        self.register(Tool(
            name="calculator",
            description="计算 加减乘除 数学 预算",
            func=self._calculator,
            keywords=["计算", "加", "减", "乘", "除", "预算"]
        ))
        
        # 3. 文件读取
        self.register(Tool(
            name="file_reader",
            description="读取 打开 查看 文件 内容",
            func=self._file_reader,
            keywords=["读取", "打开", "查看"]  # 移除"文件"避免冲突
        ))
        
        # 4. 文件写入
        self.register(Tool(
            name="file_writer",
            description="写入 保存 生成 创建 文件 PDF 文档",
            func=self._file_writer,
            keywords=["写入", "保存", "生成", "创建", "PDF", "文档"]
        ))
        
        # 5. 代码执行
        self.register(Tool(
            name="code_executor",
            description="执行 运行 代码 Python",
            func=self._code_executor,
            keywords=["执行", "运行", "代码", "Python"]
        ))
    
    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        print(f"✅ 注册工具: {tool.name}")
    
    def select(self, task: str) -> Optional[Tool]:
        """根据任务自动选择工具"""
        # 1. 找出所有匹配的工具及其匹配分数
        matched_tools = []
        for tool in self.tools.values():
            if tool.matches(task):
                # 计算匹配分数（匹配的关键词数量）
                score = sum(1 for kw in tool.keywords if kw.lower() in task.lower())
                matched_tools.append((tool, score))
        
        # 2. 如果没有匹配，返回 None
        if not matched_tools:
            return None
        
        # 3. 按匹配分数排序（分数高的优先，分数相同则按成功率）
        matched_tools.sort(
            key=lambda x: (x[1], x[0].success_count / max(x[0].usage_count, 1)),
            reverse=True
        )
        
        return matched_tools[0][0]
    
    def execute(self, tool_name: str, **params) -> ToolResult:
        """执行工具"""
        tool = self.tools.get(tool_name)
        
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                observation=f"工具 {tool_name} 不存在",
                error="Tool not found"
            )
        
        # 执行工具
        result = tool.execute(**params)
        
        # 记录历史
        self.tool_history.append({
            "tool_name": tool_name,
            "params": params,
            "result": result.to_dict(),
            "timestamp": time.time()
        })
        
        return result
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具信息"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "keywords": tool.keywords,
                "stats": tool.get_stats()
            }
            for tool in self.tools.values()
        ]
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        return {
            "total_tools": len(self.tools),
            "total_executions": sum(t.usage_count for t in self.tools.values()),
            "total_successes": sum(t.success_count for t in self.tools.values()),
            "tools": [tool.get_stats() for tool in self.tools.values()]
        }
    
    # ==================== 默认工具实现 ====================
    
    def _web_search(self, query: str) -> str:
        """Web 搜索（模拟）"""
        return f"搜索结果: {query}（模拟数据）"
    
    def _calculator(self, expression: str) -> float:
        """计算器"""
        try:
            return eval(expression)
        except Exception as e:
            raise ValueError(f"计算错误: {e}")
    
    def _file_reader(self, file_path: str) -> str:
        """文件读取"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        return path.read_text(encoding="utf-8")
    
    def _file_writer(self, file_path: str, content: str) -> str:
        """文件写入"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"文件已保存: {file_path}"
    
    def _code_executor(self, code: str) -> str:
        """代码执行（沙盒）"""
        # 简单实现：只支持安全的表达式
        try:
            result = eval(code, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            raise RuntimeError(f"代码执行错误: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建工具管理器
    manager = ToolManager()
    
    print("\n=== 工具列表 ===")
    for tool_info in manager.get_all_tools():
        print(f"- {tool_info['name']}: {tool_info['description']}")
    
    print("\n=== 测试工具选择 ===")
    tasks = [
        "搜索2024年AI Agent市场报告",
        "计算 1+2+3+4+5",
        "读取 README.md 文件",
        "生成一个 PDF 报告"
    ]
    
    for task in tasks:
        tool = manager.select(task)
        if tool:
            print(f"任务: {task}")
            print(f"  → 选择工具: {tool.name}")
        else:
            print(f"任务: {task}")
            print(f"  → 没有匹配的工具")
    
    print("\n=== 测试工具执行 ===")
    
    # 1. 计算器
    result = manager.execute("calculator", expression="1+2+3+4+5")
    print(f"计算器: {result.output} ({result.observation})")
    
    # 2. 文件写入
    result = manager.execute("file_writer", 
                            file_path="test_output.txt", 
                            content="Hello, AIOS!")
    print(f"文件写入: {result.output} ({result.observation})")
    
    # 3. 文件读取
    result = manager.execute("file_reader", file_path="test_output.txt")
    print(f"文件读取: {result.output} ({result.observation})")
    
    print("\n=== 工具统计 ===")
    stats = manager.get_tool_stats()
    print(f"总工具数: {stats['total_tools']}")
    print(f"总执行次数: {stats['total_executions']}")
    print(f"总成功次数: {stats['total_successes']}")
    print("\n各工具统计:")
    for tool_stat in stats['tools']:
        if tool_stat['usage_count'] > 0:
            print(f"  {tool_stat['name']}: "
                  f"{tool_stat['usage_count']} 次, "
                  f"成功率 {tool_stat['success_rate']:.1%}, "
                  f"平均耗时 {tool_stat['avg_time']:.3f}s")
