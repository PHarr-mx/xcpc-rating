# Rating 计算模块设计

> 关联：[需求文档](../需求文档.txt) · [比赛与记录](./03-比赛与记录模块.md) · [数据导入与加工](./04-数据导入与加工模块.md) · [数据导出与发布](./05-数据导出与发布模块.md) · [榜单](./07-榜单模块.md) · [比赛权重](./07-比赛权重.md)

---

## 1. 模块职责

- 定义 **Rating 数值**的计算接口：基类 `BaseRatingCalculator` + 按比赛类型继承
- 将 processed 事件流输入 Rating 引擎，按 `source_type` 分发到对应计算器
- 算法与流水线**解耦**，每种比赛类型可独立替换公式

> **榜单模式、时间维度、输出文件结构**由 [榜单模块](./07-榜单模块.md) 负责。

---

## 2. Rating 计算架构

### 2.1 设计原则

- 算法与流水线**解耦**，通过 `RatingEngine` 编排，各比赛类型计算器独立实现
- **基类 + 继承**：`BaseRatingCalculator` 定义统一接口，每种比赛类型继承实现自己的评分逻辑
- MVP 使用 **placeholder** 公式，正式算法确定后只换对应子类实现，不改 export 结构

### 2.2 基类 `BaseRatingCalculator`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass
class PeriodFilter:
    type: Literal["career", "competition_year", "season"]
    id: str | int | None  # None for career
    start: date
    end: date


class BaseRatingCalculator(ABC):
    """Rating 计算器基类。

    每种比赛类型（formal / training / oj_contest / oj_practice）
    继承此类，实现自己的 compute_base_score() 方法。
    """

    source_type: str  # "formal" | "training" | "oj_contest" | "oj_practice"

    @abstractmethod
    def compute_base_score(self, event: RatingEvent) -> float:
        """从事件数据计算基础分。

        子类根据自身的赛制与成绩字段实现：
        - XCPC 类：由 rank、solved、penalty 推导
        - OI 类：由 rank、score 推导
        - OJ 类：由 rating delta / rating_numeric + solve_count 推导
        """
        ...

    def compute(self, event: RatingEvent) -> float:
        """模板方法：基础分 × 权重 / 100。"""
        base = self.compute_base_score(event)
        return base * event.weight / 100
```

### 2.3 继承体系

```
BaseRatingCalculator (ABC)
├── FormalCalculator               source_type = "formal"
│     基础分 = f(rank, total_teams, solved, penalty)
│     权重   = contest_type → contest_weights.yaml · formal_types
│
├── TrainingCalculator (基类)       source_type = "training"
│   ├── TrainingTeamXcpcCalculator   format = "team_xcpc"
│   │     基础分 = f(rank, solved, penalty)
│   ├── TrainingSoloXcpcCalculator   format = "solo_xcpc"
│   │     基础分 = f(rank, solved, penalty)
│   └── TrainingOiCalculator         format = "oi"
│         基础分 = f(rank, score)
│     权重 = division → contest_weights.yaml · training_divisions
│
├── OjContestCalculator            source_type = "oj_contest"
│     基础分 = f(rating_delta)
│     权重   = oj.contest_default
│
└── OjPracticeCalculator           source_type = "oj_practice"
      基础分 = f(rating_numeric, solve_count)
      权重   = oj.practice_default
```

#### FormalCalculator

```python
class FormalCalculator(BaseRatingCalculator):
    source_type = "formal"

    def compute_base_score(self, event: RatingEvent) -> float:
        # 由 rank、total_teams、solved、penalty 计算基础分
        # total_teams 参与难度估计：规模越大、排名越靠前，基础分越高
        ...
```

- 仅处理 `format = "team_xcpc"`
- 权重由 `contest_type` 查 `contest_weights.yaml` → `formal_types`
- 支持 `weight_override`（>100 的极少数场次）

#### TrainingCalculator 及其子类

```python
class TrainingCalculator(BaseRatingCalculator):
    source_type = "training"

    def __init__(self, division: str):
        self.division = division  # 权重由 division 查表

    def compute(self, event: RatingEvent) -> float:
        # 训练赛的 weight 在 event 中已由导入阶段写入
        return super().compute(event)


class TrainingTeamXcpcCalculator(TrainingCalculator):
    """组队 XCPC 训练赛。"""
    def compute_base_score(self, event: RatingEvent) -> float:
        # 由 rank、solved、penalty 计算基础分
        # 队员分摊：基础分按队员数均分（或每人全额，可配置）
        ...


class TrainingSoloXcpcCalculator(TrainingCalculator):
    """个人 XCPC 训练赛。"""
    def compute_base_score(self, event: RatingEvent) -> float:
        # 与 team_xcpc 公式相同，但无需分摊
        ...


