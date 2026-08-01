# 数据存储与 SQLite

> 关联：[DESIGN.md](DESIGN.md) · [比赛与记录](./03-比赛与记录模块.md) · [数据导入与加工](./04-数据导入与加工模块.md) · [认证与权限](./09-认证与权限模块.md)

本文定义域数据从 JSON 全量读写迁移到 SQLite 的表结构、重构范围与迁移步骤。

> **实现选择**：core 的表用**纯 SQLAlchemy 2.0**（`xcpc_core/db/`）定义，**不依赖 reflex**。
> reflex 0.9.2 起弃用 `rx.Model`（0.9.7 上 `table=True` 子类化已损坏），官方建议直接使用 SQLAlchemy/SQLModel。
> 这同时让「core 不 import reflex」的规则成立（见 [01](01-开发环境与工程结构.md) §2）。

---

## 1. 为什么迁移

现状：`store.py` 每次操作 `load_all()` → 改列表 → `save_all()` 全量重写 JSON。
单人敲 CLI 没问题；网页多人写入会出现**丢更新**（两个请求各自读到旧全量，后写覆盖前写）。

| 方案 | 结论 |
|------|------|
| JSON + 进程内写锁 | 单进程可行，但仍全量重写；唯一性约束靠 service 层线性扫描 |
| **全量 SQLite** | **选定**。SQLAlchemy + alembic 标准路径；唯一性交给 DB 约束 |

---

## 2. raw/ 目录保留

**迁移不删 `data/raw/`。** 它承担「人工投放、可复现、可 diff、可进 Git」的职责，SQLite 替代不了。

```
raw/ ──import──▶ SQLite ──(可选)──▶ data/public/*.json（只读导出/备份快照）
```

数据流**单向**：`raw → DB`。反向只产出备份，不回写 raw。

---

## 3. 重构范围：store 层换实现，API 层不动

现有分层 `api.py → service.py → store.py → JSON` 正好把持久化隔离开了，所以：

| 层 | 改动 |
|----|------|
| `api.py` | **签名完全不变** → CLI 与现有测试不用改 |
| `service.py` | 内部改用细粒度方法。现在的「读全量 → 改 → 写全量」在 SQLite 上浪费，顺手改掉 |
| `store.py` | 从「全量读写 JSON」重写为真正的 repository：`get` / `list` / `insert` / `update` / `delete` |
| `models.py` | **保留为领域 DTO**（Pydantic），ORM 表在 `xcpc_core/db/`，两者显式互转 |

### 3.1 为什么 DTO 与 ORM 表分开

让 ORM 实例渗进 service 层会把 SQLAlchemy 的 session 生命周期问题扩散到各处
（detached instance、懒加载在 session 外触发），也会污染
`_validate_unique_constraints` 这类干净的业务校验。

代价是多一层转换代码；收益是 service 层保持可单测、不需要 DB fixture。

### 3.2 唯一性约束下沉

现在 `PlayerService._validate_unique_constraints` 用嵌套循环扫全表校验
`handle` 与 `(platform, handle)`。迁移后交给 DB 唯一索引，service 层捕获
`IntegrityError` 转成现有的 `PlayerValidationError`，对外异常语义不变。

---

## 4. 表结构

**Schema 真身在 `xcpc_core/db/tables.py`**（纯 SQLAlchemy，`Base = DeclarativeBase`）。
本文给逻辑分组与关键约束：

