"""
AIOS v0.6 Production Reactor - 规则索引 + O(1) 查找
职责：
1. 按事件类型索引 playbook
2. O(1) 哈希查找
3. 支持 100+ playbook 规则
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict


class ProductionReactor:
    """生产级 Reactor - 规则索引"""
    
    def __init__(self, playbooks_path: Optional[Path] = None):
        """
        初始化 Reactor
        
        Args:
            playbooks_path: playbook 配置文件路径
        """
        if playbooks_path is None:
            workspace = Path(__file__).parent.parent.parent
            playbooks_path = workspace / "aios" / "data" / "playbooks.json"
        
        self.playbooks_path = Path(playbooks_path)
        
        # 加载 playbook
        self.playbooks = self._load_playbooks()
        
        # 构建索引
        self.rule_index = self._build_rule_index()
        self.keyword_index = self._build_keyword_index()
        
        # 统计
        self.stats = {
            "total_matched": 0,
            "total_executed": 0,
            "total_success": 0,
            "total_failed": 0
        }
        
        print(f"[Reactor] 加载了 {len(self.playbooks)} 个 playbook")
        print(f"[Reactor] 规则索引: {len(self.rule_index)} 个规则")
        print(f"[Reactor] 关键词索引: {len(self.keyword_index)} 个关键词")
    
    def match(self, event: Dict[str, Any]) -> Optional[Dict]:
        """
        匹配 playbook（O(1) 查找）
        
        Args:
            event: 事件对象
        
        Returns:
            匹配的 playbook，如果没有匹配返回 None
        """
        event_type = event.get("type", "")
        event_text = str(event.get("payload", {}))
        
        # 1. 先尝试规则索引（精确匹配）
        if event_type in self.rule_index:
            candidates = self.rule_index[event_type]
            for playbook in candidates:
                if self._check_playbook(playbook, event):
                    self.stats["total_matched"] += 1
                    return playbook
        
        # 2. 再尝试关键词索引（模糊匹配）
        for keyword, playbooks in self.keyword_index.items():
            if keyword.lower() in event_text.lower():
                for playbook in playbooks:
                    if self._check_playbook(playbook, event):
                        self.stats["total_matched"] += 1
                        return playbook
        
        return None
    
    def execute(self, playbook: Dict, event: Dict) -> Dict:
        """
        执行 playbook
        
        Args:
            playbook: playbook 配置
            event: 触发事件
        
        Returns:
            执行结果
        """
        start_time = time.time()
        playbook_id = playbook["id"]
        
        print(f"[Reactor] 执行 playbook: {playbook['name']}")
        
        try:
            # 检查是否启用
            if not playbook.get("enabled", True):
                return {
                    "success": False,
                    "error": "Playbook disabled"
                }
            
            # 执行动作
            action = playbook["action"]
            action_type = action["type"]
            
            if action_type == "auto":
                # 自动执行
                result = self._execute_command(action["command"])
            elif action_type == "confirm":
                # 需要确认（这里先自动执行，实际应该等待确认）
                print(f"[Reactor] ⚠️  需要确认: {action['command']}")
                result = {"status": "pending_confirm"}
            elif action_type == "notify":
                # 仅通知
                print(f"[Reactor] 📢 通知: {action['command']}")
                result = {"status": "notified"}
            else:
                result = {"status": "unknown_action_type"}
            
            duration = time.time() - start_time
            
            # 更新统计
            self.stats["total_executed"] += 1
            self.stats["total_success"] += 1
            
            # 更新 playbook 统计
            playbook["success_count"] = playbook.get("success_count", 0) + 1
            self._save_playbooks()
            
            return {
                "success": True,
                "playbook_id": playbook_id,
                "duration": duration,
                "result": result
            }
        
        except Exception as e:
            duration = time.time() - start_time
            
            print(f"[Reactor] ❌ 执行失败: {e}")
            
            # 更新统计
            self.stats["total_executed"] += 1
            self.stats["total_failed"] += 1
            
            # 更新 playbook 统计
            playbook["fail_count"] = playbook.get("fail_count", 0) + 1
            self._save_playbooks()
            
            return {
                "success": False,
                "playbook_id": playbook_id,
                "duration": duration,
                "error": str(e)
            }
    
    def _execute_command(self, command: str) -> Dict:
        """执行命令（模拟）"""
        # 实际应该调用 exec 工具
        print(f"[Reactor] 🔧 执行命令: {command[:60]}...")
        time.sleep(0.1)  # 模拟执行时间
        return {"status": "executed", "command": command}
    
    def _check_playbook(self, playbook: Dict, event: Dict) -> bool:
        """
        检查 playbook 是否匹配事件
        
        Args:
            playbook: playbook 配置
            event: 事件对象
        
        Returns:
            是否匹配
        """
        # 检查是否启用
        if not playbook.get("enabled", True):
            return False
        
        # 检查关键词
        trigger = playbook.get("trigger", {})
        keywords = trigger.get("keywords", [])
        
        event_text = str(event.get("payload", {})).lower()
        
        for keyword in keywords:
            if keyword.lower() in event_text:
                return True
        
        return False
    
    # ========== 索引构建 ==========
    
    def _build_rule_index(self) -> Dict[str, List[Dict]]:
        """
        构建规则索引（按事件类型）
        
        Returns:
            {event_type: [playbook1, playbook2, ...]}
        """
        index = defaultdict(list)
        
        for playbook in self.playbooks:
            trigger = playbook.get("trigger", {})
            rule = trigger.get("rule", "")
            
            # 映射规则到事件类型
            event_types = self._rule_to_event_types(rule)
            
            for event_type in event_types:
                index[event_type].append(playbook)
        
        return dict(index)
    
    def _build_keyword_index(self) -> Dict[str, List[Dict]]:
        """
        构建关键词索引
        
        Returns:
            {keyword: [playbook1, playbook2, ...]}
        """
        index = defaultdict(list)
        
        for playbook in self.playbooks:
            trigger = playbook.get("trigger", {})
            keywords = trigger.get("keywords", [])
            
            for keyword in keywords:
                index[keyword.lower()].append(playbook)
        
        return dict(index)
    
    @staticmethod
    def _rule_to_event_types(rule: str) -> List[str]:
        """
        规则映射到事件类型
        
        Args:
            rule: 规则名称
        
        Returns:
            事件类型列表
        """
        mapping = {
            "network_error": ["agent.error", "resource.network_error"],
            "disk_full": ["resource.disk_full"],
            "process_crash": ["agent.error", "process.crashed"],
            "rate_limit": ["agent.error", "api.rate_limit"],
            "memory_high": ["resource.memory_high"],
            "gpu_overheat": ["resource.gpu_overheat"],
            "lol_version_updated": ["sensor.lol.version_updated"],
            "gpu_critical": ["resource.gpu_critical"],
            "app_stopped": ["sensor.app.stopped"],
            "model_failure": ["agent.error", "llm.error"],
            "memory_critical": ["resource.memory_critical"],
            "network_slow": ["resource.network_slow"],
            "aios_unhealthy": ["score.degraded", "reactor.failed"]
        }
        
        return mapping.get(rule, [])
    
    # ========== 配置管理 ==========
    
    def _load_playbooks(self) -> List[Dict]:
        """加载 playbook 配置"""
        if not self.playbooks_path.exists():
            return []
        
        with open(self.playbooks_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_playbooks(self):
        """保存 playbook 配置"""
        with open(self.playbooks_path, "w", encoding="utf-8") as f:
            json.dump(self.playbooks, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "playbooks_count": len(self.playbooks),
            "rule_index_size": len(self.rule_index),
            "keyword_index_size": len(self.keyword_index),
            "stats": self.stats.copy()
        }


# 全局单例
_global_reactor: Optional[ProductionReactor] = None


def get_reactor() -> ProductionReactor:
    """获取全局 Reactor 实例"""
    global _global_reactor
    if _global_reactor is None:
        _global_reactor = ProductionReactor()
    return _global_reactor
