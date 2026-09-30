"""points 模块：生涯积分制（第二轨，改挂统一比赛）。

计分公式（UCup 式单场分，去 GP30）：
- formula:    100 × (value/max_value) × 名次百分位 × tier.coefficient
- award_only: awardlevel.base_points × tier.coefficient
工作流：管理员建比赛（contest 模块）→ 选手/队伍提交认证 → 审核记分（staged/approved/rejected）。
对外入口见 ``api``（DI 注入模式与 importer/audit 一致）。
"""

from xcpc_core.points.api import (
    configure_session,
    individual_leaderboard,
    list_claims,
    my_claims,
    player_teams,
    review_claim,
    submit_claim,
    team_leaderboard,
)
from xcpc_core.points.exceptions import (
    ClaimNotFoundError,
    ClaimStateError,
    ContestNotFoundError,
    DuplicateClaimError,
    InvalidClaimError,
    NotTeamMemberError,
    PointsError,
    UnknownAwardError,
)
from xcpc_core.points.formula import compute_award_points, compute_points
from xcpc_core.points.models import (
    IndividualPointsRow,
    PointsClaimCreate,
    PointsClaimView,
    TeamPointsRow,
)

__all__ = [
    "ClaimNotFoundError",
    "ClaimStateError",
    "ContestNotFoundError",
    "DuplicateClaimError",
    "IndividualPointsRow",
    "InvalidClaimError",
    "NotTeamMemberError",
    "PointsClaimCreate",
    "PointsClaimView",
    "PointsError",
    "TeamPointsRow",
    "UnknownAwardError",
    "compute_award_points",
    "compute_points",
    "configure_session",
    "individual_leaderboard",
    "list_claims",
    "my_claims",
    "player_teams",
    "review_claim",
    "submit_claim",
    "team_leaderboard",
]