| 表 | 主键 | 关键列 / 约束 |
|----|------|--------------|
| `player` | `id` str（p001） | `handle` UNIQUE；`grade`（0=未设置）；`status` |
| `ojaccount` | 自增 | FK `player.id`；**UNIQUE(platform, handle)** |
| `playeralias` | 自增 | FK `player.id`；**UNIQUE(player_id, alias)** |
| `team` | `id` str（t001） | `member_key` UNIQUE+INDEX（p001\|p002\|p003）；`size` |
| `teammember` | 自增 | FK `team.id`、`player.id`；`seat` |
| `teamalias` | 自增 | FK `team.id`；`alias`（队名历史） |
| `contest` | `id` str | `source_type` INDEX；formal/training **合表**（见 §4.1） |
| `standing` | 自增 | FK `contest.id`；`team_id`（solo 为空）；`award`/`solved`/`penalty`/`score` |
| `standingmember` | 自增 | FK `standing.id`、`player.id` |
| `ojcontest` | `id` str | `platform`、`weight` |
| `ojcontestresult` | 自增 | FK `ojcontest.id`、`player.id`；`rating_before/after/delta` |
| `ojsnapshot` | 自增 | FK `player.id`；`rating_numeric`、`solve_count`、`date` INDEX |
| `ratingevent` | 自增 | `event_id` UNIQUE（派生表，可重建） |
| `meta` | `id` int（=1） | `data_version`（Rating 缓存失效）、`rating_algorithm` |
| `auditlog` | 自增 | 无外键；`user_id` INDEX、`action`、`diff_json`、`at` |
| `importbatch` | 自增 | `status`（staged\|confirmed\|discarded）、`payload_json` |

### 4.1 比赛与成绩：formal / training 合表

`contest` 用 `source_type`（formal|training）区分，可空列承载差异
（formal 的 `total_teams`、`contest_type`；training 的 `division`）。
formal 与 training 本就共享 `competition_year` / `season` / `rated` / `weight` / `weight_source`，
分表会让榜单查询、`RatingEvent` 生成、比赛详情页各写两遍。
代价是列可空性无法在 DB 层强约束，这条校验留在 service 层。

### 4.2 派生表与运维表

- `ratingevent`：可由 Contest/Standing/OJ* 整表重建，**不作为事实来源**，备份时可跳过
- `meta`：单行表，`data_version` 供 Rating 缓存失效（见 [06](06-Rating计算模块.md) §3）
- `auditlog`：故意不加外键（用户被删后审计仍须保留）

用户与会话表见 [09-认证与权限模块](09-认证与权限模块.md) §5（auth 模块，二期）。

---

## 5. 建表与迁移

**开发期**：`Base.metadata.create_all(engine)`（`xcpc_core/db/session.create_all`），schema 稳定后引入 alembic。

**迁移（一次性灌数据）**：

```bash
uv run python -m xcpc_core.db.migrate   # 见 §5.1
```

### 5.1 `migrate` 要求

- 读 `data/raw/players/roster.json`、`data/raw/teams/roster.json`、`data/raw/formal/*.json`
- **幂等**：按主键 upsert，可反复重跑
- 现有 ID（`p001`、`t001`）原样保留，不重新编号
- `created_at` 缺失时填迁移当日
- 输出统计与未匹配项，走结构化日志记录

> 引入 alembic 时：`alembic init` + `env.py` 导入 `xcpc_core.db.base`（含全部表），
> `alembic revision --autogenerate`。注意 alembic 只能发现 `env.py` 实际 import 的模型。

---

## 6. 已知数据问题（迁移前需处理）

| 问题 | 影响 | 建议 |
|------|------|------|
| 选手 `grade` 全为 0 | 榜单年级列无意义 | 迁移后用管理后台批量补 |
| `oj_accounts` 全为空 | OJ 榜单无数据 | 二期上线后由队员自助填（这是多用户自助的直接价值） |
| `data/processed/` 仍有文件 | 与「由 pipeline 生成」的设计矛盾 | 该目录整体废弃，数据在 DB |

---

## 7. 运维

### 7.1 并发配置：三件事同时做到，缺一不可

先明确 SQLite 的硬上限：**允许多个并发读，但同时只能有一个写。** 这是设计如此，
不是配置能绕开的。要在 Web 场景下不报 `database is locked`，需要：

