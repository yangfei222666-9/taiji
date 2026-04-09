"""
AIOS Scheduler 配置文件

这个文件控制 Scheduler 的行为，可以轻松切换调度策略和启用新功能。
"""

from enum import Enum


class SchedulerConfig:
    """Scheduler 配置"""
    
    # ==================== 基础配置 ====================
    
    # 最大并发任务数
    MAX_CONCURRENT = 5
    
    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 60
    
    # ==================== 调度策略 ====================
    
    class Policy(Enum):
        """调度策略"""
        PRIORITY = "priority"  # 优先级调度（默认）
        FIFO = "fifo"          # 先进先出
        SJF = "sjf"            # 最短作业优先
        RR = "rr"              # 轮转调度
        EDF = "edf"            # 最早截止时间优先
        HYBRID = "hybrid"      # 混合调度
    
    # 当前使用的调度策略
    CURRENT_POLICY = Policy.PRIORITY
    
    # 轮转调度的时间片（秒）
    RR_TIME_SLICE = 2
    
    # 混合调度的 fallback 策略
    HYBRID_FALLBACK = Policy.SJF
    
    # ==================== CPU 绑定 ====================
    
    # 是否启用 CPU 绑定
    ENABLE_CPU_BINDING = False
    
    # CPU 池（None = 使用所有 CPU）
    # 示例：[0, 1, 2, 3] 表示只使用 CPU 0-3
    CPU_POOL = None
    
    # ==================== 高级配置 ====================
    
    # 是否启用任务重试
    ENABLE_RETRY = True
    
    # 默认最大重试次数
    MAX_RETRIES = 3
    
    # 是否启用任务取消
    ENABLE_CANCEL = True
    
    # 是否启用进度追踪
    ENABLE_PROGRESS = True
    
    # 是否启用回调钩子
    ENABLE_CALLBACKS = True
    
    # ==================== 日志配置 ====================
    
    # 日志级别（DEBUG/INFO/WARNING/ERROR）
    LOG_LEVEL = "INFO"
    
    # 是否记录详细的调度日志
    VERBOSE_LOGGING = False
    
    # ==================== 性能调优 ====================
    
    # 是否启用性能监控
    ENABLE_PERFORMANCE_MONITORING = True
    
    # 性能监控采样间隔（秒）
    PERFORMANCE_SAMPLE_INTERVAL = 60
    
    # 是否启用自适应调度（根据历史数据自动调整）
    ENABLE_ADAPTIVE_SCHEDULING = False


# ==================== 预设配置 ====================

class PresetConfigs:
    """预设配置"""
    
    @staticmethod
    def default():
        """默认配置（兼容旧版）"""
        config = SchedulerConfig()
        config.CURRENT_POLICY = SchedulerConfig.Policy.PRIORITY
        config.ENABLE_CPU_BINDING = False
        return config
    
    @staticmethod
    def high_performance():
        """高性能配置（启用 CPU 绑定 + SJF）"""
        config = SchedulerConfig()
        config.CURRENT_POLICY = SchedulerConfig.Policy.SJF
        config.ENABLE_CPU_BINDING = True
        config.CPU_POOL = [0, 1, 2, 3]  # 使用前 4 个 CPU
        config.MAX_CONCURRENT = 8
        return config
    
    @staticmethod
    def real_time():
        """实时配置（EDF + CPU 绑定）"""
        config = SchedulerConfig()
        config.CURRENT_POLICY = SchedulerConfig.Policy.EDF
        config.ENABLE_CPU_BINDING = True
        config.CPU_POOL = [0, 1]  # 使用前 2 个 CPU（避免干扰）
        config.MAX_CONCURRENT = 4
        config.DEFAULT_TIMEOUT = 30
        return config
    
    @staticmethod
    def fair():
        """公平配置（FIFO）"""
        config = SchedulerConfig()
        config.CURRENT_POLICY = SchedulerConfig.Policy.FIFO
        config.ENABLE_CPU_BINDING = False
        config.MAX_CONCURRENT = 5
        return config
    
    @staticmethod
    def interactive():
        """交互式配置（RR）"""
        config = SchedulerConfig()
        config.CURRENT_POLICY = SchedulerConfig.Policy.RR
        config.RR_TIME_SLICE = 1  # 1秒时间片
        config.ENABLE_CPU_BINDING = False
        config.MAX_CONCURRENT = 10
        return config


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=" * 80)
    print("AIOS Scheduler 配置示例")
    print("=" * 80)
    
    # 默认配置
    print("\n=== 默认配置 ===")
    config = PresetConfigs.default()
    print(f"策略: {config.CURRENT_POLICY.value}")
    print(f"CPU 绑定: {config.ENABLE_CPU_BINDING}")
    print(f"最大并发: {config.MAX_CONCURRENT}")
    
    # 高性能配置
    print("\n=== 高性能配置 ===")
    config = PresetConfigs.high_performance()
    print(f"策略: {config.CURRENT_POLICY.value}")
    print(f"CPU 绑定: {config.ENABLE_CPU_BINDING}")
    print(f"CPU 池: {config.CPU_POOL}")
    print(f"最大并发: {config.MAX_CONCURRENT}")
    
    # 实时配置
    print("\n=== 实时配置 ===")
    config = PresetConfigs.real_time()
    print(f"策略: {config.CURRENT_POLICY.value}")
    print(f"CPU 绑定: {config.ENABLE_CPU_BINDING}")
    print(f"CPU 池: {config.CPU_POOL}")
    print(f"超时: {config.DEFAULT_TIMEOUT}s")
    
    print("\n" + "=" * 80)
    print("配置示例完成")
    print("=" * 80)
