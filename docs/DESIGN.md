# xcpc-rating 项目设计

> **Python** 负责数据采集与处理，**Vue 3 静态站**展示结果，**Caddy** 托管线上文件。  
> 技术栈：Vue 3 + Vite + Vue Router + TypeScript；数据以 **JSON** 为主（构建期可按需引入 SQLite）。

**业务详细设计**（选手、队伍、比赛、Rating、前端）见 **[docs/design/](design/README.md)**，依据 [需求文档.txt](需求文档.txt) 展开。

**已实现的后端 API 文档**：[backend-player-module.md](backend-player-module.md)（选手增删改查，CLI 与编程接口）。

---

## 1. 仓库顶层划分

仓库按职责拆为五个顶层目录，边界清晰、互不混放：

```
xcpc-rating/
├── frontend/          # 前端：Vue 3 源码与 Vite 构建
├── backend/
│   ├── data/          # 后端 · 数据：拉取、清洗、计算、导出
│   └── site/          # 后端 · 站点：组装静态产物、部署脚本
├── data/              # 数据文件（raw / processed / public）
├── docs/              # 文档（本文件、部署配置等）
├── skill/             # Cursor Agent Skills（项目专属指引）
├── pyproject.toml     # Python 工作区（backend 两个子包）
└── README.md
```

### 1.1 各目录职责

| 目录 | 职责 | 运行时 |
|------|------|--------|
| `frontend/` | 页面、组件、路由；`vite build` 产出 JS/CSS/HTML | 浏览器 |
| `backend/data/` | 更新数据的 Python 包与 CLI | 仅构建/cron |
| `backend/site/` | 调用 Vite、同步 `data/public`、rsync 部署 | 仅构建/部署 |
| `data/` | 磁盘上的数据文件（见第 2 节） | 被 Caddy 以静态文件提供 |
| `docs/` | 设计、部署说明 | — |
| `skill/` | 给 AI / 协作者的领域技能文件 | — |

### 1.2 为何 `backend` 拆成 `data` 与 `site`

两者触发频率与依赖不同，不宜混在一个 `scripts/` 里：

| 子目录 | 回答的问题 | 典型命令 | 依赖 |
|--------|------------|----------|------|
| **`backend/data/`** | 数据最新了吗？ | `xcpc-data update` | httpx、pydantic、可选 pandas |
| **`backend/site/`** | 站点构建好了吗？能上线吗？ | `xcpc-site build` / `xcpc-site deploy` | Node（仅构建时）、rsync |

```
                    ┌─────────────────┐
  外部数据源 ────────▶│ backend/data/   │
                    │  fetch→process  │
                    └────────┬────────┘
                             │ 写入
                             ▼
                    ┌─────────────────┐
                    │ data/public/    │◀── 线上 /data/*.json
                    └────────┬────────┘
                             │ 读取（开发时 proxy）
                             ▼
                    ┌─────────────────┐
                    │ frontend/       │
                    │  vite build     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ backend/site/   │──▶ rsync → 服务器
                    │  build + deploy │
                    └─────────────────┘
```

**服务器 cron 通常只跑 `backend/data`**（日更 JSON）；改 UI 时才跑 `backend/site build`。

---

## 2. 数据目录与文件格式（`data/`）

`data/` 只放**文件**，不放 Python 代码。按处理阶段分三层：

```
data/
├── raw/                    # 原始抓取缓存（建议 .gitignore）
│   └── contests/
│       └── {contest_id}.json
├── processed/              # 规范化中间结果（建议 .gitignore）
│   ├── players.json
│   ├── contests.json
│   └── standings.json
├── public/                 # 面向前端的最终导出（部署为网站 /data/）
│   ├── meta.json
│   ├── ratings.json
│   ├── ratings/
│   │   └── page-{n}.json
│   └── players/
│       └── {id}.json
└── schemas/                # JSON Schema，约束 public 输出与 TS 类型
    ├── meta.schema.json
    ├── ratings.schema.json
    └── player.schema.json
```

### 2.1 三层含义

| 层 | 格式 | 谁写 | 谁读 | Git |
|----|------|------|------|-----|
| `raw/` | JSON（或 HTML 缓存） | `backend/data` fetch | `backend/data` process | 忽略 |
| `processed/` | JSON 数组/对象，偏「表」 | process | export | 忽略 |
| `public/` | JSON，偏「API 响应」 | export | `frontend`、Caddy | 可提交样例 |

**不必一开始用 SQLite**：`processed/` 用 JSON 即可；表变多或要增量更新时，再在 `backend/data` 内引入 SQLite 作为可选中间层，**导出目标仍是 `data/public/`**。

