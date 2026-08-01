# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

校内 XCPC 系列编程竞赛的 Rating 统计与展示系统。当前实现为 **Python 数据流水线 + JSON 数据文件**（选手/队伍名册、正式赛数据导入），尚无运行时后端。

技术栈：Python 3.13、pydantic v2、openpyxl、PyYAML。数据以 JSON 存于 `data/raw/`，逐字可 diff、可进 Git。

> Reflex + SQLite 方案**已采纳**（`docs/DESIGN.md` v4.0）。当前代码仍是 JSON 数据层，按 [docs/13-实施路线图.md](docs/13-实施路线图.md) 向 `xcpc_core`/`xcpc_web` + SQLite 目标架构迁移。新开发按目标结构规划。

## 常用命令

环境（conda 环境 `xcpc_rating`、安装依赖、设置 `PYTHONPATH` 与 `XCPC_RATING_ROOT`）：

```bash
source ./setup_env.sh    # 必须在项目根目录 source
```

测试（须在 `backend/` 下运行，且 `PYTHONPATH` 已生效）：

```bash
cd backend && python -m pytest data/tests/ data/import/tests/ utils/tests/ -v
# 单个测试
cd backend && python -m pytest data/tests/test_team_crud.py -v
```

选手 / 队伍 CLI（`python -m <包>.cli`，在项目根目录运行）：

```bash
python -m player.cli list --visible-only
python -m player.cli get p001 --json
python -m team.cli list
python -m team.cli find --members p001 p002
python -m team.cli create --members p001 p002 --aliases 队名
```

正式赛导入（Python API，`source ./setup_env.sh` 后）：

```python
from datetime import date
from importer import FormalImportParams, import_formal_xcpcio_xlsx
from importer.config import load_school_organizations

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

包为**顶层命名空间**，靠 `PYTHONPATH` 注入，不是嵌套包：

- `backend/data/` → `player`、`team`、`importer`
- `backend/` → `utils`（目前仅 `plog.py`）

`setup_env.sh` 设置 `PYTHONPATH="${ROOT}/backend/data:${ROOT}/backend"`。因此 `import player`、`from utils import Plog` 均可用，但模块间无法用相对导入。

### 数据流

```
data/raw/（人工投放 + import 写入）
  ├── players/roster.json     选手名册
  ├── teams/roster.json       队伍名册
  ├── formal/{contest_id}.json 正式赛（含 standings、award_thresholds、weight）
  └── (训练赛 / OJ 数据源：设计中)
        │
        ▼ import（importer.*）
        ▼ （设计中的 SQLite → Rating 计算 → 榜单；public/ 仅可选导出）
```

`data/config/` 为配置：`contest_weights.yaml`（正式赛按 `contest_type`、训练赛按 `division` 的权重表）、`school.yaml`（本校 Organization 精确匹配名 + 自动建档默认入学年）。

### CRUD 模块分层模式

`player` 与 `team` 采用完全一致的六件套，新增 CRUD 模块照抄此模式：

| 文件 | 职责 |
|------|------|
| `models.py` | Pydantic DTO：`XxxBase` / `XxxCreate` / `XxxUpdate` / 实体类 + 校验器 |
| `store.py` | JSON 持久化；`XxxStore` 可注入 `raw_path` / `repo_root` |
| `service.py` | 业务逻辑（唯一约束、ID 生成、筛选） |
| `api.py` | **对外唯一读写入口**（facade），CLI 与其他子模块都从这里导入 |
| `cli.py` | argparse 命令行 |
| `exceptions.py` | 模块基础异常 + 子类 |
| `__init__.py` | 统一 re-export |

代表路径：`backend/data/player/{models,store,service,api,cli,exceptions}.py`。

### 关键约定

- **禁止直接读写 JSON 文件**，必须经 `player.api` / `team.api`（或 CLI，CLI 与 API 共用同一套 service 逻辑）。
- 各包以 `find_repo_root()` 定位仓库根：基于 `data/` 标志文件向上搜索（`player.store` 看 `data/raw/players/roster.json`，`team.store` 看 `data/config/school.yaml`）。测试用 `repo_root=tmp_path` 注入临时仓库。
- ID 自动生成：选手 `p001`、队伍 `t001`（全局递增，`XxxStore.next_id()`）。选手 `grade=0` 表示入学年未设置。
- 选手软删除 = `status=left`（`mark_left`）；`delete_player` 为物理删除。
- **队伍身份由队员集合决定**，与队名无关：`make_member_key` = 排序后 `"p001|p002|p003"`；同名队员不同队名 → 同一队伍（队名进 `aliases`）；换员 → 新队伍。
- 日志用 `utils.plog.Plog`（终端 + `logs/*.jsonl` 双写），在 CLI 入口实例化后传入下游函数。
- 选手/队伍数据模型要点见 `skill/player-manage/SKILL.md` 与 `skill/team-manage/SKILL.md`。

## 文档与实现状态

- `docs/` 是**已采纳设计**：`DESIGN.md` 为架构总览（Reflex + SQLite），`01` 工程结构，`03`–`11` 业务模块设计，`12` 开发流程建议，`13` 实施路线图。
- **已实现**：选手、队伍 CRUD 与正式赛导入（`backend/data/`，JSON 数据层）。**设计蓝图**：SQLite 存储（`10`）、Rating 计算器（`06`，基类+继承）、榜单（`07`）、Reflex 前端（`08`）、认证（`09`）、部署（`11`）。
- 原 Vue 静态站方案与 Reflex 提案文档已删除（留 Git 历史）。
- `skill/` 目录为 AI Agent Skills（`SKILL.md`），其中的工作流对 Claude 同样适用：`formal-import`、`player-manage`、`team-manage`。开发工作流建议见 `docs/12-开发流程建议.md`。
