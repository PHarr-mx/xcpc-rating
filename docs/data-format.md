# 数据目录与格式

> **数据目录**：`data/`（不含代码）  
> **架构说明**：见 [DESIGN.md](DESIGN.md) 第 2 节

---

## 1. 目录结构

```
data/
├── raw/                    # 原始输入文件
│   ├── players/            # 选手名册
│   ├── formal/             # 正式赛单场文件
│   ├── training/           # 训练赛单场文件
│   └── oj/                 # OJ 数据
│       ├── contests/       # OJ 比赛结果
│       └── snapshots/      # OJ rating + 做题数快照
├── config/                 # 配置文件
│   ├── contest_weights.yaml   # 比赛权重
│   └── school.yaml            # 学校信息
├── processed/              # 规范化中间结果（由 pipeline 生成）
├── public/                 # 面向前端的最终导出
└── schemas/                # JSON Schema（计划中）
```

| 层 | 格式 | 谁写 | 谁读 | Git |
|----|------|------|------|-----|
| `raw/` | JSON | 人工投放 / import 脚本 | process 阶段 | 提交样例 |
| `config/` | YAML | 人工编辑 | import 阶段 | 提交 |
| `processed/` | JSON | process 阶段 | export 阶段 | 忽略 |
| `public/` | JSON | export 阶段 | 前端、Caddy | 可提交样例 |

---

## 2. 选手名册 `raw/players/`

**文件**：`roster.json`

```json
[
  {
    "id": "p001",
    "name": "张三",
    "handle": "zs",
    "grade": 2023,
    "status": "active",
    "oj_accounts": [
      {"platform": "codeforces", "handle": "zhangsan_cf", "user_id": null}
    ],
    "aliases": ["Zhang San"]
  }
]
```

| 字段 | 说明 |
|------|------|
| `id` | 校内唯一 ID，格式 `p{序号}` |
| `name` | 真实姓名 |
| `handle` | 校内简称（可选） |
| `grade` | 入学年份，`0` = 未设置 |
| `status` | `active` / `retired` / `left` |
| `oj_accounts` | OJ 平台账号列表 |
| `aliases` | 曾用名/英文名 |

详见 [player-module.md](player-module.md)。

---

## 3. 正式比赛 `raw/formal/`

### 3.1 文件命名

`{contest_id}.json`，如 `2026_sichuan_provincial.json`

### 3.2 数据来源

- **xcpcio_xlsx**：从 XCPC.io 导出的 `.xlsx` 文件导入（`source_format = xcpcio_xlsx`）
- **手动编写**：人工维护的 JSON

### 3.3 文件结构

根字段：`contest_type`（决定权重）、`format`、`total_teams`、`standings` 等。

详见 [formal-import.md](formal-import.md)。

---

## 4. 校内训练赛 `raw/training/`

### 4.1 文件命名

建议格式：`{year}_w{week}_{format}_{division}.json`，如 `2026_w12_team_xcpc_div1+2.json`

### 4.2 根字段

| 字段 | 说明 |
|------|------|
| `format` | `team_xcpc` / `solo_xcpc` / `oi` |
| `division` | `div1` / `div2` / `div1+2` / `div3` |

**不必写 `weight`**，import 时按 `division` 查 `data/config/contest_weights.yaml`。

### 4.3 权重参考

| division | 权重 |
|----------|------|
| `div1+2` | 100 |
| `div1` | 95 |
| `div2` | 70 |
| `div3` | 60 |

---

## 5. OJ 数据 `raw/oj/`

```
raw/oj/
├── contests/          # 各平台比赛结果导出
└── snapshots/         # 各平台 rating + 做题数导出
    ├── codeforces_2026-06-29.csv
    └── luogu_2026-06-29.json
```

格式允许 CSV / JSON，由 `backend/data/import/` 适配器解析。

---

## 6. 配置文件 `config/`

| 文件 | 说明 |
|------|------|
| `contest_weights.yaml` | 训练赛 division 权重、正式赛 contest_type 权重、OJ 默认权重 |
| `school.yaml` | 学校组织名称、选手默认年级 |

详见 [contest-weights.md](contest-weights.md)。

---

## 7. 处理中间层 `processed/`

由 pipeline 的 process 阶段生成（当前仅少量样例数据）：

| 文件 | 内容 |
|------|------|
| `players.json` | 选手列表（含派生字段） |
| `teams.json` | 队伍列表 |
| `contests_formal.json` | 正式赛元信息 |
| `contests_training.json` | 训练赛元信息 |
| `standings_formal.json` | 正式赛成绩 |
| `standings_training.json` | 训练赛成绩 |
| `rating_events.json` | 归一化事件流 |

---

## 8. 导出层 `public/`

由 pipeline 的 export 阶段生成（计划中）：

```
public/
├── meta.json
├── catalogs/
│   ├── competition_years.json
│   └── seasons.json
├── ratings/
│   ├── formal_only/
│   │   ├── career.json
│   │   ├── year_2025.json
│   │   └── season_2025-春学期.json
│   └── all/
│       └── ...
├── players/
│   └── {id}.json
└── index.json
```

详见 [DESIGN.md](DESIGN.md) 第 2.2 节。