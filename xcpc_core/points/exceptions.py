"""points 模块异常。"""

from xcpc_core.contest.exceptions import ContestNotFoundError  # re-export：认证场次=统一比赛


class PointsError(Exception):
    """积分模块基础异常。"""


class ClaimNotFoundError(PointsError):
    """认证记录不存在。"""


class ClaimStateError(PointsError):
    """认证状态机违规（重复审核等）。"""


class DuplicateClaimError(PointsError):
    """同（队/人）同比赛重复认证。"""


class NotTeamMemberError(PointsError):
    """提交者不是该队伍成员。"""


class InvalidClaimError(PointsError):
    """认证内容非法（资格线、名次范围、奖项不存在、场次不允许申报等）。"""


class UnknownAwardError(InvalidClaimError):
    """申报的奖项不在 awardlevel 内。"""
