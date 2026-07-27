# Reflex Web 改造提案

> **状态：提案 · 待评审 · 未实施**
> 提出日期：2026-07-27
> 关联：[DESIGN.md](../DESIGN.md) · [数据存储与迁移](./10-数据存储与迁移-SQLite.md) · [认证与权限](./11-认证与权限模块.md) · [Web 交互与页面](./12-Web交互与页面-Reflex.md)

本文提出用 **Reflex** 把项目从「静态展示站」改造为「可交互 Web 应用」。
**当前架构（Vue 3 静态站 + Caddy file_server）仍是仓库的既定设计**，见 [DESIGN.md](../DESIGN.md)。
本提案被采纳后，才按 §10 的清单改写既有文档。

---

## 1. 动机

现在这些操作只能敲 CLI 或写 `python -c` 脚本：

| 操作 | 现状 |
|------|------|
| 导入正式赛 xlsx | `python -c "from importer import FormalImportParams, ..."` 一大段 |
| 处理未匹配选手 | 改 raw JSON 或重跑导入 |
| 补全选手 grade / OJ 账号 | `python -m player.cli update` 逐个敲 |
| 调整比赛权重看榜单变化 | 改 YAML → 重跑流水线 → 刷新页面 |
| 队员查自己的记录 | 只能看公开榜单，无法自助维护资料 |

这些是「交互」需求，静态站无法承载。**若最终只需要只读展示，原 Vue 静态方案更合适**（见 §9 反面论证）。

---

## 2. 本质：运行时模型被替换

Reflex 编译出 React 前端，但**所有状态在服务端**，浏览器通过 WebSocket 收发事件。
这与「构建期算完 → 静态 JSON → 线上无 Python 无数据库」直接冲突。

| | 现在 | 改造后 |
|---|---|---|
| 线上进程 | 无 | 常驻 Python（FastAPI + WebSocket） |
| 数据库 | 无 | SQLite（WAL） |
| 前端 | Vue 3 + Vite，手写 TS | Reflex 编译产物，无手写 JS/TS |
| 数据获取 | 浏览器 `fetch('/data/*.json')` | State 事件处理器直接调 Service 层 |
| Caddy | `file_server` | 静态资源 `file_server` + 后端 `reverse_proxy` |
| 构建期 Node | 需要（Vite） | 仍需要（Reflex 编译 React） |
| `frontend/` 目录 | 计划创建 | 不再需要，取消创建 |
| 榜单文件矩阵 | `mode × period` 每组合一个 JSON | 不需要，筛选条件是 state var |

### 2.1 前后端如何交互

**不写任何交互代码** —— 没有 REST 接口，没有 `fetch`，没有手写序列化。
这是与现有 Vue 方案最大的区别。

编译产物是 Next.js SPA（默认 3000 端口），Python 侧是 FastAPI（8000），
两者之间**一条 WebSocket 长连接**：

```
用户交互 → 前端事件队列 → WebSocket
   → 后端按 client token 取出对应 State 实例
   → 执行 Python 事件处理器（可直接查数据库）
   → 计算 dirty vars（仅真正变化的字段）
   → state delta 回传 → React 重渲染
```

| 机制 | 说明 | 对本项目的影响 |
|------|------|----------------|
| **client token** | 每个浏览器标签页一个，索引到后端一个独立 State 实例 | 同一人开两个标签页，榜单筛选互不干扰 |
| **delta 更新** | 只传变化的 var，不传全量 state | 切换筛选不会重推整张榜单 |
| **前端事件队列** | `processing` 标志保证一次只处理一个事件 | 防竞态；但长任务会卡 UI，需 `@rx.event(background=True)` |
| **StateManager** | 默认是**进程内存字典** | 单进程约束，见 §8 与 [10](./10-数据存储与迁移-SQLite.md) §7.4 |

背景任务修改 state 必须包在 `async with self` 中（取独占锁），
在块外写 state 会抛 `ImmutableStateError`，块外读可能取到过期值。

具体到榜单页：`BoardState.mode` 从 `all` 切到 `formal_only`，浏览器发一个事件，
服务端重算榜单并回推新的 `rows`。
**原 [08](./08-前端展示模块.md) §6「数据加载」整节（`lib/api.ts`、三个 composable、
预生成 JSON 路径规则）在此方案下不存在。**

---

## 3. 已确定的三个决策

| 决策项 | 选定 | 理由 |
|--------|------|------|
| 交互范围 | **多用户自助** | 队员可登录维护自己的 OJ 账号/别名；admin 管全量。需完整用户体系，见 [11](./11-认证与权限模块.md) |
| 域数据存储 | **全量迁移 SQLite** | 网页写入引入并发；`rx.Model` + alembic 是 Reflex 原生路径。见 [10](./10-数据存储与迁移-SQLite.md) |
| 部署形态 | **自有服务器：Caddy 反代 + systemd** | 沿用已有 Caddy；数据文件与备份自己掌控 |

---

## 4. 顶层目录结构

