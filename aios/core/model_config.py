"""
AIOS Model Configuration - 模型配置和选择

根据任务类型自动选择最优模型：
- Planning: Claude Opus（强推理）
- Memory: DeepSeek-R1（性价比）
- Vision: Gemini 2.0（多模态）
- Default: Claude Sonnet（平衡）

Author: 小九 + 珊瑚海
Date: 2026-02-26
"""

from typing import Dict, Any


class ModelConfig:
    """模型配置"""
    
    # 模型映射
    MODELS = {
        "planning": {
            "model": "ollama/llama3.2:latest",
            "temperature": 0,  # 降低随机性，提高稳定性
            "max_tokens": 2000,
            "reason": "最强推理能力，适合复杂任务拆解"
        },
        "memory": {
            "model": "ollama/llama3.2:latest",
            "temperature": 0,
            "max_tokens": 1000,
            "reason": "稳定快速，适合记忆检索与整理"
        },
        "vision": {
            "model": "ollama/llama3.2:latest",
            "temperature": 0.3,
            "max_tokens": 1500,
            "reason": "多模态支持，适合图像理解"
        },
        "default": {
            "model": "ollama/llama3.2:latest",
            "temperature": 0.7,
            "max_tokens": 1500,
            "reason": "平衡性能和成本"
        }
    }
    
    @classmethod
    def get_config(cls, task_type: str = "default") -> Dict[str, Any]:
        """获取模型配置"""
        return cls.MODELS.get(task_type, cls.MODELS["default"])
    
    @classmethod
    def select_model(cls, task_type: str = "default") -> str:
        """选择模型"""
        config = cls.get_config(task_type)
        return config["model"]
    
    @classmethod
    def get_temperature(cls, task_type: str = "default") -> float:
        """获取 temperature"""
        config = cls.get_config(task_type)
        return config["temperature"]


# 使用示例
if __name__ == "__main__":
    # Planning 任务
    planning_config = ModelConfig.get_config("planning")
    print(f"Planning 模型: {planning_config['model']}")
    print(f"Temperature: {planning_config['temperature']}")
    print(f"原因: {planning_config['reason']}\n")
    
    # Memory 任务
    memory_config = ModelConfig.get_config("memory")
    print(f"Memory 模型: {memory_config['model']}")
    print(f"Temperature: {memory_config['temperature']}")
    print(f"原因: {memory_config['reason']}\n")
    
    # Vision 任务
    vision_config = ModelConfig.get_config("vision")
    print(f"Vision 模型: {vision_config['model']}")
    print(f"Temperature: {vision_config['temperature']}")
    print(f"原因: {vision_config['reason']}\n")
