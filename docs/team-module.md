# 队伍模块

> **状态**：✅ 已实现  
> **代码路径**：`backend/data/team/`  
> **数据文件**：`data/raw/teams/roster.json`

---

## 1. 模块职责

- 队伍的**增删改查**（编程 API + CLI 双入口）
- 以**队员集合**识别队伍身份，队名不参与身份判定
- 作为 Rating 计算、比赛成绩引用的**参赛单元**

---

## 2. 核心概念

### 2.1 队伍身份：队员集合（Member Set）

**核心规则**：

| 规则 | 说明 |
|------|------|
| 同一性 | `members` 中 `player_id` **完全相同**（与顺序无关）→ 同一支队伍 |
| 换员 | 任意一人不同 → **另一支队伍**（新 `team_id`） |
| 队名 | **不参与**身份判定；同名不同人、同人不同名，均允许 |
| 人数 | `1`（单挑）、`2`（双打）、`3`（标准队），均合法 |

```
{张三}               → 队伍 A
{张三, 李四}         → 队伍 B
{张三, 李四, 王五}   → 队伍 C

同 {张三, 李四, 王五}，比赛 A 叫「三大队」、比赛 B 叫「无敌队」→ 仍是队伍 C
{张三, 李四, 赵六}   → 队伍 D（王五 换成 赵六，成员集合变了）
```

### 2.2 队名（Aliases）

- 存储在 `aliases[]`（累积所有队名）
- **不唯一**、不强制与 `team_id` 一一对应
- 队员相同但队名不同 → 追加到 `aliases`，不新建队伍

### 2.3 长期实体

- 同一 `member_key` 可跨多个**赛年 / 赛季**参赛，仍是同一 `team_id`
- **赛年 / 赛季**由比赛 `date` 推导，不写在队伍实体上

---

## 3. 数据模型

### 3.1 Team（队伍）

```python
# backend/data/team/models.py

class Team(TeamBase):
    id: str                          # t001, t002, ...（sequential）
    member_key: str                  # "p001|p002|p003"（排序后拼接）
    members: list[str]               # 1-3 个 player_id
    size: int                        # 1-3，派生自 len(members)
    aliases: list[str]               # 历次使用过的队名列表
    created_at: date | None = None
    updated_at: date | None = None
```

### 3.2 member_key（规范键）

```python
# backend/data/team/store.py

def make_member_key(members: list[str]) -> str:
    return "|".join(sorted(members))
    # ["p003", "p001", "p002"] → "p001|p002|p003"
```

`member_key` 在名册中**唯一**，用于匹配与去重。

### 3.3 team_id 生成

```python
# backend/data/team/store.py — TeamStore.next_id()

def next_id(self, teams: list[Team] | None = None) -> str:
    # 扫描现有 ID，取最大序号 +1
    # t001, t002, t003, ...
```

基于全局递增序号，与 `player_id` 格式一致（`p001` / `t001`）。

### 3.4 TeamCreate / TeamUpdate

```python
class TeamCreate(TeamBase):
    id: str | None = None            # 省略时自动生成
    members: list[str]               # 1-3 个 player_id
    aliases: list[str] = []          # 初始队名列表

class TeamUpdate(BaseModel):
    alias: str | None = None         # 追加到 aliases 列表
```

**注意**：`TeamUpdate` 不允许修改 `members`。换员 = 新队，应创建新队伍。

---

## 4. 架构

```
team/api.py          ← 公开编程接口（所有外部调用入口）
team/cli.py          ← xcpc-team 命令行
team/service.py      ← 业务逻辑（CRUD、查询、add_alias、唯一性校验）
team/store.py        ← JSON 文件读写（data/raw/teams/roster.json）
team/models.py       ← Pydantic 数据模型
team/exceptions.py   ← 异常层次结构
```

### 4.1 异常层次

```
TeamError              ← 基类
├── TeamNotFoundError
├── TeamAlreadyExistsError
└── TeamValidationError
```

---

## 5. 编程 API

所有函数定义于 `team/api.py`，从包根 `team` 重新导出。

```python
from team import (
    create_team, delete_team, find_by_members,
    get_team, list_teams, update_team,
    configure_store, get_service,
)
from team.models import TeamCreate, TeamUpdate
from team.service import TeamService
```

### 5.1 查询

**`list_teams() -> list[Team]`**
- 列出全部队伍

**`get_team(team_id: str) -> Team`**
- 按 ID 查询，不存在时抛出 `TeamNotFoundError`