用一个 `pyproject.toml` 统一打包，顺带解决 [PROJECT_REVIEW](../PROJECT_REVIEW.md) §3.3 记录的
「`importer`/`player` 平铺靠 PYTHONPATH」偏差。

```
xcpc-rating/
├── pyproject.toml              # 唯一包管理入口，替代 PYTHONPATH hack
├── rxconfig.py                 # Reflex 配置
├── alembic/                    # reflex db init 生成
├── xcpc_core/                  # 纯业务层，不 import reflex
│   ├── db/                     # 表定义 + session + 迁移脚本
│   ├── player/  team/          # 由现有 backend/data/{player,team} 迁入
│   ├── contest/                # formal + training 统一
│   ├── importer/               # 由现有 backend/data/import 迁入（import 是关键字）
│   ├── rating/                 # 按 06 文档实现 BaseRatingCalculator 体系
│   ├── board/                  # 按 07 文档实现榜单聚合
│   └── auth/                   # 用户、角色、绑定选手
├── xcpc_web/                   # Reflex 应用，只做 UI 与状态
│   ├── xcpc_web.py             # app = rx.App(...)
│   ├── states/  pages/  components/  assets/
├── data/
│   ├── raw/                    # 保留：人工投放归档 + 导入源，可 diff 可进 Git
│   ├── db/xcpc.db              # SQLite，gitignore
│   ├── uploads/                # 上传的 xlsx 暂存
│   └── public/                 # 降级为可选：对外只读导出 / 备份快照
└── docs/
```

### 4.1 两条硬性分层规则

**`xcpc_core` 绝不 `import reflex`。**
CLI、pytest、未来的定时任务都能脱离 web 运行，现有 24 个测试的价值全部保留。

**`xcpc_web` 绝不写 SQL，也不承载业务规则。**
State 只做四件事：读表单 → 调 `xcpc_core` 函数 → 转视图模型 → 写 state var。

违反任一条，都会让业务逻辑与框架绑死，后续换框架或加 CLI 入口都要重写。

---

## 5. Rating 计算与缓存

[06-Rating计算模块](./06-Rating计算模块.md) 的 `BaseRatingCalculator` + 继承体系设计**无需改动**，直接实现。
变的只是触发时机与结果去向：从「构建期算完写 JSON」改为「运行时按需算 + 内存缓存」。

```python
@lru_cache(maxsize=256)
def board(mode: str, period_key: str, data_version: int) -> BoardSnapshot: ...
```

`data_version` 存单行 meta 表；任何写操作（改选手、导比赛、调权重）令其 +1，缓存自然失效。
当前规模（24 选手、数十场比赛）全量重算是毫秒级，不需要增量缓存。

**权重试算**（[12](./12-Web交互与页面-Reflex.md) 的 `RatingLabState`）走独立路径：用草稿权重计算，
结果不落库、不进缓存，仅在页面上与当前榜单做 diff；admin 点「应用」才写
`data/config/contest_weights.yaml` 并 bump `data_version`。

`data/public/` 导出降级为**可选功能**，保留两个用途：对外提供只读 JSON、定期快照备份。
不再是前端的数据来源。

---

## 6. 部署

`reflex run --env prod` 默认前端听 3000、后端听 8000。更省资源的做法是
**让 Caddy 直接托管前端静态产物，只反代后端**。

### 6.1 构建

```bash
# 需要 Node/bun。建议本地构建后 rsync 产物，服务器保持干净
reflex export --frontend-only --no-zip     # → .web/build/client/
rsync -a .web/build/client/ server:/var/www/xcpc-rating/
```

### 6.2 `rxconfig.py`

```python
config = rx.Config(
    app_name="xcpc_web",
    api_url="https://rating.example.com",   # 公网可达地址
    db_url="sqlite:///data/db/xcpc.db",
)
```

> `api_url` 配错是自托管最常见的坑 —— 它决定浏览器往哪连 WebSocket。
> 写 `localhost` 就只有本机能用。也可用环境变量 `API_URL` 覆盖。

### 6.3 Caddyfile

```caddyfile
rating.example.com {
    encode gzip zstd

    # 后端：事件 WebSocket、上传、健康检查。Caddy 自动处理 WS 升级
    @backend path /_event* /_upload* /_health* /ping* /_all_routes*
    reverse_proxy @backend localhost:8000

    root * /var/www/xcpc-rating
    @assets path /assets/*
    header @assets Cache-Control "public, max-age=31536000, immutable"
    try_files {path} {path}/ /index.html
    file_server
}
```

如需把后端挂到子路径，用 Reflex 的 `backend_path` 配置项，代理侧无需重写请求。

### 6.4 systemd

```ini
# /etc/systemd/system/xcpc-rating.service
[Service]
WorkingDirectory=/opt/xcpc-rating
ExecStart=/opt/xcpc-rating/.venv/bin/reflex run --env prod --backend-only
Restart=always
Environment=API_URL=https://rating.example.com
[Install]
WantedBy=multi-user.target
```

原 [DESIGN.md](../DESIGN.md) §10.1 的数据 cron（`xcpc-data export`）**删除** —— 数据是运行时算的。
改为一条 SQLite 备份 cron，见 [10](./10-数据存储与迁移-SQLite.md) §7。

