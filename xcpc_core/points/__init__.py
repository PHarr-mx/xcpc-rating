"""points 模块：生涯积分制（第二轨，RATING_FORMULA_PLAN.md §9）。

计分公式（UCup 式单场分，去 GP30）：100 × (value/max_value) × 名次百分位。
工作流：管理员配置场次 → 选手/队伍提交认证 → 审核记分（staged/approved/rejected）。
对外入口见 ``api``（DI 注入模式与 importer/audit 一致）。
"""

from xcpc_core.points.api import (
    configure_session,
    create_event,
    get_event,
    individual_leaderboard,
    list_claims,
    list_events,
    my_claims,
    player_teams,
    review_claim,
    submit_claim,
    team_leaderboard,
    update_event,
)
from xcpc_core.points.exceptions import (
    ClaimNotFoundError,
    ClaimStateError,
    DuplicateClaimError,
    EventNotFoundError,
    InvalidClaimError,
    InvalidEventError,
    NotTeamMemberError,
    PointsError,
)
from xcpc_core.points.formula import compute_points
from xcpc_core.points.models import (
    IndividualPointsRow,
    PointsClaimCreate,
    PointsClaimView,
    PointsEventCreate,
    PointsEventUpdate,
    PointsEventView,
    TeamPointsRow,
)

__all__ = [
    "ClaimNotFoundError",
    "ClaimStateError",
    "DuplicateClaimError",
    "EventNotFoundError",
    "IndividualPointsRow",
    "InvalidClaimError",
    "InvalidEventError",
    "NotTeamMemberError",
    "PointsClaimCreate",
    "PointsClaimView",
    "PointsError",
    "PointsEventCreate",
    "PointsEventUpdate",
    "PointsEventView",
    "TeamPointsRow",
    "compute_points",
    "configure_session",
    "create_event",
    "get_event",
    "individual_leaderboard",
    "list_claims",
    "list_events",
    "my_claims",
    "player_teams",
    "review_claim",
    "submit_claim",
    "team_leaderboard",
    "update_event",
]
