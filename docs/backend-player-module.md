# 选手模块 API 使用说明

> 业务字段与状态语义见 [design/01-选手模块.md](./design/01-选手模块.md)。  
> 实现路径：`backend/data/player/`。

---

## 1. 设计原则

选手的增删改查提供**两种等价入口**，底层共用同一套逻辑：

| 入口 | 适用场景 |
|------|----------|
| **编程 API**（`player.api`） | 数据流水线、import 脚本、测试、其他 backend 子模块 |
| **CLI**（`xcpc-player` / `python -m player.cli`） | 人工维护名册、本地调试 |

**约定：**

- 其他模块应通过 `player.api` 或 `from player import ...` 调用，**不要**直接读写 `roster.json`。
- CLI 仅负责参数解析与输出格式化，所有写操作最终调用 `player.api` 中的函数。
- 需要自定义数据路径时，传入 `PlayerStore` 或使用 `configure_store()`（见 §4）。

---

## 2. 安装与导入

在项目根目录安装（见 [`pyproject.toml`](../pyproject.toml)）：

```bash
pip install -r requirements.txt
# 或: pip install -e ".[dev]"
```

**推荐导入方式（模块级函数）：**

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
```

**亦可使用服务类（适合注入依赖、批量操作）：**

```python
from player import PlayerService, PlayerStore

service = PlayerService()
players = service.list_players(include_left=False)
```

---

## 3. 编程 API 参考

以下函数均定义于 `player/api.py`，并从包根 `player` 重新导出。

### 3.1 查询

#### `list_players`

```python
list_players(
    *,
    include_left: bool = True,
    status: PlayerStatus | None = None,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]
