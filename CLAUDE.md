# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。数据层为 **SQLite 持久化**（`xcpc_core/db/`），已实现选手/队伍 CRUD、正式赛导入、contest 与 rating 模块（placeholder 公式）、board 榜单聚合；Reflex 前端为下一步。

技术栈：Python 3.13、pydantic v2、openpyxl、PyYAML、SQLAlchemy 2.0。原始数据以 JSON 存于 `data/raw/`（逐字可 diff、可进 Git，import 后写回归档），运行时数据在 SQLite（`data/db/xcpc.db`）。

> Reflex + SQLite 方案**已采纳**（`docs/DESIGN.md` v4.0）。按 [docs/13-实施路线图.md](docs/13-实施路线图.md) 已完成一期「地基」：打包、建表、JSON 一次性迁移、contest/rating 模块、board 榜单聚合。剩余：Reflex 骨架（一期收官）、认证、管理后台等。新开发按目标结构规划。

## 常用命令

环境（`uv sync` + 激活 `.venv`，Python 3.13 由 `.python-version` 锁定）：

```bash
source ./setup_env.sh    # 必须在项目根目录 source（uv 版）
```

测试（项目根目录）：

```bash
uv run python -m pytest xcpc_core -v
# 单个测试
uv run python -m pytest xcpc_core/tests/test_team_crud.py -v
```

选手 / 队伍 CLI（`python -m <包>.cli`，在项目根目录运行）：

```bash
python -m xcpc_core.player.cli list --visible-only
python -m xcpc_core.player.cli get p001 --json
python -m xcpc_core.team.cli list
python -m xcpc_core.team.cli find --members p001 p002
python -m xcpc_core.team.cli create --members p001 p002 --aliases 队名
```

正式赛导入（Python API，`source ./setup_env.sh` 后）：

```python
from datetime import date
from xcpc_core.importer import FormalImportParams, import_formal_xcpcio_xlsx
from xcpc_core.importer.config import load_school_organizations

result = import_formal_xcpcio_xlsx('比赛.xlsx', FormalImportParams(
    contest_id='2026_xxx',
    date=date(2026, 5, 18),
    contest_type='icpc_provincial',          # 须存在于 data/config/contest_weights.yaml
    school_organizations=load_school_organizations(),
))
```

未实现：`xcpc-data update` / `xcpc-site build|deploy` 尚未编写。

## 架构总览

### 包命名空间

包为**单顶层包** `xcpc_core`（下含 `player`/`team`/`contest`/`importer`/`rating`/`db`/`utils`），由 `pyproject.toml` 安装解析，非 PYTHONPATH hack：

- `xcpc_core/player/`、`xcpc_core/team/` → CRUD 模块
- `xcpc_core/contest/` → 比赛与成绩（Contest/Standing，upsert）
- `xcpc_core/importer/` → 数据导入（raw + SQLite 双写）
- `xcpc_core/rating/` → Rating 引擎（计算器 + 事件生成）
- `xcpc_core/board/` → 榜单聚合（只读，Rating × 选手信息 → BoardSnapshot）
- `xcpc_core/db/` → SQLite 表、session、一次性迁移
- `xcpc_core/utils/` → `Plog`（双写日志）、`calendar`（赛年/赛季）

`import xcpc_core.player`、`from xcpc_core.utils import Plog` 可用。后续 `xcpc_web/`（Reflex）为另一顶层包，**只依赖 `xcpc_core`，不反向依赖**。

### 数据流

```
data/raw/（人工投放 + import 写回归档，可 diff、可进 Git）
  ├── players/roster.json     选手名册（一次性迁移源；日常 CRUD 走 DB）
  ├── teams/roster.json       队伍名册（同上）
  ├── formal/{contest_id}.json 正式赛原始导入（import 写回，含 standings/award_thresholds/weight）
  └── (训练赛 / OJ 数据源：设计中)
        │
        ▼ import（xcpc_core.importer.*，raw 归档 + SQLite 双写）
        ▼ SQLite（data/db/xcpc.db，运行时数据源）
        ▼ Rating 计算（xcpc_core.rating.*）→ 榜单（xcpc_core.board.*）
```

`data/config/` 为配置：`contest_weights.yaml`（正式赛按 `contest_type`、训练赛按 `division` 的权重表）、`school.yaml`（本校 Organization 精确匹配名 + 自动建档默认入学年）。

### CRUD 模块分层模式

`player` 与 `team` 采用完全一致的六件套，新增 CRUD 模块照抄此模式：

| 文件 | 职责 |
|------|------|
| `models.py` | Pydantic DTO：`XxxBase` / `XxxCreate` / `XxxUpdate` / 实体类 + 校验器 |
| `store.py` | SQLAlchemy repository；`XxxStore(session)` 注入会话，DTO↔ORM 转换在 store 边界 |
| `service.py` | 业务逻辑（唯一约束、ID 生成、筛选） |
| `api.py` | **对外唯一读写入口**（facade），CLI 与其他子模块都从这里导入 |
| `cli.py` | argparse 命令行 |
| `exceptions.py` | 模块基础异常 + 子类 |
| `__init__.py` | 统一 re-export |

代表路径：`xcpc_core/player/{models,store,service,api,cli,exceptions}.py`。

### 关键约定

- **禁止绕过 API 直接读写存储**（SQLite 与 raw JSON 均不直接动），必须经 `xcpc_core.player.api` / `xcpc_core.team.api` / `xcpc_core.contest.api`（或 CLI，CLI 与 API 共用同一套 service 逻辑）。
- 各包以 `find_repo_root()` 定位仓库根：基于 `data/raw` 标志目录向上搜索（`xcpc_core/db/session.py`）。测试用 `db_session` fixture（内存 SQLite）注入临时数据源。
- ID 自动生成：选手 `p001`、队伍 `t001`（全局递增，`XxxStore.next_id()`）。选手 `grade=0` 表示入学年未设置。
- 选手软删除 = `status=left`（`mark_left`）；`delete_player` 为物理删除。
- **队伍身份由队员集合决定**，与队名无关：`make_member_key` = 排序后 `"p001|p002|p003"`；同名队员不同队名 → 同一队伍（队名进 `aliases`）；换员 → 新队伍。
- 日志用 `xcpc_core.utils.Plog`（终端 + `logs/*.jsonl` 双写），在 CLI 入口实例化后传入下游函数。
- 选手/队伍数据模型要点见 `skill/player-manage/SKILL.md` 与 `skill/team-manage/SKILL.md`。

## 文档与实现状态

- `docs/` 是**已采纳设计**：`DESIGN.md` 为架构总览（Reflex + SQLite），`01` 工程结构，`03`–`11` 业务模块设计，`12` 开发流程建议，`13` 实施路线图。
- **已实现**：SQLite 持久化（`xcpc_core/db/`，表结构见 `10`）、选手/队伍 CRUD、正式赛导入（raw+DB 双写）、contest 模块（`03`）、rating 引擎（`06`，placeholder 公式）、board 榜单聚合（`07`，含 data_version 缓存）。**设计蓝图**：Reflex 前端（`08`）、认证（`09`）、部署（`11`）。
- 原 Vue 静态站方案与 Reflex 提案文档已删除（留 Git 历史）。
- `skill/` 目录为 AI Agent Skills（`SKILL.md`），其中的工作流对 Claude 同样适用：`formal-import`、`player-manage`、`team-manage`。开发工作流建议见 `docs/12-开发流程建议.md`。
