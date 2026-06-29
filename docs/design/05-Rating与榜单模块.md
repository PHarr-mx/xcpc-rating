# Rating 与榜单模块设计

> 关联：[需求文档](../需求文档.txt) · [比赛与记录](./03-比赛与记录模块.md) · [数据流水线](./04-数据流水线模块.md)

---

## 1. 模块职责

- 定义 **Rating 数值**的计算接口（公式**待定**，先占位）
- 定义两种**榜单模式**与三种**时间维度**
- 将 processed 事件流聚合为各周期榜单与选手历史

---

## 2. 榜单模式

| 模式 | `mode` 键 | 包含的数据源 |
|------|-----------|--------------|
| **仅正式比赛** | `formal_only` | `source_type = formal` |
| **全部数据** | `all` | `formal` + `training` + `oj_contest` + `oj_practice` |

前端切换模式时，加载 `public/ratings/{mode}/...` 下对应文件。

---

## 3. 时间维度

### 3.1 生涯（career）

- **定义**：该选手自首次参赛起至当前的全部相关记录
- **文件**：`ratings/{mode}/career.json`
- **无** `period_id` 后缀，或统一用 `career`

### 3.2 赛年（competition_year）

- **定义**：当年 **9 月 1 日** 至次年 **8 月 31 日**（含端点，UTC+8 或配置时区）
- **标签**：`2025赛年` → `start=2025-09-01`, `end=2026-08-31`
- **文件**：`ratings/{mode}/year_{id}.json`，如 `year_2025.json`

判定规则：

```python
def competition_year(d: date) -> int:
    if d.month >= 9:
        return d.year
    return d.year - 1
```

### 3.3 赛季（season）

与**校内学期、寒暑假**对应，共四类：

| 季节 | `kind` | 含义 | 典型月份（可配置） |
|------|--------|------|-------------------|
| 秋学期 | `autumn_semester` | 秋季学期 | 9 月 – 次年 1 月 |
| 寒假 | `winter_break` | 寒假 | 2 月 |
| 春学期 | `spring_semester` | 春季学期 | 3 月 – 6 月 |
| 暑假 | `summer_break` | 暑假 | 7 月 – 8 月 |

**需求对应**：

- **春秋赛季** → 秋学期 + 春学期
- **冬夏赛季** → 寒假 + 暑假

### 3.4 赛季配置示例 `config.yaml`

```yaml
calendar:
  timezone: Asia/Shanghai
  competition_year:
    start_month: 9
    start_day: 1
  seasons:
    - kind: autumn_semester
      label_template: "{year} 秋季学期"
      start: { month: 9, day: 1 }
      end: { month: 1, day: 31, next_year: true }
    - kind: winter_break
      label_template: "{year} 寒假"
      start: { month: 2, day: 1 }
      end: { month: 2, day: 28 }
    - kind: spring_semester
      label_template: "{year} 春季学期"
      start: { month: 3, day: 1 }
      end: { month: 6, day: 30 }
    - kind: summer_break
      label_template: "{year} 暑假"
      start: { month: 7, day: 1 }
      end: { month: 8, day: 31 }
```

`season_id` 示例：`2025-秋学期`、`2025-春学期`。  
每年赛年内顺序：秋学期 → 寒假 → 春学期 → 暑假。

### 3.5 时间与模式组合

前端筛选器：

```
[ 仅正式赛 | 全部数据 ]  ×  [ 生涯 | 2025赛年 | 2025秋学期 ▼ ]
```

每个组合对应一个预生成的 JSON 文件（或前端按需加载 catalog 列出的路径）。

---

## 4. Rating 计算（待定 · 扩展点）

### 4.1 设计原则

- 算法与流水线**解耦**，通过 `RatingEngine` 插件实现
- MVP 使用 **placeholder**：按简单规则生成可排序数值，便于联调前后端
- 正式算法确定后，只换 `backend/data/rating/` 下实现，不改 export 结构

### 4.2 引擎接口

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

### 4.3 占位算法（placeholder_v0）

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

### 4.4 未来算法可考虑

| 方向 | 说明 |
|------|------|
| 加权 Elo | 正式赛权重高，训练赛/OJ 低 |
| 队内分摊 | 队伍赛事件按队员分配比例 |
| OJ 归一化 | 不同平台 Rating 映射到统一尺度 |
| 时间衰减 | 生涯榜对远古比赛降权 |

文档更新时替换本节，保持 `meta.rating_algorithm` 版本号。

---

## 5. 输出结构

### 5.1 榜单行 `ratings/{mode}/{period_key}.json`

```json
{
  "meta": {
    "mode": "formal_only",
    "period_type": "season",
    "period_id": "2025-春学期",
    "period_label": "2025 春季学期",
    "start": "2026-03-01",
    "end": "2026-06-30",
    "algorithm": "placeholder_v0",
    "generated_at": "2026-06-29T08:00:00Z"
  },
  "rows": [
    {
      "rank": 1,
      "player_id": "p20230042",
      "name": "张三",
      "grade_label": "2023级",
      "rating": 2456,
      "event_count": 15,
      "delta_recent": 32
    }
  ]
}
```

### 5.2 选手历史 `players/{id}.json` 内 `rating_history`

按时间序列，记录每次 Rating 变动及来源：

```json
{
  "date": "2026-04-12",
  "rating_before": 2424,
  "rating_after": 2456,
  "delta": 32,
  "mode_scope": "all",
  "source_type": "formal",
  "source_id": "formal_2026_spring_invitational",
  "source_title": "2026 春季校赛"
}
```

生涯历史用 `all` + 全时间窗；赛年/赛季页可过滤展示子集。

### 5.3 排名规则

- 主排序：`rating` 降序
- 同分：`player_id` 字典序（稳定、可复现）
- 排名连续：1, 2, 2, 4（或跳号，在 meta 注明 `tie_break` 策略）

---

## 6. 计算流程

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

## 7. 与正式赛「仅校内队」的关系

- `formal_only` 模式：事件流中仅保留 `source_type=formal`，且成绩来自本校队伍
- `total_teams` 仍参与占位算法中的难度估计
- 外校队伍**从不**出现在榜单行中

---

## 8. 前端交互（摘要）

详见 [06-前端展示模块](./06-前端展示模块.md)：

- 顶部：模式切换 + 时间维度 Tab/下拉
- 表格：排名、姓名、年级、Rating、近期变化
- 选手详情：Rating 折线图（可按模式过滤曲线）

---

## 9. 开放问题

| 项 | 状态 | 说明 |
|----|------|------|
| Rating 正式公式 | **待定** | 当前 placeholder_v0 |
| 是否展示「置信度」 | 待定 | 参赛场次数过少时标注 |
| 赛年榜是否包含暑假 | 是 | 赛年 = 四个赛季之和 |
| 跨赛年选手如何显示年级 | 展示用入学年 | 与赛年正交 |

---

*文档版本：v1.0*
