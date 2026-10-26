# xcpc-rating

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。

> **技术路线**：Reflex（Python 全栈 Web）+ SQLite + Caddy 反向代理。

## 目录

| 目录 | 说明 |
|------|------|
| [xcpc_core/](xcpc_core/) | Python 业务层（`player` / `team` / `contest` / `tier` / `importer` / `rating` / `points` / `board` / `db` / `utils`） |
| [xcpc_web/](xcpc_web/) | Reflex Web 前端 |
| [data/](data/) | 数据文件（raw / config / db） |
| [wiki/](wiki/) | **项目文档**（技术文档 + 使用手册） |
| [skill/](skill/) | AI Agent Skills |

## 文档

文档在 [`wiki/`](wiki/)，同步发布到 [GitHub Wiki](https://github.com/PHarr-mx/xcpc-rating/wiki)。

**技术文档**（面向二期开发与运维）

| 文档 | 说明 |
|------|------|
| [架构与数据模型](wiki/架构与数据模型.md) | 分层规则、包结构、SQLite 双库与 20 张表、并发与备份、配置、选手/队伍模型 |
| [比赛与导入](wiki/比赛与导入.md) | 统一比赛模型、xlsx 五步导入、通用 JSON 导入、事件生成 |
| [Rating与积分](wiki/Rating与积分.md) | AtCoder 式重放引擎（公式与参数）、榜单与缓存、生涯积分制 |
| [Web与权限](wiki/Web与权限.md) | 路由表、State 划分、认证与三层权限守卫、建号、审计、测试基建 |
| [开发指南](wiki/开发指南.md) | 环境、编码约定、常用任务、**避坑清单**、Agent 协作 |
| [部署运维](wiki/部署运维.md) | 生产构建、rxconfig、Caddy、systemd、备份、上线检查单 |

**使用手册**

| 手册 | 适用对象 |
|------|----------|
| [启动指南](wiki/启动指南.md) | 首次把系统跑起来 |
| [普通用户操作手册](wiki/普通用户操作手册.md) | 访客与 member |
| [管理员操作手册](wiki/管理员操作手册.md) | admin |

## 环境

```bash
source ./setup_env.sh          # uv sync + 激活 .venv
uv sync --extra web            # 追加 Web 依赖
```

依赖与 Python 版本由 `pyproject.toml`（+ `.python-version` = 3.13）统一管理。

## 常用命令

```bash
# 测试（两套分开跑）
uv run python -m pytest xcpc_core -v
cd xcpc_web && ../.venv/bin/python -m pytest tests -v

# 选手 / 队伍
python -m xcpc_core.player.cli list --visible-only
python -m xcpc_core.player.cli get p001 --json
python -m xcpc_core.team.cli list
python -m xcpc_core.team.cli find --members p001 p002

# 通用比赛 JSON 导入
python -m xcpc_core.importer.cli template --entity team
python -m xcpc_core.importer.cli import x.json --dry-run

# 一次性灌数据（幂等）
uv run python -m xcpc_core.db.migrate

# Web 开发
cd xcpc_web && ../.venv/bin/reflex run
```

正式赛 xlsx 导入用 Web `/admin/import`，或 Python API `importer.import_formal_xcpcio_xlsx`。

## 当前状态

**功能开发已完成**：选手/队伍 CRUD、统一比赛模型（tier/awardlevel）、正式赛 xlsx 导入（五步 staged）、通用比赛 JSON 导入、认证与绑定审批、账号由管理员创建（单人 + 批量）、管理后台 10 页、榜单页（AtCoder 式重放，`atcoder_v1`）、选手/比赛详情页、生涯积分制、权重试算页。

**未做**：部署上线（五期，配置产物尚未创建）、OJ 数据源（三表已建、方案未定）。

部署方案见 [部署运维](wiki/部署运维.md)；开发约定与避坑见 [开发指南](wiki/开发指南.md)。