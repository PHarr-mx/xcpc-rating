# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。数据层为 **SQLite 持久化**（`xcpc_core/db/`），Web 为 **Reflex 全栈**（`xcpc_web/`，锁 0.9.7）。已实现：选手/队伍 CRUD、正式赛导入（CLI 一步式 + Web 五步 staged）、认证与绑定审批、管理后台 9 页（含比赛统一化：统一创建表单 + 赛事等级管理 + 积分认证审批）、积分页、榜单页（Rating 走 AtCoder 式重放引擎，`meta.rating_algorithm=atcoder_v1`，数值有业务含义）。

技术栈：Python 3.13、pydantic v2、openpyxl、PyYAML、SQLAlchemy 2.0。原始数据以 JSON 存于 `data/raw/`（逐字可 diff、可进 Git，import 后写回归档），运行时数据在 SQLite（`data/db/xcpc.db` 业务 + `data/db/xcpc_web.db` 认证）。

> Reflex + SQLite 方案已落地。**功能开发已完成**（四期收官）；剩部署上线（五期）与 OJ 数据源（未立项）。**文档在 [wiki/](wiki/)，入口 [wiki/Home.md](wiki/Home.md)**；同步发布到 [GitHub Wiki](https://github.com/PHarr-mx/xcpc-rating/wiki)。

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

## Web 开发

Reflex 应用完整运行中（`xcpc_web/`，锁版本 0.9.7）：榜单页、认证、`/profile`、积分页、管理后台 9 页（概览/用户审批/选手/队伍/比赛统一管理/赛事等级/积分认证/审计/在线导入）、`/about`、选手与比赛详情页。

开发命令：

```bash
uv sync --extra web                    # 安装 reflex 及组件分包
cd xcpc_web && ../.venv/bin/reflex run # 启动开发服务器（端口 3000）
cd xcpc_web && ../.venv/bin/python -m pytest tests -v   # web 测试单独跑
```

详见 [wiki/Web与权限.md](wiki/Web与权限.md)。

## 架构总览

### 包命名空间

包为**单顶层包** `xcpc_core`（下含 `player`/`team`/`contest`/`tier`/`importer`/`rating`/`points`/`db`/`utils`），由 `pyproject.toml` 安装解析，非 PYTHONPATH hack：

- `xcpc_core/player/`、`xcpc_core/team/` → CRUD 模块
- `xcpc_core/contest/` → 统一比赛与成绩（Contest/Standing，upsert；赛制 icpc|ioi × 形式 player|team × 等级 tier × 双开关）
- `xcpc_core/tier/` → 赛事等级（系数）与奖项基线 CRUD（config 种子/兜底与迁移 0003 共用）
- `xcpc_core/importer/` → 数据导入（raw + SQLite 双写）
- `xcpc_core/rating/` → Rating 引擎（计算器 + 事件生成 + AtCoder 式重放）
- `xcpc_core/points/` → 生涯积分（认证工作流 + 双账本 + 积分榜）
- `xcpc_core/board/` → 榜单聚合（只读，Rating × 选手信息 → BoardSnapshot）
- `xcpc_core/db/` → SQLite 表、session、alembic 迁移（`migrations/`，schema 变更走 `migrations.revision`）、一次性灌数据（`db.migrate`）
- `xcpc_core/utils/` → `Plog`（双写日志）、`calendar`（赛年/赛季）

`import xcpc_core.player`、`from xcpc_core.utils import Plog` 可用。后续 `xcpc_web/`（Reflex）为另一顶层包，**只依赖 `xcpc_core`，不反向依赖**。

### 数据流

```
data/raw/（人工投放 + import 写回归档，可 diff、可进 Git）
  ├── players/roster.json     选手名册（一次性迁移源；日常 CRUD 走 DB）
  ├── teams/roster.json       队伍名册（同上）
  ├── formal/{contest_id}.json 正式赛原始导入（import 写回，含 standings/award_thresholds）
  └── (通用比赛 JSON / OJ 数据源：P-U3 / 立项中)
        │
        ▼ import（xcpc_core.importer.*，raw 归档 + SQLite 双写）
        ▼ SQLite（data/db/xcpc.db，运行时数据源：统一 contest + tier/awardlevel + points 双表）
        ▼ Rating 计算（xcpc_core.rating.*，只取 counts_for_ranking 场次）→ 榜单（xcpc_core.board.*）
```

`data/config/` 为配置：`contest_weights.yaml`（P-U1 起作为「类型 → 等级标签/系数」的种子源，tier 表是运行时权威）、`school.yaml`（本校 Organization 精确匹配名 + 自动建档默认入学年）。

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

- **禁止绕过 API 直接读写存储**（SQLite 与 raw JSON 均不直接动），必须经 `xcpc_core.player.api` / `xcpc_core.team.api` / `xcpc_core.contest.api` / `xcpc_core.tier.api` / `xcpc_core.points.api`（或 CLI，CLI 与 API 共用同一套 service 逻辑）。
- 各包以 `find_repo_root()` 定位仓库根：基于 `data/raw` 标志目录向上搜索（`xcpc_core/db/session.py`）。测试用 `db_session` fixture（内存 SQLite）注入临时数据源。
- ID 自动生成：选手 `p001`、队伍 `t001`（全局递增，`XxxStore.next_id()`）。选手 `grade=0` 表示入学年未设置。
- 选手软删除 = `status=left`（`mark_left`）；`delete_player` 为物理删除。
- **队伍身份由队员集合决定**，与队名无关：`make_member_key` = 排序后 `"p001|p002|p003"`；同名队员不同队名 → 同一队伍（队名进 `aliases`）；换员 → 新队伍。
- 日志用 `xcpc_core.utils.Plog`（终端 + `logs/*.jsonl` 双写），在 CLI 入口实例化后传入下游函数。
- 选手/队伍数据模型要点见 `skill/player-manage/SKILL.md` 与 `skill/team-manage/SKILL.md`。

## 文档与实现状态

- 文档在 [wiki/](wiki/)，入口 [wiki/Home.md](wiki/Home.md)（同步发布到 GitHub Wiki）。按主题组织，**不再保留进度追踪/路线图类文档**（2026-10-26 重构，历史见 Git）：
  - 技术文档：`架构与数据模型`、`比赛与导入`、`Rating与积分`、`Web与权限`、`开发指南`、`部署运维`
  - 使用手册：`启动指南`、`普通用户操作手册`、`管理员操作手册`
- **已实现**：SQLite 持久化（20 张表，alembic 管到 `0004`）、选手/队伍 CRUD、统一比赛模型（tier/awardlevel + 双开关）、正式赛 xlsx 导入（五步 staged）、通用比赛 JSON 导入、认证与绑定审批、账号由管理员创建（单人 + 批量）、管理后台 10 页、榜单（AtCoder 式重放 `atcoder_v1`）、选手/比赛详情、生涯积分制（含免认证直录）、权重试算页、三层权限守卫。
- **未实现**：部署上线（Caddyfile / systemd / 备份 cron / 生产 rxconfig 均未创建）、OJ 数据源（三表已建、零读写代码、方案未定）。
- 原 Vue 静态站方案、v1 版 docs（DESIGN + 01–14）、docs/ v2 九篇、根目录计划稿（PROGRESS / CONTEXT / RATING_FORMULA_PLAN / CONTEST_UNIFICATION_PLAN）均已删除（留 Git 历史）。
- `skill/` 目录为 AI Agent Skills（`SKILL.md`），其中的工作流对 Claude 同样适用：`formal-import`、`player-manage`、`team-manage`。开发工作流与避坑见 [wiki/开发指南.md](wiki/开发指南.md)。
