---
name: team-manage
description: >-
  管理 xcpc-rating 队伍名册（增删改查、别名、按队员查找）。
  通过 team.api 或 xcpc-team CLI 操作 data/raw/teams/roster.json。
  在用户提到队伍、名册、建队、别名、team_id、member_key、队员查找时使用。
---

# 队伍管理

## 前置条件

1. 激活环境：`source ./setup_env.sh`（项目根目录）
2. 数据文件：`data/raw/teams/roster.json`

详细 API 见 [docs/team-module.md](../../docs/team-module.md)。

## 原则

- **必须通过 `team.api` 或 CLI**，不要手改 `roster.json`
- 编程 API 与 CLI 共用同一套逻辑
- 队伍身份由**队员集合**（`member_key`）决定，队名不参与
- 队员相同但队名不同 → 同一队伍，新队名追加到 `aliases`
- 换员 → 新队伍（新 `team_id`）
- `id` 省略时自动生成 `t001`、`t002`…（全局递增）
- **Formal Import 已集成**：导入比赛时自动调用 `resolve_team()` 查找或创建队伍

## 数据模型要点

| 字段 | 说明 |
|------|------|
| `id` | 队伍唯一 ID，如 `t001` |
| `member_key` | 规范键 `"p001|p002|p003"`（排序后拼接），名册中唯一 |
| `members` | 1-3 个 `player_id`，顺序无关 |
| `size` | 派生自 `len(members)` |
| `aliases` | 历次使用过的队名列表，去重 |

唯一约束：`member_key` 不可重复（同一组队员只能有一条记录）。

## 工作流

```
任务进度：
- [ ] 1. 确认操作类型（查 / 增 / 改别名 / 删）
- [ ] 2. 查重（find_by_members）避免重复建队
- [ ] 3. 执行 API 或 CLI
- [ ] 4. 汇报变更（team_id、受影响字段）
```

## 编程 API（推荐）

```python
from team import (
    create_team,
    delete_team,
    find_by_members,
    get_team,
    list_teams,
    update_team,
)
from team.models import TeamCreate, TeamUpdate
from team.service import TeamService
from utils import Plog
```

### 查询

```python
# 列出所有队伍
teams = list_teams()

# 按 ID 查询
team = get_team("t001")

# 按队员查找（顺序无关）
team = find_by_members(["p003", "p001", "p002"])
if team:
    print(team.id, team.aliases)  # t001 ['泠鸢yousa从小就不迷路']
```

### 新建

```python
plog = Plog(name="xcpc-team")
team = create_team(
    TeamCreate(
        members=["p001", "p002", "p003"],
        aliases=["测试队"],
    ),
)
plog.info("新建队伍", team_id=team.id, aliases=team.aliases)
plog.close()
```

### 追加别名

```python
# 方式一：update_team
team = update_team("t001", TeamUpdate(alias="新队名"))

# 方式二：add_alias（直接操作 service）
from team.service import TeamService
service = TeamService()
team = service.add_alias("t001", "新队名")
```

### 删除

```python
delete_team("t001")  # 物理删除，慎用
```

## CLI

```bash
# 列出所有队伍
xcpc-team list [--json]

# 查询单个队伍
xcpc-team get t001 [--json]

# 按队员查找
xcpc-team find --members p001 p002 p003 [--json]

# 新建队伍
xcpc-team create --members p001 p002 p003 --aliases "测试队" "测试" [--json]

# 追加别名
xcpc-team update t001 --alias "新队名" [--json]

# 删除队伍
xcpc-team delete t001 [--json]
```

未安装入口脚本时：`python -m team.cli <子命令>`（需已 `source ./setup_env.sh`）。

## 常见场景

| 场景 | 做法 |
|------|------|
| 导入比赛后队伍自动建档 | 由 `importer.resolve_team()` 调用 `find_by_member_key` + `create_team` |
| 同一队换了队名 | 队员相同 → `add_alias` 追加新队名，不新建 |
| 队员换人 | 成员集合变了 → 创建新队伍 |
| 导入时发现已有队伍 | 自动匹配 `member_key`，队名不同则追加 alias |
| 查找某队员所在队伍 | `find_by_members(["p001"])` 返回该队员所在的队伍（1 人队） |

## 与 Formal Import 的协作

正式赛导入（`backend/data/import/formal.py`）中的 `resolve_team()` 已集成队伍管理：

```python
def resolve_team(player_ids, team_name, store):
    member_key = make_member_key(player_ids)
    service = TeamService(store)
    team = service.find_by_member_key(member_key)
    if team:
        # 队员相同、队名不同 → 追加别名
        if team_name and team_name.strip() not in team.aliases:
            service.add_alias(team.id, team_name.strip())
        return team.id
    # 新队伍 → 自动建档
    created = service.create_team(TeamCreate(
        members=player_ids,
        aliases=[team_name.strip()] if team_name and team_name.strip() else [],
    ))
    return created.id
```

## 异常处理

| 异常 | 处理 |
|------|------|
| `TeamNotFoundError` | 核对 `team_id` |
| `TeamAlreadyExistsError` | `member_key` 冲突，队员已在名册中；应追加别名而非新建 |
| `TeamValidationError` | ID 冲突或别名为空 |

## 修改代码时

- API：`backend/data/team/api.py`
- 业务逻辑：`backend/data/team/service.py`
- 数据模型：`backend/data/team/models.py`
- 存储层：`backend/data/team/store.py`
- CLI：`backend/data/team/cli.py`
- 测试：`pytest backend/data/tests/test_team_crud.py`

## 禁止事项

- 不要直接编辑 `data/raw/teams/roster.json`
- 未经用户要求不要 `git commit`
- 不要通过 `update_team` 修改 `members`（换员应创建新队）