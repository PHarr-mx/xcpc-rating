# xcpc-rating

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。

> **技术路线（已采纳）**：Reflex（Python 全栈 Web）+ SQLite + Caddy 反向代理。
> 原 Vue 3 静态站方案已废弃。进度与剩余工作见 [docs/08-路线图.md](docs/08-路线图.md)。

## 目录

| 目录 | 说明 |
|------|------|
| [xcpc_core/](xcpc_core/) | Python 业务层（`player` / `team` / `importer` / `utils`） |
| [data/](data/) | 数据文件（raw / config / db） |
| [docs/](docs/) | 设计文档、模块说明、开发手册 |
| [skill/](skill/) | AI Agent Skills |
| [xcpc_web/](xcpc_web/) | Reflex Web 前端（一期地基） |

## 文档

入口：[docs/README.md](docs/README.md)（文档地图 + 模块实现状态总览）。

| 文档 | 说明 |
|------|------|
| [docs/01-架构与数据流.md](docs/01-架构与数据流.md) | 架构、分层规则、SQLite 表与并发运维、配置文件 |
| [docs/02-选手与队伍.md](docs/02-选手与队伍.md) | Player / Team 模型、状态机、API 与 CLI |
| [docs/03-比赛与导入.md](docs/03-比赛与导入.md) | 三类数据源；正式赛导入全链路；训练赛/OJ 待建 |
| [docs/04-Rating与榜单.md](docs/04-Rating与榜单.md) | 事件模型、计算器体系、placeholder 现状、榜单与缓存 |
| [docs/05-Web与认证.md](docs/05-Web与认证.md) | Reflex 分层、路由与页面、认证与权限、Web 测试基建 |
| [docs/06-部署与运维.md](docs/06-部署与运维.md) | Caddy / systemd / 备份（五期待建） |
| [docs/07-开发流程.md](docs/07-开发流程.md) | 开发手册：环境、约定、避坑、Agent 协作 |
| [docs/08-路线图.md](docs/08-路线图.md) | 里程碑状态、剩余工作、待定决策 |

## 环境

```bash
source ./setup_env.sh   # uv sync + 激活 .venv
```

依赖与 Python 版本由 `pyproject.toml`（+ `.python-version` = 3.13）统一管理：

```bash
uv python install 3.13
uv sync
uv run python -m pytest xcpc_core -v
```

## 常用命令

```bash
# 选手管理
python -m xcpc_core.player.cli list --visible-only
python -m xcpc_core.player.cli get p001 --json

# 队伍管理
python -m xcpc_core.team.cli list
python -m xcpc_core.team.cli find --members p001 p002

# 正式赛导入（Python API）
python -c "
from xcpc_core.importer import FormalImportParams, import_formal_xcpcio_xlsx
from xcpc_core.importer.config import load_school_organizations
from datetime import date
result = import_formal_xcpcio_xlsx('比赛.xlsx', FormalImportParams(
    contest_id='2026_xxx', date=date(2026,5,18),
    contest_type='icpc_provincial',
    school_organizations=load_school_organizations(),
))
"

# 运行测试
uv run python -m pytest xcpc_core -v

# Web 开发
uv sync --extra web
cd xcpc_web && ../.venv/bin/reflex run
```

## 实施状态

已完成：选手/队伍 CRUD、正式赛导入（CLI + Web 五步 staged）、认证与绑定审批、管理后台、榜单页（Rating 公式为 placeholder_v0）。

待建：Rating 正式公式（四期）、训练赛/OJ 数据源、选手/比赛详情页、权重试算页、部署上线（五期）。

剩余工作与待定决策见 [docs/08-路线图.md](docs/08-路线图.md)；开发指引见 [docs/07-开发流程.md](docs/07-开发流程.md)。
