---
name: formal-import
description: >-
  导入 xcpc-rating 正式比赛数据（当前支持 XCPC.io xlsx，source_format=xcpcio_xlsx）。
  解析榜单、按本校 Organization 过滤、自动建档缺失队员、写入 raw；
  支持 add_formal_team 手动补录未挂靠本校的打星队。
  在用户提到正式赛导入、xcpcio、xlsx 榜单、formal import、补录队伍、省赛/区域赛成绩入库时使用。

---

# 正式赛导入

## 前置条件

1. 激活环境：`source ./setup_env.sh`（项目根目录）
2. 确认 `data/config/school.yaml` 中 `organizations` 与 `player_defaults.grade` 正确
3. 确认 `data/config/contest_weights.yaml` 含目标 `contest_type`

## 支持的源格式

| `source_format` | 文件 | 实现 |
|-----------------|------|------|
| `xcpcio_xlsx` | XCPC.io 导出 `.xlsx` | `importer.import_formal_xcpcio_xlsx` |

详细字段说明见 [docs/backend-formal-import-xcpcio.md](../../docs/backend-formal-import-xcpcio.md)。

## 工作流

```
任务进度：
- [ ] 1. 确认 xlsx 路径与比赛元信息
- [ ] 2. 选择 contest_type 与 contest_id
- [ ] 3. （可选）先 parse 预览本校队伍数
- [ ] 4. 执行 import
- [ ] 5. （可选）`add_formal_team` 补录未挂靠本校的打星队
- [ ] 6. 汇报结果并处理 unmatched
```

### 1. 收集参数

向用户确认或从文件名/标题推断：

| 参数 | 说明 | 示例 |
|------|------|------|
| `path` | xlsx 绝对或相对路径 | `第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx` |
| `contest_id` | 唯一 ID，建议 `{年}_{简称}` | `2026_sichuan_provincial` |
| `date` | 比赛日期 | `2026-05-18` |
| `contest_type` | 查权重表 | `icpc_provincial`（省赛）、`icpc_regional`（区域赛） |

`contest_type` 枚举见 `data/config/contest_weights.yaml` 的 `formal_types`。

### 2. 预览解析（推荐）

```python
from importer import parse_xcpcio_xlsx
from importer.config import load_school_organizations

parsed = parse_xcpcio_xlsx(
    "比赛文件.xlsx",
    school_organizations=load_school_organizations(),
)
print(parsed.title, parsed.total_teams, len(parsed.standings))
for row in parsed.standings:
    print(row.rank, row.team_name, row.members, row.award)
```

### 3. 执行导入

**必须通过 `importer` API**，不要手改 `data/raw/formal/*.json`。

```python
from datetime import date

from importer import FormalImportParams, import_formal_xcpcio_xlsx
from importer.config import load_school_organizations
from utils import Plog

plog = Plog(name="formal-import")
result = import_formal_xcpcio_xlsx(
    "比赛文件.xlsx",
    FormalImportParams(
        contest_id="2026_sichuan_provincial",
        date=date(2026, 5, 18),
        contest_type="icpc_provincial",
        school_organizations=load_school_organizations(),
        # auto_create_players=True,   # 默认开启
        # default_grade=0,       # 覆盖 school.yaml 中的默认入学年（0 表示未设置）
    ),
    plog=plog,
)
plog.close()
```

### 5. 手动补录队伍

打星队或外校挂靠导致 xlsx 自动导入遗漏时，在**已完成 import** 后使用 `add_formal_team` 追加单支队伍到 raw 文件。

从 xlsx **`所有队伍`** 工作表查找该队（`Organization` 可能不是本校），确认 `rank` / `solved` / `penalty` / `Unofficial`。

```python
from importer import AddFormalTeamParams, add_formal_team
from utils import Plog

plog = Plog(name="formal-import")
result = add_formal_team(
    AddFormalTeamParams(
        contest_id="2026_sichuan_provincial",
        team_name="左脑攻击右脑，暴力代替思考",
        member_names=["李汶航", "陈子川", "滕召宇"],
        rank=212,
        solved=2,
        penalty=122,
        unofficial=True,
        note="打星队，Organization 未挂靠本校",
        # award="bronze",  # 可省略，按 raw 中 award_thresholds 推算
    ),
    plog=plog,
)
plog.close()
```

- 写入已有 `data/raw/formal/{basename}.json` 的 `standings`，标记 `manually_added: true`
- `award` 可省略，按文件中 `award_thresholds` 推算；未达奖线会报错
- 同队员 `team_id` 已存在则覆盖更新
- 自动建档队员逻辑与 import 相同

### 6. 汇报结果

向用户说明：

- `result.total_teams`：全场队伍数
- `result.school_teams_count`：本校队伍总数（含未获奖）
- `result.standings_imported`：写入成绩条数（仅金/银/铜）
- `result.players_created`：自动新建选手（姓名、`player_id`）
- `result.unmatched_players` / `result.unmatched_teams`：需人工处理

写入位置：

- `data/raw/formal/{basename}.json`
- `data/raw/players/roster.json`（自动建档时更新）

## xcpcio_xlsx 要点

- **`所有队伍`** → `total_teams`、`total_problems`（A/B/C… 题号列数）+ 本校队伍成绩
- **`正式组`** → 推算金/银/铜奖线（有 `Medal` 列时优先）
- 无 `Medal` 时按全场 10%/20%/30% 推算奖线
- 仅记录金/银/铜获奖队伍，忽略未获奖与优胜
- `Organization` **精确匹配** `school.yaml`
- 不需要打星队时设 `include_unofficial=False`

## 异常处理

| 情况 | 处理 |
|------|------|
| 本校队伍数为 0 | 检查 `school.yaml` 的 `organizations` 是否与 xlsx 中 `Organization` 一致 |
| 本校无获奖队伍 | 不会写入 standings；检查奖线或本校成绩 |
| `unmatched_players`（姓名歧义） | 在 roster 中消歧或补 `aliases`，勿自动建档 |
| `unmatched_teams` | 查看 `reason`；修复名册后重新 import（同 `contest_id` 会覆盖） |
| 打星队未挂靠本校、自动导入遗漏 | 从 xlsx `所有队伍` 查成绩后调用 `add_formal_team` |

## 修改代码时

- 解析逻辑：`backend/data/import/xcpcio_xlsx.py`
- 获奖计算：`backend/data/import/awards.py`
- 导入编排：`backend/data/import/formal.py`
- 队员解析/建档：`backend/data/import/players.py`
- 测试：`pytest backend/data/import/tests`

## 禁止事项

- 不要爬取办赛网站；只处理用户提供的 xlsx/raw 文件
- 不要跳过 `school.yaml` 用子串匹配学校
- 未经用户要求不要 `git commit`
