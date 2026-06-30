# xcpc-rating

XCPC 评级数据静态展示站。

## 目录

| 目录 | 说明 |
|------|------|
| [backend/](backend/) | Python 数据流水线 + 站点构建脚本 |
| [data/](data/) | 数据文件（raw / config / processed） |
| [docs/](docs/) | 设计文档、API 文档、Review |
| [skill/](skill/) | Cursor Agent Skills |

## 文档

| 文档 | 说明 |
|------|------|
| [docs/DESIGN.md](docs/DESIGN.md) | 工程架构、目录、部署 |
| [docs/backend.md](docs/backend.md) | Backend 模块概览 |
| [docs/player-module.md](docs/player-module.md) | 选手模块 API + CLI（已实现） |
| [docs/team-module.md](docs/team-module.md) | 队伍模块 API + CLI（已实现） |
| [docs/formal-import.md](docs/formal-import.md) | 正式赛 xlsx 导入（已实现） |
| [docs/contest-weights.md](docs/contest-weights.md) | 比赛权重配置（已实现） |
| [docs/data-format.md](docs/data-format.md) | 数据目录与文件格式 |
| [docs/skills.md](docs/skills.md) | AI Agent Skills |
| [docs/design/](docs/design/README.md) | 业务模块设计（未实现模块的蓝图） |
| [docs/PROJECT_REVIEW.md](docs/PROJECT_REVIEW.md) | 项目整体 Review（2026-06-30） |
| [docs/需求文档.txt](docs/需求文档.txt) | 原始需求 |

## 环境

```bash
source ./setup_env.sh   # 创建 conda 环境、安装依赖、设置 PYTHONPATH
```

或手动：

```bash
conda create -n xcpc_rating python=3.13 pip -y
conda activate xcpc_rating
pip install -r requirements.txt
```

## 常用命令

```bash
# 选手管理
python -m player.cli list --visible-only
python -m player.cli get p001 --json

# 队伍管理
python -m team.cli list --school-only
python -m team.cli find --members p001 p002

# 正式赛导入（Python API）
python -c "
from importer import FormalImportParams, import_formal_xcpcio_xlsx
from importer.config import load_school_organizations
from datetime import date
result = import_formal_xcpcio_xlsx('比赛.xlsx', FormalImportParams(
    contest_id='2026_xxx', date=date(2026,5,18),
    contest_type='icpc_provincial',
    school_organizations=load_school_organizations(),
))
"

# 运行测试
cd backend && python -m pytest data/tests/ data/import/tests/ utils/tests/ -v
```

## 待实现

```bash
xcpc-data update      # 更新 data/public/
xcpc-site build       # 构建 frontend/dist/
xcpc-site deploy      # 部署到服务器
```