class TrainingOiCalculator(TrainingCalculator):
    """OI 训练赛。"""
    def compute_base_score(self, event: RatingEvent) -> float:
        # 由 rank、score 计算基础分
        ...
```

| 子类 | format | 成绩字段 | 队伍分摊 |
|------|--------|---------|---------|
| `TrainingTeamXcpcCalculator` | `team_xcpc` | rank, solved, penalty | 按队员数均分 |
| `TrainingSoloXcpcCalculator` | `solo_xcpc` | rank, solved, penalty | 无需 |
| `TrainingOiCalculator` | `oi` | rank, score | 无需 |

#### OjContestCalculator / OjPracticeCalculator

```python
class OjContestCalculator(BaseRatingCalculator):
    source_type = "oj_contest"

    def compute_base_score(self, event: RatingEvent) -> float:
        # 由 rating_delta 计算基础分
        # 若 delta 缺失，由 rating_after - rating_before 推算
        ...


class OjPracticeCalculator(BaseRatingCalculator):
    source_type = "oj_practice"

    def compute_base_score(self, event: RatingEvent) -> float:
        # 由 rating_numeric + solve_count 计算基础分
        ...
```

### 2.4 与 RatingEngine 的关系

```python
class RatingEngine:
    """编排 Rating 计算流程，持有各类型计算器。"""

    def __init__(self):
        self.calculators: dict[str, BaseRatingCalculator] = {
            "formal": FormalCalculator(),
            "training": TrainingDispatcher(),  # 内部按 format 分发
            "oj_contest": OjContestCalculator(),
            "oj_practice": OjPracticeCalculator(),
        }

    def compute(
        self,
        events: list[RatingEvent],
        players: dict[str, Player],
        *,
        mode: Literal["formal_only", "all"],
        period: PeriodFilter,
    ) -> RatingSnapshot:
        scores: dict[str, float] = {}
        for event in self._filter(events, mode, period):
            calc = self.calculators[event.source_type]
            score = calc.compute(event)
            scores[event.player_id] = scores.get(event.player_id, 0) + score
        return self._build_snapshot(scores, players)
```

`TrainingDispatcher` 根据 `event.contest_format` 路由到对应的 `TrainingXxxCalculator`。

### 2.5 占位公式（placeholder_v0）

用于开发阶段，**非最终业务规则**。各子类的 `compute_base_score()` 使用以下占位公式：

| 计算器 | 占位公式 |
|--------|---------|
| `FormalCalculator` | `max(0, (total_teams - rank + 1) / total_teams * 1000 + solved * 50)` |
| `TrainingTeamXcpcCalculator` | `max(0, (team_count - rank + 1) / team_count * 800 + solved * 30) / size` |
| `TrainingSoloXcpcCalculator` | `max(0, (player_count - rank + 1) / player_count * 800 + solved * 30)` |
| `TrainingOiCalculator` | `max(0, (player_count - rank + 1) / player_count * 800 + score * 2)` |
| `OjContestCalculator` | `max(0, delta)` |
| `OjPracticeCalculator` | `rating_numeric * 0.5 + solve_count * 2` |

配置 `rating.engine: placeholder_v0`；权重表 `data/config/contest_weights.yaml`。

### 2.6 未来算法可考虑

| 方向 | 说明 |
|------|------|
| 加权 Elo | 正式赛权重高，训练赛/OJ 低；按时间序迭代更新 |
| 队内分摊 | 队伍赛事件按队员贡献比例分配（目前均分） |
| OJ 归一化 | 不同平台 Rating 映射到统一尺度 |
| 时间衰减 | 生涯榜对远古比赛降权 |

文档更新时替换 §2.5 各子类公式，保持 `meta.rating_algorithm` 版本号。

---

## 3. 计算流程

```
rating_events.json (sorted by date)
        │
        ▼
for mode in [formal_only, all]:
  for period in catalog.all_periods():
    events_filtered = filter(events, mode, period)
    snapshot = engine.compute(events_filtered, ...)
    write ratings/{mode}/{period_key}.json
        │
        ▼
for each player:
  aggregate history → players/{id}.json
```

全量重算；数据量小（校内规模）时可接受。后期可对 `period` 做增量缓存。

---

## 4. 与正式赛「仅校内队」的关系

- `formal_only` 模式：事件流中仅保留 `source_type=formal`，且成绩来自本校队伍
- `total_teams` 仍参与占位算法中的难度估计
- 外校队伍**从不**出现在榜单行中

---

## 5. 开放问题

| 项 | 状态 | 说明 |
|----|------|------|
| Rating 正式公式 | **待定** | 当前 placeholder_v0 |
| 是否展示「置信度」 | 待定 | 参赛场次数过少时标注 |
| 赛年榜是否包含暑假 | 是 | 赛年 = 四个赛季之和 |

---

*文档版本：v2.0 — 重构为基类+继承体系；各比赛类型独立计算器。*