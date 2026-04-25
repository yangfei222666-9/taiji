#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AIOS 健康检查脚本"""

import json
from pathlib import Path
from datetime import datetime
from aios.agent_system.config_center import agent_system_root
from agent_status import (
    validate_status_object,
    is_production_ready,
    is_healthy,
    needs_attention,
    get_status_summary
)

def main():
    base_path = agent_system_root()

    # 读取 agents.json
    agents_file = base_path / 'agents.json'
    with open(agents_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        agents = data.get('agents', [])
        metadata = data.get('metadata', {})

    # 统计 Agent 状态
    total_agents = len(agents)
    enabled_agents = sum(1 for a in agents if a.get('enabled', False))
    production_ready = sum(1 for a in agents if a.get('production_ready', False))

    # 统计任务执行情况
    total_tasks = sum(a.get('stats', {}).get('tasks_total', 0) for a in agents)
    completed_tasks = sum(a.get('stats', {}).get('tasks_completed', 0) for a in agents)
    failed_tasks = sum(a.get('stats', {}).get('tasks_failed', 0) for a in agents)

    # 找出失败率高的 Agent
    high_failure_agents = []
    for agent in agents:
        stats = agent.get('stats', {})
        total = stats.get('tasks_total', 0)
        failed = stats.get('tasks_failed', 0)
        if total > 0:
            failure_rate = failed / total
            if failure_rate > 0.3:  # 失败率 > 30%
                high_failure_agents.append({
                    'name': agent.get('name'),
                    'total': total,
                    'failed': failed,
                    'rate': round(failure_rate * 100, 1)
                })

    # 检查任务队列
    queue_file = base_path / 'task_queue.jsonl'
    pending_tasks = 0
    if queue_file.exists():
        with open(queue_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    task = json.loads(line)
                    if task.get('status') == 'pending':
                        pending_tasks += 1

    # 检查 spawn_pending
    spawn_file = base_path / 'spawn_pending.jsonl'
    pending_spawns = 0
    if spawn_file.exists():
        with open(spawn_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    pending_spawns += 1

    # 检查最近错误
    log_file = base_path / 'heartbeat.log'
    recent_errors = []
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-100:]:
                if 'ERROR' in line or 'FAILED' in line or 'Exception' in line:
                    recent_errors.append(line.strip())

    # 计算健康分数
    score = 100

    # Agent 可用性（-10 if < 50% enabled）
    if enabled_agents / total_agents < 0.5:
        score -= 10

    # 生产就绪度（-15 if < 2 production ready）
    # 注：当前真实 production-ready 数量为 2（GitHub_Researcher + Error_Analyzer）
    if production_ready < 2:
        score -= 15

    # 任务成功率（-20 if < 70%）
    if total_tasks > 0:
        success_rate = completed_tasks / total_tasks
        if success_rate < 0.7:
            score -= 20

    # 高失败率 Agent（-15 per agent, max -30）
    score -= min(len(high_failure_agents) * 15, 30)

    # 待处理任务积压（-15 if > 10）
    if pending_tasks > 10:
        score -= 15

    # 待处理 spawn 积压（-10 if > 5）
    if pending_spawns > 5:
        score -= 10

    # 最近错误（-5 per error, max -25）
    error_penalty = min(len(recent_errors) * 5, 25)
    score -= error_penalty

    health_score = max(0, score)

    # 输出报告
    print('=== AIOS 健康检查报告 ===')
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()
    print('【系统概览】')
    print(f'  总 Agent 数: {total_agents}')
    print(f'  已启用: {enabled_agents}')
    print(f'  生产就绪: {production_ready}')
    print()
    print('【任务执行】')
    print(f'  总任务数: {total_tasks}')
    print(f'  已完成: {completed_tasks}')
    print(f'  失败: {failed_tasks}')
    if total_tasks > 0:
        print(f'  成功率: {round(completed_tasks/total_tasks*100, 1)}%')
    print()
    print('【队列状态】')
    print(f'  待处理任务: {pending_tasks}')
    print(f'  待处理 spawn: {pending_spawns}')
    print()
    if high_failure_agents:
        print('【高失败率 Agent】')
        for agent in high_failure_agents:
            print(f'  - {agent["name"]}: {agent["failed"]}/{agent["total"]} ({agent["rate"]}%)')
        print()
    if recent_errors:
        print('【最近错误】')
        print(f'  错误数量: {len(recent_errors)}')
        print('  最新 3 条:')
        for err in recent_errors[-3:]:
            if len(err) > 100:
                print(f'    {err[:100]}...')
            else:
                print(f'    {err}')
        print()
    print('【健康分数】')
    print(f'  分数: {health_score}/100')
    if health_score >= 80:
        status = '✅ 良好'
    elif health_score >= 60:
        status = '⚠️ 警告'
    else:
        status = '🚨 严重'
    print(f'  状态: {status}')
    print()
    if health_score < 60:
        print('【告警】健康分数低于 60，需要立即关注！')

    # === Governance Status（state_index.json 消费） ===
    state_index_file = base_path / 'state_index.json'
    if state_index_file.exists():
        try:
            with open(state_index_file, 'r', encoding='utf-8') as f:
                state_index = json.load(f)

            gov_items = []
            validation_errors = []

            # 读取 agents
            for name, state in state_index.get('agents', {}).items():
                # 使用统一状态模块校验
                is_valid, errors = validate_status_object(state)
                if not is_valid:
                    validation_errors.append((name, errors))
                
                # 使用统一状态模块生成摘要
                summary = get_status_summary(state)
                
                # 判断是否需要关注
                attention = needs_attention(state)
                
                gov_items.append((name, summary, attention))

            # 读取 skills
            for name, state in state_index.get('skills', {}).items():
                is_valid, errors = validate_status_object(state)
                if not is_valid:
                    validation_errors.append((name, errors))
                
                summary = get_status_summary(state)
                attention = needs_attention(state)
                
                gov_items.append((name, summary, attention))

            if gov_items:
                print('【Governance Status】(source: state_index.json)')
                for name, summary, attention in gov_items:
                    marker = '⚠️' if attention else '✅'
                    print(f'  {marker} {name} — {summary}')
                print()
            
            if validation_errors:
                print('【状态校验错误】')
                for name, errors in validation_errors:
                    print(f'  ❌ {name}:')
                    for error in errors:
                        print(f'      {error}')
                print()
        except Exception as e:
            print(f'【Governance Status】读取 state_index.json 失败: {e}')
            print()

    # === Agent Tier Summary（agent_tiers.json 消费） ===
    tiers_file = base_path / 'agent_tiers.json'
    if tiers_file.exists():
        try:
            with open(tiers_file, 'r', encoding='utf-8') as f:
                tiers_data = json.load(f)
            
            summary = tiers_data.get('summary', {})
            real_chain = tiers_data.get('real_chain', [])
            
            print('【Agent Tier Summary】(source: agent_tiers.json)')
            print(f'  真链: {summary.get("real_chain_count", 0)}')
            print(f'  候选链: {summary.get("candidate_count", 0)}')
            print(f'  休眠壳: {summary.get("dormant_count", 0)}')
            print()
            
            if real_chain:
                print('  真链代表:')
                for agent in real_chain[:7]:  # 最多显示 7 个
                    name = agent.get('agent_name', 'unknown')
                    evidence = agent.get('evidence', '')
                    print(f'    - {name} ({evidence})')
                print()
        except Exception as e:
            print(f'【Agent Tier Summary】读取 agent_tiers.json 失败: {e}')
            print()

    # === Self-Learning Status（selflearn-state.json 消费） ===
    selflearn_file = base_path / 'data' / 'selflearn-state.json'
    if selflearn_file.exists():
        try:
            with open(selflearn_file, 'r', encoding='utf-8') as f:
                selflearn = json.load(f)
            
            print('【Self-Learning Status】(source: selflearn-state.json)')
            print(f'  最近运行: {selflearn.get("last_run", "未知")}')
            print(f'  最近成功: {selflearn.get("last_success", "未知")}')
            print(f'  已激活学习 Agent: {len(selflearn.get("activated_agents", []))}')
            print(f'  待提炼 lesson: {selflearn.get("pending_lessons", 0)}')
            print(f'  已提炼规则: {selflearn.get("rules_derived_count", 0)}')
            
            activated = selflearn.get('activated_agents', [])
            if activated:
                print(f'  激活列表: {", ".join(activated)}')
            print()
        except Exception as e:
            print(f'【Self-Learning Status】读取 selflearn-state.json 失败: {e}')
            print()

    return health_score

if __name__ == '__main__':
    score = main()
    exit(0 if score >= 60 else 1)
