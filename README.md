# xcpc-rating

XCPC 评级数据静态展示站。

## 目录

| 目录 | 说明 |
|------|------|
| [frontend/](frontend/) | Vue 3 + Vite 前端 |
| [backend/data/](backend/data/) | 数据更新脚本（fetch / process / export） |
| [backend/site/](backend/site/) | 站点构建与部署脚本 |
| [data/](data/) | 数据文件（raw / processed / public） |
| [docs/](docs/) | 设计文档与部署配置 |
| [skill/](skill/) | Cursor Agent Skills |

## 文档

| 文档 | 说明 |
|------|------|
| [docs/DESIGN.md](docs/DESIGN.md) | 工程架构、目录、部署 |
| [docs/design/](docs/design/README.md) | 业务模块详细设计 |
| [docs/需求文档.txt](docs/需求文档.txt) | 原始需求 |

## 环境

```bash
source ./setup_env.sh   # 创建/检查 conda 环境、安装依赖、设置 PYTHONPATH
```

或手动：

```bash
conda create -n xcpc_rating python=3.13 pip -y
conda activate xcpc_rating
pip install -r requirements.txt
```

> `conda create -n xcpc_rating` 不带 `python=` 只会创建空环境，无法直接运行代码。

## 常用命令（待实现）

```bash
xcpc-data update      # 更新 data/public/
xcpc-site build       # 构建 frontend/dist/
xcpc-site deploy      # 部署到服务器
```
