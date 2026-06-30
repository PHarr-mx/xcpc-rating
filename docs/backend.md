# Backend Python

> **代码路径**：`backend/`  
> **架构说明**：见 [DESIGN.md](DESIGN.md)

---

## 1. 目录结构

```
backend/
├── data/                  # 数据流水线
│   ├── import/            # 比赛数据导入（formal xlsx → raw JSON）
│   ├── player/            # 选手 CRUD（API + CLI）
│   ├── team/              # 队伍 CRUD（API + CLI）
│   ├── tests/             # 测试
│   └── utils/             # 公共工具（Plog 日志）
└── site/                  # 站点构建与部署（未实现）
```

---

## 2. `backend/data/` — 数据流水线

### 2.1 已实现

| 模块 | 路径 | 说明 |
|------|------|------|
| **Player CRUD** | `player/` | 选手增删改查，API + CLI 双入口 |
| **Team CRUD** | `team/` | 队伍增删改查（队员集合识别），API + CLI 双入口 |
| **Formal Import** | `import/` | xcpcio_xlsx 解析 → 选手匹配 → 写 raw JSON |
| **Award 计算** | `import/awards.py` | 奖牌线推算 + 百分位兜底 |
| **权重配置** | `import/weights.py` | 读取 contest_weights.yaml |
| **结构化日志** | `utils/plog.py` | 终端彩色 + JSONL 文件双写 |

### 2.2 未实现

- Training import
- OJ import
- Process / Export / Rating pipeline
- `xcpc-data` CLI 入口

### 2.3 模块文档

| 文档 | 说明 |
|------|------|
| [player-module.md](player-module.md) | 选手模块 API + CLI |
| [team-module.md](team-module.md) | 队伍模块 API + CLI |
| [formal-import.md](formal-import.md) | 正式赛 xlsx 导入 |
| [contest-weights.md](contest-weights.md) | 权重配置 |

---

## 3. `backend/site/` — 站点构建（未实现）

设计职责：
- 编排 `npm ci && vite build`
- 部署：`rsync frontend/dist/` + `data/public/` → 服务器
- CLI：`xcpc-site build` / `xcpc-site deploy`

---

## 4. 环境

```bash
# 一键设置
source ./setup_env.sh

# 或手动
conda create -n xcpc_rating python=3.13 pip -y
conda activate xcpc_rating
pip install -r requirements.txt
```

依赖：`pydantic>=2.0`, `openpyxl>=3.1`, `pyyaml>=6.0`

---

## 5. 运行测试

```bash
cd backend
python -m pytest data/tests/ data/import/tests/ utils/tests/ -v
```

---

## 6. 使用 CLI

```bash
# 选手管理
python -m player.cli list --visible-only
python -m player.cli get p001 --json
python -m player.cli create --name 测试 --grade 2025

# 队伍管理
python -m team.cli list --school-only
python -m team.cli find --members p001 p002
python -m team.cli create --members p001 p002 --name "测试队"
```