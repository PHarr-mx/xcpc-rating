"""points 模块异常。"""


class PointsError(Exception):
    """积分模块基础异常。"""


class EventNotFoundError(PointsError):
    """积分场次不存在。"""


class InvalidEventError(PointsError):
    """场次参数非法。"""


class ClaimNotFoundError(PointsError):
    """认证记录不存在。"""


class ClaimStateError(PointsError):
    """认证状态机违规（重复审核等）。"""


class DuplicateClaimError(PointsError):
    """同（队/人）同场次重复认证。"""


class NotTeamMemberError(PointsError):
    """提交者不是该队伍成员。"""


class InvalidClaimError(PointsError):
    """认证内容非法（资格线、名次范围、value 越界等）。"""
