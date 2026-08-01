# xcpc-rating

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。

> **技术路线（已采纳）**：Reflex（Python 全栈 Web）+ SQLite + Caddy 反向代理。
> 原 Vue 3 静态站方案已废弃。实施计划见 [docs/13-实施路线图.md](docs/13-实施路线图.md)。

## 目录

| 目录 | 说明 |
|------|------|
| [xcpc_core/](xcpc_core/) | Python 业务层（`player` / `team` / `importer` / `utils`） |
| [data/](data/) | 数据文件（raw / config / db） |
| [docs/](docs/) | 设计文档、模块说明、开发手册 |
| [skill/](skill/) | AI Agent Skills |

## 文档

| 文档 | 说明 |
|------|------|
| [docs/DESIGN.md](docs/DESIGN.md) | 工程架构总览（已采纳 Reflex + SQLite） |
| [docs/01-开发环境与工程结构.md](docs/01-开发环境与工程结构.md) | 目标工程结构、分层规则、迁移对应 |
| [docs/03-比赛与记录模块.md](docs/03-比赛与记录模块.md) | 正式赛 / 训练赛 / OJ 三类数据源定义 |
| [docs/04-数据导入与加工模块.md](docs/04-数据导入与加工模块.md) | raw → SQLite 导入、Web 交互式导入 |
| [docs/05-数据导出与发布模块.md](docs/05-数据导出与发布模块.md) | 可选只读导出 / 备份 |
| [docs/06-Rating计算模块.md](docs/06-Rating计算模块.md) | Rating 引擎（基类 + 继承体系） |
| [docs/07-榜单模块.md](docs/07-榜单模块.md) | 双榜模式、时间维度、排名规则 |
| [docs/08-前端与Web交互模块.md](docs/08-前端与Web交互模块.md) | Reflex State / 路由 / 页面 |
| [docs/09-认证与权限模块.md](docs/09-认证与权限模块.md) | 角色、用户↔选手绑定、字段级权限 |
| [docs/10-数据存储与SQLite.md](docs/10-数据存储与SQLite.md) | SQLite 表结构、迁移、运维 |
| [docs/11-部署与运维.md](docs/11-部署与运维.md) | Caddy / systemd / 备份 |
| [docs/12-开发流程建议.md](docs/12-开发流程建议.md) | 开发手册：环境、约定、避坑 |
| [docs/13-实施路线图.md](docs/13-实施路线图.md) | 五期实施计划 |
| [docs/skills.md](docs/skills.md) | AI Agent Skills |

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
```

## 实施状态

当前完成：选手/队伍 CRUD、正式赛 xlsx 导入（JSON 数据层）。

按 [docs/13-实施路线图.md](docs/13-实施路线图.md) 推进五期改造：
`pyproject 打包 → Reflex 骨架 → 认证 → 管理后台 → Rating 计算 → 上线`。
开发指引见 [docs/12-开发流程建议.md](docs/12-开发流程建议.md)。
