# Rating 计算模块设计

> 关联：[需求文档](../需求文档.txt) · [比赛与记录](./03-比赛与记录模块.md) · [数据导入与加工](./04-数据导入与加工模块.md) · [数据导出与发布](./05-数据导出与发布模块.md) · [榜单](./07-榜单模块.md) · [比赛权重](./07-比赛权重.md)

---

## 1. 模块职责

- 定义 **Rating 数值**的计算接口（公式**待定**，先占位）
- 将 processed 事件流输入 Rating 引擎，产出各周期的 Rating 快照
- 算法与流水线**解耦**，通过 `RatingEngine` 插件实现

> **榜单模式、时间维度、输出文件结构**由 [榜单模块](./07-榜单模块.md) 负责。

---

## 2. Rating 计算（待定 · 扩展点）

### 2.1 设计原则

- 算法与流水线**解耦**，通过 `RatingEngine` 插件实现
- MVP 使用 **placeholder**：按简单规则生成可排序数值，便于联调前后端
- 正式算法确定后，只换 `backend/data/rating/` 下实现，不改 export 结构

### 2.2 引擎接口

```python
class RatingEngine(Protocol):
  name: str
  version: str

  def compute(
    self,
    events: list[RatingEvent],
    players: dict[str, Player],
    *,
    mode: Literal["formal_only", "all"],
    period: PeriodFilter,
  ) -> RatingSnapshot:
    ...
```

`PeriodFilter`：

```python
@dataclass
class PeriodFilter:
  type: Literal["career", "competition_year", "season"]
  id: str | int | None  # None for career
  start: date
  end: date
```

### 2.3 占位算法（placeholder_v0）

用于开发阶段，**非最终业务规则**：

1. 过滤：`mode` + `period` 时间窗 + `source_type`
2. 每条事件基础分 × **`weight / 100`**（权重见 [07-比赛权重](./07-比赛权重.md)）：
   - 校内训练：`weight` = division 查表（div1+2→100 … div3→60）
   - 正式赛：`weight` = `contest_type` 查表；允许 `weight_override` > 100
   - `team_xcpc` / `solo_xcpc`：由 rank、solved、penalty 算基础分
   - `oi`：由 rank、score 算基础分
   - oj_contest / oj_practice：单独默认权重（config `oj` 段）
3. 选手得分 = 事件分之和，或 Elo 式迭代（二期）

配置 `rating.engine: placeholder_v0`；权重表 `data/config/contest_weights.yaml`。

### 2.4 未来算法可考虑

| 方向 | 说明 |
|------|------|
| 加权 Elo | 正式赛权重高，训练赛/OJ 低 |
| 队内分摊 | 队伍赛事件按队员分配比例 |
| OJ 归一化 | 不同平台 Rating 映射到统一尺度 |
| 时间衰减 | 生涯榜对远古比赛降权 |

文档更新时替换本节，保持 `meta.rating_algorithm` 版本号。

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

*文档版本：v1.0 — 从原 06-Rating与榜单模块拆分。*