### 2.2 `public/` 文件约定

#### `meta.json`（必选）

```json
{
  "built_at": "2026-06-29T06:00:00Z",
  "data_version": 3,
  "git_sha": "abc1234",
  "counts": {
    "players": 12000,
    "contests": 450
  }
}
```

#### `ratings.json`（排行榜主表）

扁平数组，一行一条，字段与表头对齐：

```json
[
  { "rank": 1, "id": "p001", "name": "张三", "school": "XX大学", "rating": 2456 },
  { "rank": 2, "id": "p002", "name": "李四", "school": "YY大学", "rating": 2410 }
]
```

超过约 5000 行时改为分页：

```
public/ratings/page-1.json
public/ratings/page-2.json
```

`meta.json` 或 `ratings/index.json` 记录分页信息。

#### `players/{id}.json`（详情，按需加载）

```json
{
  "id": "p001",
  "name": "张三",
  "school": "XX大学",
  "rating": 2456,
  "history": [
    { "date": "2026-05-01", "rating": 2400, "contest_id": "c100" }
  ]
}
```

### 2.3 格式选型

| 场景 | 格式 |
|------|------|
| 原始缓存、中间表、`public` 导出 | **JSON** |
| 项目配置（数据源 URL、权重） | **YAML**，放 `backend/data/config.yaml` 或根配置 |
| 本地人工查看大表 | **CSV** 可作为 `processed/` 的补充，非必须 |
| 线上 | 仅 **JSON**（Caddy 静态托管） |

### 2.4 原子写入与失败回滚

`backend/data` 导出时应：

1. 写入 `data/public/.staging/`
2. 校验 schema
3. `rename` 替换 `data/public/`（或逐文件替换）

避免 cron 写到一半导致前端读到半截 JSON。

---

## 3. `backend/data/`（更新数据）

```
backend/data/
├── pyproject.toml          # 可选：子包独立依赖；也可只用根 pyproject.toml
├── config.yaml.example     # 数据源、路径配置
└── src/xcpc_data/
    ├── __init__.py
    ├── cli.py              # xcpc-data 入口
    ├── fetch/              # 按数据源拆分
    ├── processors/         # 清洗、评级算法
    ├── models/             # Pydantic
    └── export/             # processed → data/public/
```

### 3.1 CLI

```bash
# 完整更新：fetch → process → export
xcpc-data update

# 分步
xcpc-data fetch
xcpc-data process
xcpc-data export

# 指定输出目录（默认仓库 data/public/）
xcpc-data export --output /var/www/xcpc-rating/data
```

### 3.2 路径配置（`config.yaml`）

```yaml
paths:
  raw: ../../data/raw
  processed: ../../data/processed
  public: ../../data/public
```

路径相对于仓库根目录解析，避免硬编码绝对路径。

---

## 4. `backend/site/`（构建前端页面）

```
backend/site/
└── src/xcpc_site/
    ├── __init__.py
    ├── cli.py              # xcpc-site 入口
    ├── build.py            # npm ci && vite build
    └── deploy.py           # rsync frontend/dist + data/public
```

`backend/site` **不写业务数据逻辑**，只编排：

1. （可选）检查 `data/public/meta.json` 是否存在
2. `cd frontend && npm ci && npm run build`
3. 部署时：`rsync frontend/dist/` 与 `data/public/` → 服务器

### 4.1 CLI

```bash
# 本地构建前端
xcpc-site build

# 构建并部署
xcpc-site deploy --host user@server --path /var/www/xcpc-rating
```

部署脚本见 `docs/deploy/deploy.sh`。

---

## 5. `frontend/`（Vue 3）

```
frontend/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.ts
    ├── App.vue
    ├── router/index.ts
    ├── views/              # HomeView, PlayerView, …
    ├── components/         # RatingTable, RatingChart
    ├── composables/        # useRatings.ts
    ├── types/rating.ts
    └── lib/api.ts          # fetch(import.meta.env.BASE_URL + 'data/…')
```

开发与构建时，**不从 `frontend/public/data` 复制一份**；统一读仓库根 `data/public/`：

```typescript
// vite.config.ts — 开发代理
server: {
  proxy: {
    '/data': {
      target: 'http://localhost:8765',
      // 本地: python -m http.server 8765 -d ../data/public
    },
  },
},
```

构建产物在 `frontend/dist/`（仅 HTML/JS/CSS）；**JSON 不打进 bundle**，运行时请求 `/data/*.json`。

---

## 6. `docs/` 与 `skill/`