**`find_by_members(members: list[str]) -> Team | None`**
- 按队员集合查找，顺序无关
- 未找到返回 `None`

### 5.2 写入

**`create_team(data: TeamCreate, *, today=None) -> Team`**
- `member_key` 由 `members` 自动计算（排序后拼接）
- `team_id` 省略时自动生成（`t001`、`t002`…）
- 校验：同一 `member_key` 不得重复
- 持久化到 `data/raw/teams/roster.json`

**`update_team(team_id: str, data: TeamUpdate, *, today=None) -> Team`**
- `alias`：追加到 `aliases` 列表（去重）
- 不允许修改 `members`（换员应创建新队）

**`add_alias(team_id: str, alias: str, *, today=None) -> Team`**
- `TeamService` 方法，追加别名（去重）
- 供 `resolve_team()` 在导入时自动调用

**`delete_team(team_id: str) -> Team`**
- 从名册**物理删除**队伍

### 5.3 示例

```python
from team import create_team, find_by_members, list_teams, update_team
from team.models import TeamCreate, TeamUpdate
from team.service import TeamService

# 新建队伍
team = create_team(TeamCreate(
    members=["p001", "p002", "p003"],
    aliases=["三大队"],
))
print(team.id)          # t001
print(team.member_key)  # p001|p002|p003

# 按队员查找（顺序无关）
found = find_by_members(["p003", "p001", "p002"])
print(found.aliases)  # ["三大队"]

# 追加别名
team = update_team(team.id, TeamUpdate(alias="无敌队"))
print(team.aliases)  # ["三大队", "无敌队"]

# 或使用 service 直接追加
service = TeamService()
team = service.add_alias(team.id, "超级队")
print(team.aliases)  # ["三大队", "无敌队", "超级队"]
```

### 5.4 测试中使用独立存储

```python
from team import TeamStore, configure_store, create_team
from team.models import TeamCreate

store = TeamStore(raw_path="/tmp/test/teams.json")
configure_store(store)
create_team(TeamCreate(members=["p001"], aliases=["单测"]))
```

---

## 6. CLI

CLI 与编程 API 一一对应：

```bash
xcpc-team list [--json]
xcpc-team get <team_id> [--json]
xcpc-team find --members <p001> [<p002> ...] [--json]
xcpc-team create --members <p001> [<p002> ...] --aliases <alias> [...] [--json]
xcpc-team update <team_id> --alias <alias> [--json]
xcpc-team delete <team_id> [--json]
```

常用命令示例：

```bash
cd backend

# 列出所有队伍
python -m team.cli list

# 按队员查找
python -m team.cli find --members p001 p002 p003

# 新建队伍
python -m team.cli create --members p001 p002 p003 --aliases "测试队"

# 追加别名
python -m team.cli update t001 --alias "新队名"

# JSON 输出
python -m team.cli --json get t001
```

---

## 7. 校验规则

| 规则 | 处理 |
|------|------|
| 同一 `member_key` 不得重复 | 拒绝（`TeamAlreadyExistsError`） |
| `members` 长度 1–3 | Pydantic 自动校验 |
| `members` 内无重复 `player_id` | Pydantic 自动校验 |
| `team_id` 冲突 | 拒绝（`TeamValidationError`） |
| 换员（修改 members） | 不允许通过 update；应创建新队 |

---

## 8. 数据文件

| 路径 | 说明 |
|------|------|
| `data/raw/teams/roster.json` | 队伍名册，JSON 数组 |

写操作（create/update/delete）更新上述文件。路径相对于仓库根目录自动解析。

**存储格式**（raw，不含派生字段）：

```json
[
  {
    "id": "t001",
    "member_key": "p001|p002|p003",
    "members": ["p001", "p002", "p003"],
    "size": 3,
    "aliases": ["三大队", "无敌队"]
  }
]
```

---

## 9. 与 Formal Import 的协作

正式赛导入（`backend/data/import/formal.py`）中已集成队伍管理：

```python
# backend/data/import/formal.py

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

导入比赛时自动：
- 调用 `find_by_member_key()` 查找已有队伍
- 新队伍调用 `create_team()` 写入名册
- 已有队伍队名不同时追加 alias

---

## 10. 与 Rating 的关系

- 队伍成绩映射到选手时，按 `standings.members` 中的 1～3 人分摊或复制事件
- 单挑 / 双打 / 三人队均产生 `team_id`
- 个人训练赛也可直接用 `player_id` 而不建队