---

## 7. 分期实施

| 期 | 内容 | 结束标志 |
|----|------|----------|
| **一期 · 地基** | `pyproject.toml` 统一打包（修掉 PYTHONPATH 偏差）、建表、JSON 一次性迁移、Reflex 骨架、`/` 榜单只读页 | 能用真实数据看到榜单 |
| **二期 · 认证** | 接入 `reflex-local-auth`、角色与绑定审批、`/profile`、审计日志 | 权限三处校验点立稳 |
| **三期 · 管理后台** | 选手/队伍 CRUD、xlsx 在线导入 + 交互式匹配 | 不再需要敲 CLI 导入 |
| **四期 · 业务补齐** | 训练赛录入、Rating 计算器实现、权重试算页、图表 | 榜单数值有业务含义 |
| **五期 · 上线** | systemd + Caddy + 备份 cron | 公网可访问 |

两条顺序约束：

- **一期必须最先**。包结构不统一，后面每步都在跟 PYTHONPATH 打架。
- **二期必须在三期之前**。否则会先做出一批无认证的写接口。

---

## 8. 风险

| 风险 | 说明 | 应对 |
|------|------|------|
| **预渲染泄露** | Reflex 静态预渲染页面，写在组件树里的数据对所有人可见 | 私有数据必经带权限判断的 computed var，见 [11](./11-认证与权限模块.md) §4 |
| **内存状态与单进程** | StateManager 默认是进程内存字典（按 client token 索引）。多 worker 会让同一用户的两次请求落到不同进程、看到不同 state；官方生产环境用 Redis | 当前规模单进程足够，**不要加 `--workers`**。顺带保证 SQLite 只有一个写进程 |
| **SQLite 写并发** | 多人同时写可能锁表 | 开 WAL；真需要时 `db_url` 换 Postgres 即可 |
| **构建期工具链** | 服务器需 Node/bun | 本地构建后 rsync 产物（§6.1） |
| **Reflex 版本流动** | 0.9.x 仍在快速变（近期移除 `CustomComponent`，改用 `rx.memo`） | requirements 锁死 `reflex` 与各 `reflex-components-*` 具体版本，升级作独立任务 |
| **运维复杂度上升** | 多了会崩的常驻进程 + 要备份的数据库 | 见 §9 |

---

## 9. 反面论证：什么情况下不该做

改造后**不再是**「线上无 Python、无 Node、无数据库」。原设计 [DESIGN.md](../DESIGN.md) §7 的
这个特性是实打实的运维优势，换掉它得到的是交互能力。

若评审后发现：

- 实际只需要只读展示，写操作仍愿意用 CLI 完成；
- 没人会真的登录维护自己的资料；
- 不希望服务器上多一个常驻进程和数据库备份负担；

那么**保持现有 Vue 3 静态站方案更合适**，本提案应被否决。
在这种情况下更划算的投入是把 [PROJECT_REVIEW](../PROJECT_REVIEW.md) §7.2 的 P0 项
（process / rating / export 流水线）做完。

---

## 10. 采纳后需改写的文档

本提案通过评审后，按此清单更新既有文档：

| 文档 | 处理 |
|------|------|
| [DESIGN.md](../DESIGN.md) | §1 目录、§2 数据分层、§5 frontend、§7 运行时、§8 选型、§9 构建发布、§10 Caddy、§11 工作流 大改；§13 MVP 清单重写 |
| [08-前端展示模块](./08-前端展示模块.md) | 整篇由 [12](./12-Web交互与页面-Reflex.md) 取代，Vue 版本留 Git 历史 |
| [05-数据导出与发布模块](./05-数据导出与发布模块.md) | `public/` 从「前端数据源」降级为「可选只读导出」；原子导出逻辑保留给备份 |
| [04-数据导入与加工模块](./04-数据导入与加工模块.md) | 增「Web 交互式导入」一节（`ImportBatch` 暂存 + 人工复核） |
| [03-比赛与记录模块](./03-比赛与记录模块.md) | 增 SQLite 表结构映射；说明 formal/training 合表 |
| [06](./06-Rating计算模块.md) · [07](./07-榜单模块.md) | 基本不动，算法与榜单定义仍成立 |
| [data-format.md](../data-format.md) | raw 保留说明 + DB schema 位置 |
| [backend.md](../backend.md) · [README.md](../../README.md) | 包结构、命令、环境 |
| `skill/*/SKILL.md` | 三份 SKILL 内的 CLI 路径随包结构改动 |

---

## 11. 开放问题

| 项 | 状态 |
|----|------|
| 是否保留 `xcpc-data` CLI 作为 web 之外的第二入口 | 建议保留，`xcpc_core` 不依赖 reflex 即为此 |
| `data/public/` 只读导出是否真有外部消费者 | 待确认，无则可完全砍掉 |
| 队员自助的实际使用意愿 | 待确认，直接影响 §9 的结论 |

---

*文档版本：v1.0 — 提案，未实施。*


