"""Rating 计算器：基类 + 按比赛类型继承（docs/06 §2）。

占位公式 placeholder_v0（docs/06 §2.5）——非最终业务规则，正式算法确定后只换对应子类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from xcpc_core.rating.models import RatingEvent


class BaseRatingCalculator(ABC):
    """计算器基类。每种比赛类型继承实现 ``compute_base_score``。"""

    source_type: str

    @abstractmethod
    def compute_base_score(self, event: RatingEvent) -> float:
        """从事件数据计算基础分。"""
        raise NotImplementedError

    def compute(self, event: RatingEvent) -> float:
        """模板方法：基础分 × 权重 / 100。"""
        base = self.compute_base_score(event)
        return base * event.weight / 100


class FormalCalculator(BaseRatingCalculator):
    """正式赛（XCPC 组队）。权重由 contest_type → contest_weights.yaml。"""

    source_type = "formal"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["rank"]
        total_teams = event.payload["total_teams"]
        solved = event.payload.get("solved", 0)
        return max(0, (total_teams - rank + 1) / total_teams * 1000 + solved * 50)


class TrainingTeamXcpcCalculator(BaseRatingCalculator):
    """组队 XCPC 训练赛：基础分按队员数均分。"""

    source_type = "training"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["rank"]
        team_count = event.payload["team_count"]
        solved = event.payload.get("solved", 0)
        size = max(event.payload.get("size", 1), 1)
        return max(0, (team_count - rank + 1) / team_count * 800 + solved * 30) / size


class TrainingSoloXcpcCalculator(BaseRatingCalculator):
    """个人 XCPC 训练赛。"""

    source_type = "training"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["rank"]
        player_count = event.payload["player_count"]
        solved = event.payload.get("solved", 0)
        return max(0, (player_count - rank + 1) / player_count * 800 + solved * 30)


class TrainingOiCalculator(BaseRatingCalculator):
    """OI 训练赛。"""

    source_type = "training"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["rank"]
        player_count = event.payload["player_count"]
        score = event.payload.get("score", 0)
        return max(0, (player_count - rank + 1) / player_count * 800 + score * 2)


class TrainingDispatcher(BaseRatingCalculator):
    """训练赛按 ``contest_format`` 路由到具体计算器。"""

    source_type = "training"

    def __init__(self) -> None:
        self._by_format: dict[str, BaseRatingCalculator] = {
            "team_xcpc": TrainingTeamXcpcCalculator(),
            "solo_xcpc": TrainingSoloXcpcCalculator(),
            "oi": TrainingOiCalculator(),
        }

    def compute_base_score(self, event: RatingEvent) -> float:
        calc = self._by_format.get(event.contest_format or "")
        if calc is None:
            raise ValueError(f"未知训练赛 format: {event.contest_format}")
        return calc.compute_base_score(event)


class ContestTeamCalculator(BaseRatingCalculator):
    """统一比赛·团队形式（placeholder_v0）：按重排名百分位，基础分按队员数均分。"""

    source_type = "contest"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["internal_rank"]
        n_recorded = event.payload["n_recorded"]
        solved = event.payload.get("solved", 0)
        size = max(event.payload.get("size", 1), 1)
        return max(0, (n_recorded - rank + 1) / n_recorded * 800 + solved * 30) / size


class ContestSoloCalculator(BaseRatingCalculator):
    """统一比赛·个人形式（placeholder_v0）。"""

    source_type = "contest"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["internal_rank"]
        n_recorded = event.payload["n_recorded"]
        solved = event.payload.get("solved", 0)
        return max(0, (n_recorded - rank + 1) / n_recorded * 800 + solved * 30)


class ContestOiCalculator(BaseRatingCalculator):
    """统一比赛·IOI 赛制（placeholder_v0）：按得分。"""

    source_type = "contest"

    def compute_base_score(self, event: RatingEvent) -> float:
        rank = event.payload["internal_rank"]
        n_recorded = event.payload["n_recorded"]
        score = event.payload.get("score", 0)
        return max(0, (n_recorded - rank + 1) / n_recorded * 800 + score * 2)


class ContestDispatcher(BaseRatingCalculator):
    """统一比赛按赛制×参与形式路由到具体计算器。"""

    source_type = "contest"

    def __init__(self) -> None:
        self._by_shape: dict[tuple[str, str], BaseRatingCalculator] = {
            ("icpc", "team"): ContestTeamCalculator(),
            ("icpc", "player"): ContestSoloCalculator(),
            ("ioi", "player"): ContestOiCalculator(),
        }

    def compute_base_score(self, event: RatingEvent) -> float:
        shape = (event.contest_format or "", event.payload.get("entity", "player"))
        calc = self._by_shape.get(shape)
        if calc is None:
            raise ValueError(f"未知比赛形态: {shape}")
        return calc.compute_base_score(event)


class OjContestCalculator(BaseRatingCalculator):
    """OJ 比赛：由 rating delta 计算。"""

    source_type = "oj_contest"

    def compute_base_score(self, event: RatingEvent) -> float:
        delta = event.payload.get("delta", 0)
        return max(0, delta)


class OjPracticeCalculator(BaseRatingCalculator):
    """OJ 做题：平台 Rating + 做题数。"""

    source_type = "oj_practice"

    def compute_base_score(self, event: RatingEvent) -> float:
        rating_numeric = event.payload.get("rating_numeric", 0)
        solve_count = event.payload.get("solve_count", 0)
        return rating_numeric * 0.5 + solve_count * 2
