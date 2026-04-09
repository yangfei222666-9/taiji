"""
AIOS Ollama 集成配置

M2 MacBook 上的 Ollama 服务配置
"""

import requests
import json
from typing import Dict, Any, Optional


class OllamaClient:
    """Ollama API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        初始化 Ollama 客户端
        
        Args:
            base_url: Ollama API 地址（M2 MacBook 的 IP）
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
    
    def list_models(self) -> Dict[str, Any]:
        """列出所有可用模型"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def generate(self, model: str, prompt: str, stream: bool = False) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            model: 模型名称（例如：gemma3:4b, qwen2.5:7b）
            prompt: 提示词
            stream: 是否流式输出
        
        Returns:
            生成的文本
        """
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }
            
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            if stream:
                # 流式输出
                result = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if 'response' in data:
                            result += data['response']
                return {"response": result}
            else:
                # 非流式输出
                return response.json()
        
        except Exception as e:
            return {"error": str(e)}
    
    def chat(self, model: str, messages: list, stream: bool = False) -> Dict[str, Any]:
        """
        对话模式
        
        Args:
            model: 模型名称
            messages: 消息列表 [{"role": "user", "content": "..."}]
            stream: 是否流式输出
        
        Returns:
            对话响应
        """
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            
            response = requests.post(
                f"{self.api_url}/chat",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            if stream:
                # 流式输出
                result = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if 'message' in data and 'content' in data['message']:
                            result += data['message']['content']
                return {"message": {"content": result}}
            else:
                # 非流式输出
                return response.json()
        
        except Exception as e:
            return {"error": str(e)}


def test_ollama_connection():
    """测试 Ollama 连接"""
    print("\n=== 测试 Ollama 连接 ===\n")
    
    client = OllamaClient()
    
    # 1. 列出模型
    print("1. 列出可用模型...")
    models = client.list_models()
    if "error" in models:
        print(f"   ❌ 连接失败: {models['error']}")
        print("\n请确保：")
        print("   1. M2 MacBook 上运行了 'ollama serve'")
        print("   2. M2 和 Windows 在同一网络")
        print("   3. M2 的防火墙允许端口 11434")
        return False
    
    print("   ✅ 连接成功！")
    print(f"   可用模型: {len(models.get('models', []))} 个")
    for model in models.get('models', []):
        print(f"      - {model['name']}")
    print()
    
    # 2. 测试生成
    if models.get('models'):
        model_name = models['models'][0]['name']
        print(f"2. 测试生成（模型: {model_name}）...")
        result = client.generate(model_name, "Say hello in one sentence")
        
        if "error" in result:
            print(f"   ❌ 生成失败: {result['error']}")
            return False
        
        print(f"   ✅ 生成成功！")
        print(f"   响应: {result.get('response', '')[:100]}...")
        print()
    
    # 3. 测试对话
    if models.get('models'):
        model_name = models['models'][0]['name']
        print(f"3. 测试对话（模型: {model_name}）...")
        messages = [
            {"role": "user", "content": "What is 1+1?"}
        ]
        result = client.chat(model_name, messages)
        
        if "error" in result:
            print(f"   ❌ 对话失败: {result['error']}")
            return False
        
        print(f"   ✅ 对话成功！")
        print(f"   响应: {result.get('message', {}).get('content', '')[:100]}...")
        print()
    
    print("=== 所有测试通过 ✅ ===\n")
    return True


if __name__ == '__main__':
    # 测试连接
    success = test_ollama_connection()
    
    if success:
        print("\n🎉 Ollama 集成配置成功！\n")
        print("现在可以在 AIOS 中使用 M2 上的模型了！")
        print("\n使用示例：")
        print("```python")
        print("from ollama_client import OllamaClient")
        print("")
        print("client = OllamaClient()")
        print("result = client.generate('gemma3:4b', '写一个 Python 函数计算斐波那契数列')")
        print("print(result['response'])")
        print("```")
    else:
        print("\n❌ 连接失败，请检查配置")
