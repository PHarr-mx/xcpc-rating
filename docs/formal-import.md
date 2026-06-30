# 正式赛导入

> **状态**：✅ 已实现  
> **代码路径**：`backend/data/import/`  
> **数据文件**：`data/raw/formal/{contest_id}.json`  
> **支持格式**：`xcpcio_xlsx`（XCPC.io 导出的 `.xlsx` 榜单）

---

## 1. 模块职责

- 解析 XCPC.io 导出的 `.xlsx` 榜单文件
- 过滤本校队伍，计算奖牌线
- 匹配选手身份（自动创建或手动关联）
- 写入 raw JSON 文件
- 支持手动追加打星队伍

---

## 2. 数据流

```
xlsx 文件
  → xcpcio_xlsx.py（openpyxl 解析，过滤本校组织）
  → awards.py（计算奖牌线）
  → formal.py（匹配选手、生成 team_id、写 raw JSON）
  → players.py（resolve 选手名 → 查 roster 或自动创建）
  → weights.py（查 contest_weights.yaml）
  → formal_store.py（读写 raw/formal/ 目录）
```

---

## 3. xlsx 文件结构

| 工作表 | 用途 |
|--------|------|
| `所有队伍` | 统计 `total_teams`、`total_problems`；本校队伍成绩来源（含打星队 `Unofficial=Y`） |
| `正式组` | 读取全场 `Medal` 列，推算金/银/铜奖线 |
| `女生组` / `高职组` | 默认不导入 |

第 1 行：比赛标题；第 2 行：表头（`Rank`, `Organization`, `Team`, `Solved`, `Penalty`, `Member1`…`Member3`, `Unofficial` 等）。

---

## 4. 获奖计算

1. 从 **`正式组`** 读取全场获奖信息（`Medal` 列），取各奖项最弱队伍的 `(solved, penalty)` 作为金/银/铜奖线
2. 若正式组无获奖信息，则按 **`所有队伍`** 全场排名推算：金奖线 10%、银奖线 20%、铜奖线 30%
3. 在 **`所有队伍`** 中过滤本校队伍，按奖线比较 `solved` / `penalty` 计算获奖等级
4. **仅写入**获得金/银/铜的队伍；未获奖与优胜（honorable）均不记录

比较规则：解题数更多者优先；解题数相同时罚时更少者优先。

---

## 5. 本校过滤

从 `data/config/school.yaml` 读取 `organizations`，**精确匹配** `Organization` 列：

```yaml
# data/config/school.yaml
organizations:
  - 电子科技大学
```

不会匹配「电子科技大学成都学院」等子串学校。

默认包含 `Unofficial=Y` 的打星队（来自 `所有队伍` 工作表）；设为 `include_unofficial=False` 时跳过。

---

## 6. 队员自动建档

默认 `auto_create_players=True`：本校过滤后的队伍中，若队员在 `roster.json` 中不存在，**自动新建选手**并写入名册。

- 入学年默认来自 `data/config/school.yaml` 的 `player_defaults.grade`（`0` = 未设置）
- 可用 `FormalImportParams.default_grade` 覆盖
- 姓名匹配到多名选手时**不会**自动建档，记入 `unmatched_players`
- 关闭自动建档：`auto_create_players=False`

---

## 7. Team ID 生成

Team ID 基于队员集合的哈希：

```python
member_key = "|".join(sorted(player_ids))
digest = hashlib.sha256(member_key.encode()).hexdigest()[:8]
team_id = f"t_{digest}"
```

同一组人无论队名如何变化，ID 不变；换任意一人，ID 改变。

---

## 8. Python API

### 8.1 完整导入

```python
from datetime import date
from importer import FormalImportParams, import_formal_xcpcio_xlsx
from importer.config import load_school_organizations
from utils import Plog

plog = Plog(name="import")

result = import_formal_xcpcio_xlsx(
    "第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx",
    FormalImportParams(
        contest_id="2026_sichuan_provincial",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        school_organizations=load_school_organizations(),
    ),
    plog=plog,
)
plog.close()
```

### 8.2 仅解析（不写 raw）

```python
from importer import parse_xcpcio_xlsx

parsed = parse_xcpcio_xlsx(path, school_organizations=["电子科技大学"])
print(parsed.total_teams, parsed.total_problems)
```

