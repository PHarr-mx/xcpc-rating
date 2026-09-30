"""AtCoder 式训练赛 Rating 公式参数（docs/04 §2.1，定案 2026-09-28）。

全部集中于此，试算页（P-R4）调参只动这个文件。
"""

CENTER: float = 800.0              # 无历史先验锚点（对应 AtCoder ABC 档；定案暂不分档）
LOGISTIC_SCALE: float = 400.0      # Logistic 尺度：实力差 400 分 → 期望对局赔率 1:6
LOGISTIC_ODDS: float = 6.0         # 赔率基数
G_SCALE: float = 800.0             # g 变换尺度 g(X)=2^(X/800)
TIME_DECAY: float = 0.9            # 时间权重 0.9^i（i=1 最新，约 22 场半衰）
FIRST_PERF_INFLATION: float = 1.5  # 实体首场表现分膨胀
F_FULL: float = 1200.0             # f(n) 满额（n=1 时的扣减值）
