---
name: player-manage
description: >-
  管理 xcpc-rating 选手名册（增删改查、别名、OJ 账号、离队）。
  通过 player.api 或 xcpc-player CLI 操作 data/raw/players/roster.json。
  在用户提到选手、名册、roster、建档、离队、别名、handle、入学年、player_id 时使用。
---

# 选手管理

## 前置条件

1. 激活环境：`source ./setup_env.sh`（项目根目录）
2. 数据文件：`data/raw/players/roster.json`

详细 API 见 [docs/backend-player-module.md](../../docs/backend-player-module.md)。

## 原则

- **必须通过 `player.api` 或 CLI**，不要手改 `roster.json`
- 编程 API 与 CLI 共用同一套逻辑
- `grade=0` 表示入学年未设置（导入自动建档默认值，见 `school.yaml`）
- `id` 省略时自动生成 `p001`、`p002`…（全局递增，不含年份）
- `status=left` 为软删除（离队）；`delete_player` 为物理删除

## 数据模型要点

| 字段 | 说明 |
|------|------|
| `id` | 校内唯一 ID，如 `p001` |
| `name` | 姓名 |
| `handle` | 校内昵称，全局唯一，可省略 |
| `grade` | 入学年；`0` = 未设置 |
| `status` | `active` / `retired` / `left` |
| `aliases` | 别名列表，用于 `find_by_name` |
| `oj_accounts` | `[{platform, handle}]`，platform: `codeforces` / `atcoder` / `luogu` / `nowcoder` |

唯一约束：`id`、`handle`、每个 OJ `(platform, handle)` 均不可重复。

## 工作流

```
任务进度：
- [ ] 1. 确认操作类型（查 / 增 / 改 / 离队 / 删）
- [ ] 2. 查重（find_by_name / find_by_oj）避免歧义
- [ ] 3. 执行 API 或 CLI
- [ ] 4. 汇报变更（player_id、受影响字段）
```

## 编程 API（推荐）

```python
from player import (
    create_player,
    delete_player,
    find_by_name,
    find_by_oj,
    get_player,
    list_players,
    mark_left,
    update_player,
)
from player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate
from utils import Plog
```

### 查询

```python
# 列出在队选手
players = list_players(include_left=False)

# 按姓名（含别名）
matches = find_by_name("张三")
if len(matches) != 1:
    # 歧义：补 aliases 或指定 grade 再查
    matches = find_by_name("张三", grade=2024)

# 按 OJ
player = find_by_oj("codeforces", "tourist")
```

### 新建

```python
plog = Plog(name="xcpc-player")
player = create_player(
    PlayerCreate(
        name="李四",
        grade=2025,
        handle="ls",
        aliases=["小李"],
        oj_accounts=[OJAccount(platform="luogu", handle="lisi_lg")],
    ),
)
plog.info("新建选手", player_id=player.id, name=player.name)
plog.close()
```

### 更新

```python
update_player(
    "p001",
    PlayerUpdate(grade=2024, aliases=["李四", "Lisi"]),
)

# OJ 账号整体替换（非合并）
update_player(
    "p001",
    PlayerUpdate(oj_accounts=[OJAccount(platform="codeforces", handle="lisi_cf")]),
)
```

### 离队 / 删除

```python
mark_left("p001")       # 软删除，保留档案
delete_player("p001")   # 物理删除，慎用
```

## CLI

```bash
# 列出可展示选手
xcpc-player list --visible-only

# 按姓名查找
xcpc-player find --name 张三

# 新建（grade 可为 0）
xcpc-player create --name 王五 --grade 2025

# 更新入学年、别名
xcpc-player update p001 --grade 2024 --aliases 王五,WW

# 绑定 OJ
xcpc-player update p001 \
  --oj-accounts '[{"platform":"codeforces","handle":"wangwu"}]'

# 标记离队
xcpc-player mark-left p001
```

未安装入口脚本时：`python -m player.cli <子命令>`（需已 `source ./setup_env.sh`）。

## 常见场景

| 场景 | 做法 |
|------|------|
| 导入后补全入学年 | `update_player(id, PlayerUpdate(grade=2024))` |
| 同名歧义 | 为已有人选补 `aliases`，或新建时区分 `grade` |
| 比赛 import 自动建档 | 由 `importer` 调用 `create_player`，默认 `grade` 来自 `school.yaml` |
| 确认是否已在册 | `find_by_name` 返回 0/1/多条，多条需人工消歧 |
| 退役但未离队 | `update_player(..., PlayerUpdate(status=PlayerStatus.retired))` |

## 异常处理

| 异常 | 处理 |
|------|------|
| `PlayerNotFoundError` | 核对 `player_id` |
| `PlayerAlreadyExistsError` | `id` 冲突，换 ID 或更新已有记录 |
| `PlayerValidationError` | `handle` 或 OJ 账号与他人重复 |
| `find_by_name` 多条 | 不要自动新建；补 `aliases` 或让用户指定 `grade` |

## 修改代码时

- API：`backend/data/player/api.py`
- 业务逻辑：`backend/data/player/service.py`
- CLI：`backend/data/player/cli.py`
- 测试：`pytest backend/data/tests`

## 禁止事项

- 不要直接编辑 `data/raw/players/roster.json`
- 未经用户要求不要 `git commit`
- 物理删除前确认无历史成绩关联需求（优先 `mark_left`）