### 8.3 FormalImportParams

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `contest_id` | str | ✅ | 比赛唯一标识，如 `2026_sichuan_provincial` |
| `date` | date | ✅ | 比赛日期 |
| `contest_type` | str | ✅ | 比赛类型，查权重表（如 `icpc_provincial`） |
| `format` | str | 否 | 默认 `team_xcpc` |
| `school_organizations` | list[str] | ✅ | 本校组织名称列表 |
| `standings_sheet` | str | 否 | 默认 `正式组` |
| `total_teams_sheet` | str | 否 | 默认 `所有队伍` |
| `include_unofficial` | bool | 否 | 默认 `True` |
| `auto_create_players` | bool | 否 | 默认 `True` |
| `default_grade` | int | 否 | 覆盖配置文件中的默认年级 |
| `weight_override` | int | 否 | 覆盖权重（>100 的特殊场次） |
| `weight_override_reason` | str | 否 | 权重覆盖原因 |

### 8.4 FormalImportResult

| 字段 | 说明 |
|------|------|
| `contest_id` | 比赛 ID |
| `title` | 比赛标题 |
| `total_teams` | 全场队伍数 |
| `school_teams_count` | 本校队伍总数 |
| `standings_imported` | 成功导入的队伍数 |
| `players_created` | 自动新建的选手列表 |
| `unmatched_players` | 无法匹配的选手 |
| `unmatched_teams` | 无法导入的队伍 |
| `raw_path` | 写入的 raw 文件路径 |
| `source_file` | raw 文件相对路径 |

---

## 9. 手动补录单支队伍

适用于打星队或 `Organization` 未挂靠本校、自动 import 未收录的获奖队伍。须先完成该场比赛的 import。

```python
from importer import AddFormalTeamParams, add_formal_team

add_formal_team(AddFormalTeamParams(
    contest_id="2026_sichuan_provincial",
    team_name="队名",
    member_names=["队员甲", "队员乙", "队员丙"],
    rank=212,
    solved=2,
    penalty=122,
    unofficial=True,
))
```

- 追加到 `data/raw/formal/{contest_id}.json` 的 `standings`，并标记 `manually_added: true`
- `award` 可省略，按 raw 内 `award_thresholds` 推算；也可显式指定 `gold` / `silver` / `bronze`
- 同 `team_id`（队员组合相同）已存在则覆盖

---

## 10. 导入结果

1. 写入 `data/raw/formal/{contest_id}.json`（比赛元信息、成绩、未匹配记录）
2. 自动建档时更新 `data/raw/players/roster.json`
3. `result.players_created` 列出本次自动新建的选手
4. `result.unmatched_players` / `result.unmatched_teams` 同时写入 raw 文件对应字段

### 10.1 Raw 文件结构

```json
{
  "contest_id": "2026_sichuan_provincial",
  "source_format": "xcpcio_xlsx",
  "title": "第十八届四川省大学生程序设计竞赛 - 正式赛",
  "date": "2026-05-18",
  "contest_type": "icpc_provincial",
  "format": "team_xcpc",
  "total_teams": 312,
  "total_problems": 12,
  "school_teams_count": 11,
  "school_teams_awarded": 8,
  "award_thresholds": {
    "gold": [5, 519],
    "silver": [3, 131],
    "bronze": [2, 211],
    "source": "formal_medals"
  },
  "competition_year": 2025,
  "season": "2026-春学期",
  "contest_type_label": "ICPC 省赛",
  "format_label": "组队 XCPC",
  "rated": true,
  "weight": 70,
  "weight_source": "config",
  "standings": [
    {
      "team_id": "t_23db55ea",
      "team_name": "队名",
      "member_names": ["队员1", "队员2", "队员3"],
      "player_ids": ["p001", "p002", "p003"],
      "size": 3,
      "rank": 7,
      "school_rank": 5,
      "award": "gold",
      "solved": 5,
      "penalty": 519,
      "unofficial": false
    }
  ],
  "unmatched_players": [],
  "unmatched_teams": []
}
```

---

## 11. 权重配置

`contest_type` 权重从 `data/config/contest_weights.yaml` 自动填充。详见 [contest-weights.md](contest-weights.md)。