```
docs/
├── 需求文档.txt
├── DESIGN.md               # 本文件：工程架构
├── design/                 # 业务模块设计（详见 design/README.md）
│   ├── 01-选手模块.md
│   ├── 02-队伍模块.md
│   ├── 03-比赛与记录模块.md
│   ├── 04-数据流水线模块.md
│   ├── 05-Rating与榜单模块.md
│   └── 06-前端展示模块.md
└── deploy/
    ├── Caddyfile.snippet
    └── deploy.sh

skill/
└── README.md               # 说明如何添加本项目 Cursor Skills
```

- **docs/**：给人看的设计与运维文档。  
- **skill/**：给 Cursor Agent 用的 `SKILL.md`（如「如何跑数据更新」「评级字段含义」），与代码分离，避免塞进注释。

---

## 7. 方案本质与运行时

```
┌─────────────────────────────────────────────────────────────┐
│  构建时（本地 / CI / 服务器 cron）                              │
│  xcpc-data update  →  data/public/                           │
│  xcpc-site build   →  frontend/dist/                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  运行时（服务器）                                              │
│  浏览器 ──HTTPS──▶ Caddy ──▶ index.html + assets/ + data/    │
│  ❌ 无 Node  ❌ 无 Python  ❌ 无数据库                         │
└─────────────────────────────────────────────────────────────┘
```

Vue 3 开发时是 SPA，`vite build` 后仍是纯静态文件。

---

## 8. 技术选型

| 模块 | 选型 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Vue Router |
| UI | Naive UI 或 Element Plus |
| 图表 | ECharts + vue-echarts |
| 数据脚本 | Python 3.12+、httpx、pydantic |
| 部署 | 自有服务器 + Caddy `file_server` |

---

## 9. 构建与发布流程

### 9.1 日常：只更新数据

```bash
xcpc-data update
# 服务器 cron 示例：
# xcpc-data export --output /var/www/xcpc-rating/data
```

### 9.2 发版：改 UI 后

```bash
xcpc-data update          # 确保 public 最新
xcpc-site build
xcpc-site deploy
```

### 9.3 服务器目录（与仓库对应）

```
/var/www/xcpc-rating/
  index.html          ← frontend/dist/
  assets/             ← frontend/dist/assets/
  data/               ← data/public/（可单独 rsync）
```

---

## 10. 自有服务器部署（Caddy）

假设 **已运行 Caddy**。配置片段见 `docs/deploy/Caddyfile.snippet`。

```caddyfile
rating.example.com {
    root * /var/www/xcpc-rating
    encode gzip zstd

    @assets path /assets/*
    header @assets Cache-Control "public, max-age=31536000, immutable"

    @data path /data/*
    header @data Cache-Control "public, max-age=300, must-revalidate"

    try_files {path} {path}/ /index.html
    file_server
}
```

```bash
caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

子路径部署、与其他 `reverse_proxy` 共存等细节见原文档第 6.4–6.5 节（路径已改为 `docs/deploy/`）。

### 10.1 cron（仅数据）

```cron
0 6 * * * cd /opt/xcpc-rating && .venv/bin/xcpc-data export --output /var/www/xcpc-rating/data >> /var/log/xcpc-rating-data.log 2>&1
```

---

## 11. 开发工作流

```bash
# 终端 1：导出样例数据并托管 public/
xcpc-data export
python -m http.server 8765 -d data/public

# 终端 2：前端热更新
cd frontend && npm run dev
```

改 UI 不动 `backend/data`；改算法不动 `frontend`。契约在 `data/schemas/`。

---

## 12. 非功能需求

- [ ] `meta.json` 记录 `built_at`、`data_version`
- [ ] 导出失败时不覆盖上次成功的 `data/public/`
- [ ] `data/raw`、`data/processed` 加入 `.gitignore`
- [ ] 可选：由 schema 生成 `frontend/src/types/`

---

## 13. MVP 清单

1. `backend/data`：样例 fetch + export → `data/public/ratings.json`、`meta.json`
2. `frontend`：一页表格 + 一条 ECharts 曲线
3. `backend/site build`：产出 `frontend/dist/`
4. Caddy 指向 `/var/www/xcpc-rating`
5. cron 每日 `xcpc-data export`

---

## 附录 A：`vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router'],
          charts: ['echarts', 'vue-echarts'],
        },
      },
    },
  },
});
```

## 附录 B：关于原 `DESIGN.md`

根目录 **`DESIGN.md` 已移除**。该文件是早期多方案（A–E）比选文档；项目已确定 **方案 D（Vue 3 + JSON + Caddy）**，内容与本文重复且易误导，故不再维护。若需回顾其他方案，可查 Git 历史。

---

*文档版本：v2.1 — 业务模块设计见 docs/design/。*
