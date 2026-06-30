# 选手模块

> **状态**：✅ 已实现  
> **代码路径**：`backend/data/player/`  
> **数据文件**：`data/raw/players/roster.json`

---

## 1. 模块职责

- 选手的**增删改查**（编程 API + CLI 双入口）
- 选手**唯一标识**与**静态属性**（姓名、handle、年级、OJ 账号）
- 作为 Rating 计算、榜单、队伍成员引用的**主实体**

---

## 2. 数据模型

### 2.1 Player（选手）

```python
# backend/data/player/models.py

class PlayerStatus(str, Enum):
    active = "active"      # 现役
    retired = "retired"    # 退役
    left = "left"          # 离队

class OJAccount(BaseModel):
    platform: Literal["codeforces", "atcoder", "luogu", "nowcoder"]
    handle: str
    user_id: str | None = None

class Player(PlayerBase):
    id: str                          # 如 p001, p002 ...
    name: str                        # 真实姓名
    handle: str | None = None        # 校内简称（可选）
    grade: int = 0                   # 入学年份，0 = 未设置
    status: PlayerStatus = PlayerStatus.active
    oj_accounts: list[OJAccount] = []
    aliases: list[str] = []          # 曾用名/英文名，用于导入匹配
    created_at: date | None = None
    updated_at: date | None = None
```

### 2.2 选手状态（status）

| `status` | 中文 | 展示 | 说明 |
|----------|------|------|------|
| `active` | 现役 | ✅ 正常展示 | 正常计入榜单 |
| `retired` | 退役 | ✅ 展示（可加标记） | 历史数据保留，仍可导入新成绩 |
| `left` | 离队 | ❌ 默认过滤 | raw 保留档案，public 导出时排除 |

**退役 vs 离队**：
- **退役**：毕业或结束正式队员身份，但校友赛、个人参赛等仍可追踪
- **离队**：因转专业、退学等原因离开集训队，站点当其人不存在

### 2.3 handle 与 OJ handle

| 字段 | 层级 | 说明 |
|------|------|------|
| `handle` | 选手 | 校内简称，如 `zs`；榜单、队内展示用，**可选** |
| `oj_accounts[].handle` | OJ 账号 | 各平台用户名，与选手 `handle` 无关 |

### 2.4 年级（grade）

- 存储为**入学年份**整数（如 `2023` 表示 2023 级），`0` 表示未设置
- 展示标签：`0` → `"未设置"`，其他 → `"{grade}级"`

### 2.5 选手 ID 生成

- 格式：`p` + 三位序号（`p001`, `p002`, ...）
- 新建时自动分配：取已有最大序号 +1
- 可在 `create_player` 时手动指定

---

## 3. 架构

```
player/api.py          ← 公开编程接口（所有外部调用入口）
player/cli.py          ← xcpc-player 命令行
player/service.py      ← 业务逻辑（CRUD、查询、唯一性校验）
player/store.py        ← JSON 文件读写（data/raw/players/roster.json）
player/models.py       ← Pydantic 数据模型
player/exceptions.py   ← 异常层次结构
```

### 3.1 异常层次

```
PlayerError              ← 基类
├── PlayerNotFoundError
├── PlayerAlreadyExistsError
└── PlayerValidationError
```

---

## 4. 编程 API

所有函数定义于 `player/api.py`，从包根 `player` 重新导出。

```python
from player import (
    create_player, delete_player, find_by_name, find_by_oj,
    get_player, list_players, mark_left, update_player,
    configure_store, get_service,
)
from player.models import OJAccount, PlayerCreate, PlayerStatus, PlayerUpdate
```

### 4.1 查询

**`list_players(*, include_left=True, status=None, grade=None) -> list[Player]`**

| 参数 | 说明 |
|------|------|
| `include_left` | `False` 时排除 `status=left` |
| `status` | 按状态筛选：`active` / `retired` / `left` |
| `grade` | 按入学年份筛选，如 `2023` |

**`get_player(player_id: str) -> Player`**
- 按 ID 查询，不存在时抛出 `PlayerNotFoundError`

**`find_by_name(name: str, *, grade=None) -> list[Player]`**
- 匹配 `name` 或 `aliases` 中的条目（精确匹配）
- `grade` 可选，用于缩小范围

