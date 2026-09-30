"""tier 模块异常基类与子类。"""


class TierError(Exception):
    """tier 模块基础异常。"""


class TierNotFoundError(TierError):
    """赛事等级不存在。"""


class DuplicateTierError(TierError):
    """赛事等级名已存在。"""


class TierInUseError(TierError):
    """赛事等级仍被比赛引用，禁止删除。"""


class AwardLevelNotFoundError(TierError):
    """奖项等级不存在。"""


class DuplicateAwardLevelError(TierError):
    """奖项等级名已存在。"""


class AwardLevelInUseError(TierError):
    """奖项等级仍被认证/成绩引用，禁止删除。"""