| # | 措施 | 作用 |
|---|------|------|
| 1 | **WAL 模式** | 读不阻塞写。设一次持久生效 |
| 2 | **busy_timeout** | 撞锁时等待重试，而非立刻抛错 |
| 3 | **短事务** | 不在持有写锁时做慢活 |

**WAL 单独不够 —— 这一条最容易漏。** 有实测：仅开 WAL 不设 timeout，6400 次操作中
仍有 7 次报锁；WAL + 1 秒 busy_timeout 则为 0 次。连读操作也可能撞锁，
在连接池频繁开关连接时尤其明显。

实现见 `xcpc_core/db/session.py`：

```python
engine = create_engine(
    url or default_db_url(),
    connect_args={"check_same_thread": False, "timeout": 5},
)

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.execute("PRAGMA foreign_keys=ON")      # SQLite 默认不强制外键
    cur.close()
```

PRAGMA 必须挂在 `connect` 事件上**逐连接执行** —— 连接池里每条新连接都要设，
只在启动时执行一次是无效的（`journal_mode` 除外，它持久化在库文件里）。

`foreign_keys=ON` 也别漏：SQLite 默认不强制外键约束，不开的话 §4 里那些
`ForeignKey` 声明只是文档,不会真正拦住脏数据。

### 7.2 三个容易踩的坑

**`check_same_thread=False` 不等于连接可以并发使用。** SQLAlchemy 对文件型数据库默认
就设了它（配合 `QueuePool`）。但连接池本身线程安全，`Connection` 与 `Session` 对象
**不是** —— 不要把一个 session 跨线程共享。

**ORM 会让锁问题更严重。** SQLAlchemy 官方警告：Session 默认在事务中运行，autoflush
会在 SELECT 前先发 DML，导致比预期更早加锁。官方原话是「在 SQLite 上追求高写并发
是一场必败的仗」。这也是本项目坚持 [§3.1](#31-为什么-dto-与-orm-表分开) 让 service 层
不持有 ORM 实例的一个附带理由：事务边界更容易看清。

**长事务是最大的隐藏杀手。** 具体到本项目：xlsx 解析、Rating 全量重算都不要放在
写事务里。这正是 [08](./08-前端与Web交互模块.md) §4.4 用 `ImportBatch` 暂存的
另一个理由 —— 解析与落库分成两个短事务。

### 7.3 规模判断

本项目的写操作是「admin 偶尔导一场比赛」「队员偶尔改个 OJ 账号」，
量级上 WAL + busy_timeout 完全够用。

真到写不过来时，`db_url` 换成 Postgres 即可，`xcpc_core` 一行不用改 ——
这是「不 import reflex」+「DTO 与 ORM 分离」两条规则换来的可迁移性。

### 7.4 单进程约束

Reflex 的 State 默认存在**进程内存的字典**里（按 client token 索引）。
多 worker 会导致同一用户的两次请求落到不同进程、看到不同 state。

**本项目单进程运行，不要加 `--workers`。** 见 [11](./11-部署与运维.md) §6。
这也顺带保证了 SQLite 只有一个进程在写。

### 7.5 备份

```cron
30 4 * * * sqlite3 /opt/xcpc-rating/data/db/xcpc.db ".backup '/var/backups/xcpc-$(date +\%F).db'"
```

用 `.backup` 而非 `cp` —— 前者对正在写入的库是安全的。

`data/raw/` 已在 Git 里，本身就是一份可追溯的冷备。

---

## 8. 开放问题

| 项 | 状态 |
|----|------|
| `data/processed/` 是否彻底删除 | 建议删除，其职责被 DB 取代 |
| 是否保留 JSON 导出以便脱库审阅 | 建议保留 `xcpc-core dump-json`，输出到 `data/public/` |
| 规模增长后是否换 Postgres | `db_url` 改一行即可，暂不需要 |
| alembic 何时引入 | schema 稳定后；开发期用 `create_all` |

---

*文档版本：v1.2 — 已采纳；表改用纯 SQLAlchemy（reflex 弃用 rx.Model）。*
