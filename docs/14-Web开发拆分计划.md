# Web 开发拆分计划

> 关联：[08-前端与Web交互模块](./08-前端与Web交互模块.md)（设计蓝图：State / 路由 / 页面） · [12-开发流程建议](./12-开发流程建议.md)（怎么做） · [13-实施路线图](./13-实施路线图.md)（分期验收）

08 说「Web 做成什么样」，13 说「分期验收标准」，**本文说「Web 开发拆成几块、每块做什么、按什么顺序做」**。

---

## 1. 原则

- **`xcpc_core` 不 import reflex；`xcpc_web` 不写 SQL、不承载业务规则**（[12](./12-开发流程建议.md) §3.1）
- State 只做「读表单 → 调 core → 转视图模型 → 写 var」；视图模型用 `rx.Base`，不把 Pydantic 塞进 state var（[08](./08-前端与Web交互模块.md) §2.1）
- 每个 Part 可独立验收：跑起一个命令、看到一个能用的页面即算完成
- Reflex 锁 `0.9.7`，组件分包（`reflex-components-core` / `-lucide`）按 [08](08-前端与Web交互模块.md) §1

## 2. 拆分总览

| Part | 内容 | 对应期 | 依赖 | 验收 |
|------|------|--------|------|------|
| **P0** ✅ | 工程地基：装依赖、`reflex init`、包骨架、dev 脚本 | 一期 | 无 | `reflex run` 起空壳页，能 import `xcpc_core` |
| **P1** ✅ | 榜单只读页 `/` | 一期（收官） | P0 | 浏览器看到真实数据榜单，筛选/搜索/排序可用 |
| **P2** | 认证底座：登录注册 + AuthState + 权限守卫 | 二期 | P1 | 未登录访问 `/profile` 被重定向 |
| **P3** | `/profile` 自助资料 + 绑定申请 | 二期 | P2 | 用户可提交绑定申请 |
| **P4** | 后台 CRUD：players / teams / contests / users / audit | 三期 | P2 | admin 在 Web 完成全部增删改查 |
| **P5** | 在线导入 `/admin/import` | 三期 | P4 | 不再需要敲 CLI 导入 |
| **P6** | 详情页与图表：`/players/{id}` `/contests/{id}` `/about` | 一期后即可插入 | P1 | 详情页渲染真实记录，Rating 曲线可见 |
| **P7** | 权重试算 `/admin/rating` | 四期 | P4 | 试算 diff 可见，应用后榜单变化 |

顺序约束：**P0→P1 最先；P2→P3 必须先于 P4/P5**（否则会先做出一批无认证的写接口，[13](./13-实施路线图.md) §2）。
P6 是纯只读页，不依赖认证，建议紧跟 P1 做掉（一期/二期间隙），也可推迟。

## 3. 目标包结构

```
xcpc_web/
├── xcpc_web/
│   ├── xcpc_web.py          # app 入口：注册全部页面（reflex init 生成后改造）
│   ├── states/
│   │   ├── auth.py          # AuthState（P2）
│   │   ├── views.py         # BoardRowView 等 rx.Base 视图模型 + 领域→视图转换（P1）
│   │   ├── board.py         # BoardState（P1）
│   │   ├── player_detail.py # PlayerDetailState（P6）
│   │   ├── contest_detail.py# ContestDetailState（P6）
│   │   ├── profile.py       # ProfileState（P3）
│   │   └── admin/           # AdminPlayer/Team/Contest/User/Import/RatingLab（P4/P5/P7）
│   ├── pages/               # 一个路由一个文件，与 08 §3 路由表一一对应
│   ├── components/          # layout / board_table / period_selector / rating_chart 等（08 §5）
│   └── config.py            # API 端口、OJ 外链模板等
├── assets/
└── rxconfig.py
```

`xcpc_web` 与 `xcpc_core` 平级，通过已安装的 `xcpc_core` 包引用（editable install），不复制代码。

## 4. 各 Part 详解

### P0 · 工程地基 ✅（2026-08-18）

任务：

1. ✅ `uv sync --extra web`（reflex==0.9.7 已在 `pyproject.toml` `[web]` extra 中声明）
2. ✅ 仓库根 `reflex init`，把生成的脚手架整理为上面的包结构；`rxconfig.py` 中 `app_name="xcpc_web"`
3. ✅ 验证 `xcpc_web` 内能 `from xcpc_core.board import api`（editable 安装已覆盖）
4. ✅ `.gitignore` 补 Reflex 产物：`.web/` `.states/` `assets/external/`；README / CLAUDE.md 补启动命令
5. ✅ 首页 (`pages/index.py`) 展示真实数据版本、选手人数，确认数据桥接通

验收：`reflex run` 起来，浏览器打开空壳页无报错；`pytest xcpc_core` 仍全绿（证明 web 依赖未污染 core）。

坑：Reflex 首次 init 会下载前端运行时；确认 Python 3.13 与 0.9.7 兼容（不兼容则锁一个兼容版本并同步改 pyproject，升级作独立任务）。已通过，无问题。

### P1 · 榜单只读页 `/` ✅（2026-08-18，一期收官）

任务：