```

| 参数 | 说明 |
|------|------|
| `include_left` | `False` 时排除 `status=left` 的选手（对应 CLI `--visible-only`） |
| `status` | 按状态筛选：`active` / `retired` / `left` |
| `grade` | 按入学年份筛选，如 `2023` |
| `store` | 可选，指定数据存储；默认使用仓库内路径 |

#### `get_player`

```python
get_player(player_id: str, *, store: PlayerStore | None = None) -> Player
```

按校内 ID 查询。不存在时抛出 `PlayerNotFoundError`。

#### `find_by_name`

```python
find_by_name(
    name: str,
    *,
    grade: int | None = None,
    store: PlayerStore | None = None,
) -> list[Player]
```

匹配 `name` 或 `aliases` 中的条目；`grade` 可选，用于缩小范围。

#### `find_by_oj`

```python
find_by_oj(
    platform: str,
    handle: str,
    *,
    store: PlayerStore | None = None,
) -> Player | None
```

按 OJ 平台与 handle 查找；未找到返回 `None`。  
`platform` 取值：`codeforces` | `atcoder` | `luogu` | `nowcoder`。

### 3.2 写入

#### `create_player`

```python
create_player(
    data: PlayerCreate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player
```

- `data.id` 可省略，自动生成 `p{入学年}{三位序号}`（如 `p2025001`）。
- 校验：`id`、校内 `handle`、OJ `(platform, handle)` 全局唯一。
- 持久化时同步更新 raw 与 processed 两份文件。

#### `update_player`

```python
update_player(
    player_id: str,
    data: PlayerUpdate,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player
```

只更新 `PlayerUpdate` 中显式传入的字段；`oj_accounts` 传入时**整体替换**。

#### `delete_player`

```python
delete_player(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player
```

从名册**物理删除**选手，返回被删除的记录。

#### `mark_left`

```python
mark_left(
    player_id: str,
    *,
    today: date | None = None,
    store: PlayerStore | None = None,
) -> Player
```

将 `status` 设为 `left`（软删除）；processed 保留档案，public 导出时应过滤。

### 3.3 辅助

```python
configure_store(store: PlayerStore) -> None   # 设置进程级默认存储
get_service(*, store: PlayerStore | None = None) -> PlayerService
find_repo_root(start: Path | None = None) -> Path
```

---

## 4. 编程示例

### 4.1 新建选手

```python
from player import create_player
from player.models import OJAccount, PlayerCreate, PlayerStatus

player = create_player(
    PlayerCreate(
        name="测试选手",
        handle="cs",
        grade=2025,
        status=PlayerStatus.active,
        oj_accounts=[
            OJAccount(platform="codeforces", handle="test_cf"),
        ],
        aliases=["Test"],
    )
)
print(player.id)  # 如 p2025001
```

### 4.2 更新与标记离队

```python
from player import mark_left, update_player
from player.models import PlayerStatus, PlayerUpdate

update_player("p2025001", PlayerUpdate(status=PlayerStatus.retired))
mark_left("p2025001")  # 或物理删除：delete_player("p2025001")
```

### 4.3 在 import 流水线中解析选手

```python
from player import find_by_name, find_by_oj

def resolve_player(name: str, grade: int):
    matches = find_by_name(name, grade=grade)
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"无法唯一匹配选手: {name} ({grade})")

player = find_by_oj("luogu", "zhangsan_lg")
```

### 4.4 测试中使用独立存储

```python
from pathlib import Path

from player import PlayerStore, configure_store, create_player
from player.models import PlayerCreate

store = PlayerStore(
    raw_path=Path("/tmp/test/roster.json"),
    processed_path=Path("/tmp/test/players.json"),
)
configure_store(store)  # 之后省略 store 参数即可

create_player(PlayerCreate(name="单测", grade=2024))
```

或单次调用时传入 `store=`，不影响全局默认。

---

## 5. CLI 参考

CLI 与编程 API **一一对应**：

| CLI 命令 | 编程 API |
|----------|----------|
| `list [--visible-only] [--status] [--grade]` | `list_players(...)` |
| `get <player_id>` | `get_player(player_id)` |
| `find --name <name> [--grade]` | `find_by_name(name, grade=...)` |
| `find --oj <platform> <handle>` | `find_by_oj(platform, handle)` |
| `create --name ... --grade ...` | `create_player(PlayerCreate(...))` |
| `update <player_id> [--name] ...` | `update_player(player_id, PlayerUpdate(...))` |
| `delete <player_id>` | `delete_player(player_id)` |
| `mark-left <player_id>` | `mark_left(player_id)` |

### 5.1 常用命令

```bash
cd backend

# 列出可展示选手（排除离队）
python -m player.cli list --visible-only

# 查询单个选手（JSON 输出）
python -m player.cli get p20230001 --json

# 新建
python -m player.cli create --name 测试 --grade 2025 --handle ts

# 绑定 OJ 账号
python -m player.cli update p2025001 \
  --oj-accounts '[{"platform":"codeforces","handle":"test_cf"}]'

# 标记离队
python -m player.cli mark-left p2025001
```

安装包后也可使用入口脚本：

```bash
xcpc-player list --visible-only
```

---

## 6. 数据文件

| 路径 | 说明 |
|------|------|
| `data/raw/players/roster.json` | 人工维护的原始名册（精简字段） |
| `data/processed/players.json` | 流水线中间表（含 `grade_label`、`status_label`、时间戳） |

任意写操作（create / update / delete / mark_left）会**同时更新**上述两个文件。  
默认路径相对于仓库根目录自动解析（查找 `data/raw/players/roster.json`）。

---

## 7. 异常

| 异常 | 含义 |
|------|------|
| `PlayerNotFoundError` | 指定 `player_id` 不存在 |
| `PlayerAlreadyExistsError` | `id` 冲突 |
| `PlayerValidationError` | handle 或 OJ 账号重复等业务校验失败 |
| `PlayerError` | 以上异常的基类 |

调用方应捕获 `PlayerError` 或具体子类，CLI 会将错误信息打印到 stderr 并以退出码 `1` 结束。

---

## 8. 与其他模块的集成

后续模块（比赛 import、Rating 计算、export）建议：

1. **只读**：`list_players(include_left=False)` 获取可展示选手；或 `get_player` / `find_by_*` 做关联。
2. **写入**：在 import 发现新选手时调用 `create_player`；离队调用 `mark_left`，避免手改 JSON。
3. **测试**：构造 `PlayerStore(raw_path=..., processed_path=...)` 注入，勿污染仓库 `data/raw`。

```python
# 示例：export 模块过滤离队选手
from player import list_players

def export_ratings():
    for player in list_players(include_left=False):
        ...
```
