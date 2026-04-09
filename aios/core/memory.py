"""
AIOS Memory Module - 记忆管理系统

核心功能：
1. 向量检索（FAISS）
2. 记忆分层（短期/长期/工作记忆）
3. 自动整理（定期提炼）
4. 重要性评分

Author: 小九 + 珊瑚海
Date: 2026-02-26
"""

import json
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib


@dataclass
class Memory:
    """记忆单元"""
    id: str
    content: str
    type: str  # short_term/long_term/working
    importance: float  # 0.0 - 1.0
    timestamp: float
    source: str  # 来源（user/agent/system）
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    
    def __post_init__(self):
        if not self.id:
            # 生成唯一 ID（基于内容哈希）
            self.id = hashlib.md5(
                f"{self.content}{self.timestamp}".encode()
            ).hexdigest()[:16]


class SimpleEmbedding:
    """简单的 Embedding 实现（TF-IDF 风格）"""
    
    def __init__(self, dim: int = 128):
        self.dim = dim
        self.vocab = {}
        self.idf = {}
    
    def fit(self, texts: List[str]):
        """构建词表和 IDF"""
        # 统计词频
        doc_freq = {}
        for text in texts:
            words = set(self._tokenize(text))
            for word in words:
                doc_freq[word] = doc_freq.get(word, 0) + 1
        
        # 构建词表（取前 dim 个高频词）
        sorted_words = sorted(doc_freq.items(), key=lambda x: x[1], reverse=True)
        self.vocab = {word: i for i, (word, _) in enumerate(sorted_words[:self.dim])}
        
        # 计算 IDF
        n_docs = len(texts)
        for word, freq in doc_freq.items():
            self.idf[word] = np.log(n_docs / (freq + 1))
    
    def encode(self, text: str) -> List[float]:
        """文本 → 向量"""
        vector = np.zeros(self.dim)
        words = self._tokenize(text)
        
        # TF-IDF
        word_count = {}
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1
        
        for word, count in word_count.items():
            if word in self.vocab:
                idx = self.vocab[word]
                tf = count / len(words)
                idf = self.idf.get(word, 1.0)
                vector[idx] = tf * idf
        
        # 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector.tolist()
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词（按空格和标点）"""
        import re
        # 移除标点，转小写，按空格分词
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        return text.split()


class VectorDB:
    """简单的向量数据库（基于 FAISS 的思路，但用纯 Python 实现）"""
    
    def __init__(self, dim: int = 128):
        self.dim = dim
        self.vectors = []
        self.memories = []
    
    def add(self, embedding: List[float], memory: Memory):
        """添加向量"""
        self.vectors.append(np.array(embedding))
        self.memories.append(memory)
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Memory]:
        """向量检索（余弦相似度）"""
        if not self.vectors:
            return []
        
        query_vec = np.array(query_embedding)
        
        # 计算余弦相似度
        similarities = []
        for vec in self.vectors:
            sim = np.dot(query_vec, vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-8
            )
            similarities.append(sim)
        
        # 取 top-k
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        return [self.memories[i] for i in top_k_indices if similarities[i] > 0.1]
    
    def save(self, path: Path):
        """保存到文件"""
        data = {
            "vectors": [v.tolist() for v in self.vectors],
            "memories": [asdict(m) for m in self.memories]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self, path: Path):
        """从文件加载"""
        if not path.exists():
            return
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.vectors = [np.array(v) for v in data["vectors"]]
        self.memories = [Memory(**m) for m in data["memories"]]


class MemoryManager:
    """记忆管理器"""
    
    def __init__(self, workspace: Path, dim: int = 128):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 三层记忆
        self.short_term: List[Memory] = []  # 短期记忆（最近 100 条）
        self.long_term = VectorDB(dim)  # 长期记忆（向量数据库）
        self.working: Dict[str, List[Memory]] = {}  # 工作记忆（任务相关）
        
        # Embedding 模型
        self.embedding = SimpleEmbedding(dim)
        
        # 加载长期记忆
        self._load_long_term()
        
        # 训练 Embedding（如果是首次运行）
        if not self.long_term.memories:
            self._init_embedding()
    
    def _load_long_term(self):
        """加载长期记忆"""
        db_file = self.memory_dir / "long_term.json"
        if db_file.exists():
            self.long_term.load(db_file)
    
    def _save_long_term(self):
        """保存长期记忆"""
        db_file = self.memory_dir / "long_term.json"
        self.long_term.save(db_file)
    
    def _init_embedding(self):
        """初始化 Embedding（从 MEMORY.md 训练）"""
        memory_md = self.workspace / "MEMORY.md"
        if not memory_md.exists():
            return
        
        with open(memory_md, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 按段落分割
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        # 训练 Embedding
        self.embedding.fit(paragraphs)
        
        # 将 MEMORY.md 内容加入长期记忆
        for para in paragraphs:
            if len(para) > 20:  # 过滤太短的段落
                memory = Memory(
                    id="",
                    content=para,
                    type="long_term",
                    importance=0.8,
                    timestamp=time.time(),
                    source="system",
                    metadata={"source_file": "MEMORY.md"}
                )
                embedding = self.embedding.encode(para)
                memory.embedding = embedding
                self.long_term.add(embedding, memory)
        
        self._save_long_term()
    
    def store(self, content: str, source: str = "user", 
              importance: Optional[float] = None, 
              metadata: Optional[Dict] = None) -> Memory:
        """存储记忆"""
        # 计算重要性（如果未指定）
        if importance is None:
            importance = self._calculate_importance(content)
        
        # 创建记忆
        memory = Memory(
            id="",
            content=content,
            type="short_term",
            importance=importance,
            timestamp=time.time(),
            source=source,
            metadata=metadata or {}
        )
        
        # 1. 短期记忆（直接存储）
        self.short_term.append(memory)
        
        # 2. 长期记忆（重要的记忆持久化）
        if importance > 0.7:
            embedding = self.embedding.encode(content)
            memory.embedding = embedding
            memory.type = "long_term"
            self.long_term.add(embedding, memory)
            self._save_long_term()
        
        # 3. 限制短期记忆大小
        if len(self.short_term) > 100:
            self.short_term = self.short_term[-100:]
        
        return memory
    
    def retrieve(self, query: str, k: int = 5, 
                include_short_term: bool = True) -> List[Memory]:
        """检索相关记忆"""
        results = []
        
        # 1. 向量检索（长期记忆）
        query_embedding = self.embedding.encode(query)
        long_term_results = self.long_term.search(query_embedding, k)
        results.extend(long_term_results)
        
        # 2. 短期记忆（最近的记忆）
        if include_short_term:
            results.extend(self.short_term[-10:])
        
        # 3. 去重 + 按重要性排序
        seen = set()
        unique_results = []
        for mem in results:
            if mem.id not in seen:
                seen.add(mem.id)
                unique_results.append(mem)
        
        unique_results.sort(key=lambda m: m.importance, reverse=True)
        return unique_results[:k]
    
    def store_working(self, task_id: str, content: str, 
                     metadata: Optional[Dict] = None) -> Memory:
        """存储工作记忆（任务相关）"""
        memory = Memory(
            id="",
            content=content,
            type="working",
            importance=0.5,
            timestamp=time.time(),
            source="agent",
            metadata=metadata or {"task_id": task_id}
        )
        
        if task_id not in self.working:
            self.working[task_id] = []
        
        self.working[task_id].append(memory)
        return memory
    
    def get_working(self, task_id: str) -> List[Memory]:
        """获取工作记忆"""
        return self.working.get(task_id, [])
    
    def clear_working(self, task_id: str):
        """清理工作记忆"""
        if task_id in self.working:
            del self.working[task_id]
    
    def consolidate(self):
        """整理记忆（定期执行）"""
        # 1. 短期 → 长期（重要的记忆持久化）
        for memory in self.short_term:
            if memory.importance > 0.7 and memory.type == "short_term":
                embedding = self.embedding.encode(memory.content)
                memory.embedding = embedding
                memory.type = "long_term"
                self.long_term.add(embedding, memory)
        
        # 2. 清理短期记忆（保留最近 100 条）
        self.short_term = self.short_term[-100:]
        
        # 3. 保存长期记忆
        self._save_long_term()
        
        # 4. 更新 MEMORY.md（提炼精华）
        self._update_memory_md()
    
    def _calculate_importance(self, content: str) -> float:
        """计算重要性（简单规则）"""
        importance = 0.5  # 基础分
        
        # 长度加分（长文本通常更重要）
        if len(content) > 100:
            importance += 0.1
        if len(content) > 500:
            importance += 0.1
        
        # 关键词加分
        keywords = [
            "重要", "关键", "核心", "突破", "成功", "失败", "教训",
            "决策", "方案", "架构", "设计", "实现", "优化"
        ]
        for kw in keywords:
            if kw in content:
                importance += 0.05
        
        return min(importance, 1.0)
    
    def _update_memory_md(self):
        """更新 MEMORY.md（提炼精华）"""
        memory_md = self.workspace / "MEMORY.md"
        
        # 读取现有内容
        existing_content = ""
        if memory_md.exists():
            with open(memory_md, "r", encoding="utf-8") as f:
                existing_content = f.read()
        
        # 提取最近 7 天的重要记忆
        cutoff_time = time.time() - 7 * 24 * 3600
        recent_important = [
            m for m in self.long_term.memories
            if m.timestamp > cutoff_time and m.importance > 0.8
        ]
        
        # 按时间排序
        recent_important.sort(key=lambda m: m.timestamp, reverse=True)
        
        # 生成新内容
        new_section = "\n\n## 最近更新（自动生成）\n\n"
        for mem in recent_important[:10]:  # 最多 10 条
            date = datetime.fromtimestamp(mem.timestamp).strftime("%Y-%m-%d")
            new_section += f"### {date}\n\n{mem.content}\n\n"
        
        # 追加到文件（如果有新内容）
        if recent_important and new_section not in existing_content:
            with open(memory_md, "a", encoding="utf-8") as f:
                f.write(new_section)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "short_term_count": len(self.short_term),
            "long_term_count": len(self.long_term.memories),
            "working_tasks": len(self.working),
            "total_memories": len(self.short_term) + len(self.long_term.memories),
            "avg_importance": np.mean([m.importance for m in self.long_term.memories]) if self.long_term.memories else 0.0
        }


def demo():
    """演示 Memory 模块功能"""
    workspace = Path(__file__).parent.parent.parent
    manager = MemoryManager(workspace)
    
    print("=== AIOS Memory Module Demo ===\n")
    
    # 测试1：存储记忆
    print("测试1：存储记忆")
    mem1 = manager.store("实现了 Planning 模块，支持 CoT 任务拆解", importance=0.9)
    mem2 = manager.store("修复了一个小 bug", importance=0.3)
    mem3 = manager.store("设计了 Memory 模块的架构，包含向量检索和记忆分层", importance=0.9)
    print(f"已存储 3 条记忆")
    print(f"- 记忆1: {mem1.content[:30]}... (重要性: {mem1.importance})")
    print(f"- 记忆2: {mem2.content[:30]}... (重要性: {mem2.importance})")
    print(f"- 记忆3: {mem3.content[:30]}... (重要性: {mem3.importance})")
    print()
    
    # 测试2：检索记忆
    print("测试2：检索记忆")
    query = "Planning 模块"
    results = manager.retrieve(query, k=3)
    print(f"查询: {query}")
    print(f"找到 {len(results)} 条相关记忆:")
    for i, mem in enumerate(results):
        print(f"  {i+1}. {mem.content[:50]}... (重要性: {mem.importance:.2f})")
    print()
    
    # 测试3：工作记忆
    print("测试3：工作记忆")
    task_id = "task_123"
    manager.store_working(task_id, "开始设计 Memory 模块")
    manager.store_working(task_id, "完成了向量检索功能")
    working_mems = manager.get_working(task_id)
    print(f"任务 {task_id} 的工作记忆:")
    for mem in working_mems:
        print(f"  - {mem.content}")
    print()
    
    # 测试4：统计信息
    print("测试4：统计信息")
    stats = manager.get_stats()
    print(f"短期记忆: {stats['short_term_count']}")
    print(f"长期记忆: {stats['long_term_count']}")
    print(f"工作任务: {stats['working_tasks']}")
    print(f"总记忆数: {stats['total_memories']}")
    print(f"平均重要性: {stats['avg_importance']:.2f}")
    print()
    
    # 测试5：整理记忆
    print("测试5：整理记忆")
    manager.consolidate()
    print("记忆整理完成！")
    print()
    
    print("[OK] Demo 完成！")


if __name__ == "__main__":
    demo()