1. ✅ `states/views.py`：`BoardRowView(rx.Base)`、`BoardMetaView`，转换函数（[08](08-前端与Web交互模块.md) §2.1）
2. ✅ `states/board.py`：`BoardState` —— `mode` / `period_type` / `period_id` / `search` / `sort_by`，`rows` 用 `@rx.var(cache=True)` 调 `board_api.board(...)` 并复用 `data_version` 缓存（[08](08-前端与Web交互模块.md) §2.2）
3. ✅ `components/layout.py`：`page_shell`（nav + footer）
4. ✅ `components/board_table.py`：表格，表头点击切 `sort_by`；meta 条展示 `algorithm` + `data_version`
5. ✅ `components/period_selector.py`：mode 单选 + 周期下拉（周期选项从 `xcpc_core.utils.calendar` 取）
6. ⬜ 筛选条件同步 URL query（`on_load` 读 `self.router.page.params`，事件里 `rx.redirect` 带参）
7. ✅ `status=left` 不显示；`retired` 显示退役标记（[08](08-前端与Web交互模块.md) §4.1）

验收：浏览器看到 21 行真实榜单；切换 mode/周期/搜索均实时生效；刷新带参 URL 状态保持（URL 同步待完善）。
**此 Part 完成即一期关闭**（更新 [13](./13-实施路线图.md) 与根 PROGRESS.md）。

### P2 · 认证底座

任务：

1. `uv sync --extra web` 后补装 `reflex-local-auth`（加进 `[web]` extra）
2. DB 补表：`UserProfile` / `BindingRequest`（[09](./09-认证与权限模块.md) §5；schema 变更走 `create_all` 或首个 alembic 迁移）
3. `states/auth.py`：`AuthState(LocalAuthState)` + `is_admin` / `bound_player_id` computed var
4. `/login` `/register` 页；注册同事务补写 `UserProfile`（[12](./12-开发流程建议.md) §5 二期坑）
5. 权限三落点：路由 `on_load` 守卫 / 事件处理器 `require_login` + 角色判断 / 私有数据 computed var（[09](09-认证与权限模块.md) §3/§4）

验收：未登录访问 `/profile` 重定向到 `/login`；普通用户访问 `/admin/*` 被拒；预渲染不泄露私有数据。

### P3 · `/profile` 自助资料

任务：校内简称 / 曾用名维护，OJ 账号增删，绑定选手申请表单 + 待审批状态展示（[08](08-前端与Web交互模块.md) §4.3）。
admin-only 字段只读展示并注明原因。

验收：走通「注册 → 提交绑定 → 管理员批准 → 页面显示已绑定」全链路（批准动作暂用 DB/脚本模拟亦可，正式 UI 在 P4）。

### P4 · 后台 CRUD 页

任务：`/admin`（概览 + 待审批）、`/admin/players` `/admin/teams` `/admin/contests` `/admin/users` `/admin/audit`（[08](08-前端与Web交互模块.md) §4.6）。
全部走 `player.api` / `team.api` / `contest.api`，唯一性冲突把异常消息直接展示到字段级错误（[08](08-前端与Web交互模块.md) §6）。

验收：admin 全程不敲 CLI 完成选手/队伍增删改查与绑定审批。

### P5 · 在线导入

任务：`/admin/import` 五步流程（上传 → 元信息 → 预览 → 未匹配决策 → 确认写入），解析结果先落 `ImportBatch(status=staged)`，长解析用 `@rx.event(background=True)` 且不进写事务（[08](08-前端与Web交互模块.md) §4.4、[12](12-开发流程建议.md) §8）。

验收：用真实省赛 xlsx 走通全流程；中途关页面无半截数据。**此 Part 完成即三期关闭。**

### P6 · 详情页与图表

任务：`/players/{player_id}`（信息 + 参赛记录 Tab + Plotly Rating 曲线）、`/contests/{contest_id}`（formal/training 同页按 format 切列）、`/about`（[08](08-前端与Web交互模块.md) §4.2）。
依赖 `reflex-components-plotly`；曲线超 500 点按赛年聚合（[08](08-前端与Web交互模块.md) §7）。
注意：Rating 曲线在真实公式（四期）落地前展示的是 placeholder 数据，可先上。

验收：点榜单行的选手名进入详情页，记录与曲线与 DB 数据一致。

### P7 · 权重试算

任务：`/admin/rating` 左调权重右看 diff；试算不落库不进缓存，「应用」才写 YAML + bump `data_version` + 记审计（[08](08-前端与Web交互模块.md) §4.5）。
前置：四期 Rating 计算器已实现，试算才有业务含义。

## 5. 测试与验收方式

- **逻辑测试下沉 core**：筛选/排序/转换逻辑尽量写成 `xcpc_core` 纯函数测；State 保持薄到不值得单测
- **视图模型转换**在 `xcpc_web/states/views.py` 写少量 pytest（纯函数，无需起 Reflex）
- **页面验收靠手工清单**：每个 Part 的「验收」条目即 checklist；关键链路（登录、导入、审批）写成固定走查脚本记入 README
- 每 Part 合入前：`uv run python -m pytest xcpc_core -v` 必须全绿

## 6. 风险

| 风险 | 应对 |
|------|------|
| Reflex 0.9.x 组件分包生态较新，文档少 | P0 先做最小页面踩坑，版本锁死，升级独立立项 |
| `reflex-local-auth` 与 Reflex 版本适配 | P2 开始时先验证库版本兼容，不兼容则降级手写最小 session 认证 |
| Plotly 产物体积大 | 仅详情页引入，榜单页不加载 |
| 单进程约束 | 部署不加 `--workers`（[12](./12-开发流程建议.md) §8） |

---

*文档版本：v1.1 — P0/P1 已完成，一期关闭，进入 P2 认证底座开发。*
