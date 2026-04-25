#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real Executor - 直接调用 Claude API 执行任务
"""
import sys
import json
import os
import time
import requests
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 从 OpenClaw 配置读取 API Key
CONFIG_FILE = Path(os.environ.get("OPENCLAW_CONFIG_FILE", Path.home() / ".openclaw" / "openclaw.json"))

def get_api_config():
    """读取 API 配置"""
    with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f:
        config = json.load(f)
    
    chat_provider = config['models']['providers']['chat']
    return {
        'base_url': chat_provider['baseUrl'],
        'api_key': chat_provider['apiKey'],
        'model': 'claude-sonnet-4-6'
    }

def execute_task_real(task_desc: str, agent_type: str = 'coder') -> dict:
    """
    真实执行任务（通过 Claude API）
    
    Args:
        task_desc: 任务描述
        agent_type: Agent 类型（coder/analyst/monitor）
    
    Returns:
        执行结果
    """
    config = get_api_config()
    
    # 构建 prompt
    system_prompt = {
        'coder': 'You are a coding assistant. Execute the task and provide code or implementation.',
        'analyst': 'You are a data analyst. Analyze the data and provide insights.',
        'monitor': 'You are a system monitor. Check system status and report findings.'
    }.get(agent_type, 'You are a helpful assistant.')
    
    # 调用 Claude API
    url = f"{config['base_url']}v1/messages"
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': config['api_key'],
        'anthropic-version': '2023-06-01'
    }
    
    payload = {
        'model': config['model'],
        'max_tokens': 4096,
        'system': system_prompt,
        'messages': [
            {
                'role': 'user',
                'content': task_desc
            }
        ]
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            output = result['content'][0]['text']
            
            return {
                'success': True,
                'agent': agent_type,
                'duration': duration,
                'output': output,
                'tokens': {
                    'input': result['usage']['input_tokens'],
                    'output': result['usage']['output_tokens']
                }
            }
        else:
            return {
                'success': False,
                'agent': agent_type,
                'error': f"API error: {response.status_code} - {response.text}"
            }
    
    except requests.Timeout:
        return {
            'success': False,
            'agent': agent_type,
            'error': 'Request timeout (60s)'
        }
    except Exception as e:
        return {
            'success': False,
            'agent': agent_type,
            'error': str(e)
        }

if __name__ == '__main__':
    # 测试
    result = execute_task_real(
        task_desc="输出 'Hello from AIOS' 并解释这个系统的作用",
        agent_type='coder'
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