**`find_by_oj(platform: str, handle: str) -> Player | None`**
- 按 OJ 平台与 handle 查找，未找到返回 `None`
- `platform` 取值：`codeforces` | `atcoder` | `luogu` | `nowcoder`

### 4.2 写入

**`create_player(data: PlayerCreate, *, today=None) -> Player`**
- `data.id` 可省略，自动生成 `p{三位序号}`
- 校验：`id`、校内 `handle`、OJ `(platform, handle)` 全局唯一
- 持久化到 `data/raw/players/roster.json`

**`update_player(player_id: str, data: PlayerUpdate, *, today=None) -> Player`**
- 只更新 `PlayerUpdate` 中显式传入的字段
- `oj_accounts` 传入时**整体替换**

**`delete_player(player_id: str) -> Player`**
- 从名册**物理删除**选手

**`mark_left(player_id: str) -> Player`**
- 将 `status` 设为 `left`（软删除），名册保留

### 4.3 示例

```python
from player import create_player, find_by_name, list_players, mark_left
from player.models import OJAccount, PlayerCreate, PlayerStatus

# 新建选手
player = create_player(PlayerCreate(
    name="张三",
    handle="zs",
    grade=2023,
    oj_accounts=[OJAccount(platform="codeforces", handle="zhangsan_cf")],
    aliases=["Zhang San"],
))
print(player.id)  # p001

# 查询
active = list_players(include_left=False)
matches = find_by_name("张三", grade=2023)

# 标记离队
mark_left("p001")
```

### 4.4 测试中使用独立存储

```python
from player import PlayerStore, configure_store, create_player
from player.models import PlayerCreate

store = PlayerStore(raw_path="/tmp/test/roster.json")
configure_store(store)
create_player(PlayerCreate(name="单测", grade=2024))
```

---

## 5. CLI

CLI 与编程 API 一一对应：

```bash
xcpc-player list [--visible-only] [--status active|retired|left] [--grade 2023] [--json]
xcpc-player get <id> [--json]
xcpc-player find --name <name> [--grade 2023] [--json]
xcpc-player find --oj <platform> <handle> [--json]
xcpc-player create --name <name> [--grade 2023] [--handle <handle>] [--oj <platform:handle>]
xcpc-player update <id> [--name <name>] [--grade 2023] [--status active|retired|left]
xcpc-player delete <id>
xcpc-player mark-left <id>
```

常用命令示例：

```bash
cd backend
python -m player.cli list --visible-only
python -m player.cli get p001 --json
python -m player.cli create --name 测试 --grade 2025 --handle ts
python -m player.cli mark-left p001
```

---

## 6. 校验规则

| 规则 | 处理 |
|------|------|
| 同一 `id` 不得重复 | 拒绝（`PlayerAlreadyExistsError`） |
| 同一 `handle`（校内）不得绑定两名选手 | 拒绝（`PlayerValidationError`） |
| 同一 `(platform, handle)` 不得绑定两名选手 | 拒绝（`PlayerValidationError`） |
| `status` 合法枚举 | Pydantic 自动校验 |
| `grade` 范围 0–2035 | Pydantic 自动校验 |
| `left` 不出现在 public 导出 | export 阶段过滤 |

---

## 7. 数据文件

| 路径 | 说明 |
|------|------|
| `data/raw/players/roster.json` | 选手名册，JSON 数组 |

写操作（create/update/delete/mark_left）更新上述文件。路径相对于仓库根目录自动解析。

**存储格式**（raw，不含派生字段）：

```json
[
  {
    "id": "p001",
    "name": "张三",
    "handle": "zs",
    "grade": 2023,
    "status": "active",
    "oj_accounts": [
      {"platform": "codeforces", "handle": "zhangsan_cf", "user_id": null}
    ],
    "aliases": ["Zhang San"]
  }
]
```

---

## 8. 与其他模块的集成

后续模块（比赛 import、Rating 计算、export）应：

1. **只读**：`list_players(include_left=False)` 获取可展示选手；或 `get_player` / `find_by_*` 做关联
2. **写入**：import 发现新选手时调用 `create_player`；离队调用 `mark_left`，**避免手改 JSON**
3. **测试**：构造 `PlayerStore(raw_path=...)` 注入，勿污染仓库 `data/raw`