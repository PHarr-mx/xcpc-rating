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
| **P2** ✅ | 认证底座：登录注册 + AuthState + 权限守卫 | 二期 | P1 | 未登录访问 `/profile` 被重定向 |
| **P3** ✅ | `/profile` 自助资料 + 绑定申请 | 二期 | P2 | 用户可提交绑定申请，admin 可审批 |
| **P4a–P4d** ✅ | 三期后台 CRUD ×4：选手 / 队伍 / 比赛与审计 / 在线导入 | 三期 | P2 | Web 端完成全部增删改查 + 导入 |
| **P5** | 详情页与图表：`/players/{id}` `/contests/{id}` `/about` | 一期后即可插入 | P1 | 详情页渲染真实记录，Rating 曲线可见 |
| **P6** | 权重试算 `/admin/rating` | 四期 | P4c | 试算 diff 可见，应用后榜单变化 |

顺序约束：**P0→P1 最先；P2→P3 必须先于三期 CRUD**（否则会先做出一批无认证的写接口，[13](./13-实施路线图.md) §2）。
P5 是纯只读页，不依赖认证，建议紧跟 P1 做掉（一期/二期间隙），也可推迟。

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
│   │   └── admin/           # AdminPlayer/Team/Contest/Import/RatingLab（P4a–P4d/P6）
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
6. ✅ 筛选条件同步 URL query（2026-09-11）：`BoardState.on_load` 从 `router.page.params` 恢复 mode/period_type/period_id/search（非法值忽略回落默认）；`set_*_sync_url` 事件经 `rx.redirect(path, replace=True)` 写回 URL，默认值参数不进 URL 保持地址干净；`set_sort` 暂不进 URL（排序属个人视图偏好）；回归测试 `tests/test_board_url_sync.py`（10 条）
7. ✅ `status=left` 不显示；`retired` 显示退役标记（[08](08-前端与Web交互模块.md) §4.1）

验收：浏览器看到 21 行真实榜单；切换 mode/周期/搜索均实时生效；刷新带参 URL 状态保持（URL 同步 ✅ 2026-09-11，`tests/test_board_url_sync.py`）。
**此 Part 完成即一期关闭**（更新 [13](./13-实施路线图.md) 与根 PROGRESS.md）。

### P2 · 认证底座 ✅（2026-08-20）

任务：

1. ✅ 补装 `reflex-local-auth==0.5.0`（已加进 `[web]` extra，连带 `sqlmodel`/`bcrypt`）
2. ✅ DB 补表：`UserProfile` / `BindingRequest` 以 web 层 SQLModel 定义（`states/auth_models.py`），存 `xcpc_web.db`，经 `create_all` 建表（[09](./09-认证与权限模块.md) §5；跨库 player FK 移除，改 service 层校验）
3. ✅ `states/auth.py`：`AuthState(LocalAuthState)` + `is_admin` / `bound_player_id` / `is_bound` computed var
4. ✅ `/login` `/register` 页；注册同事务补写 `UserProfile`（覆写 `_register_user`，[12](./12-开发流程建议.md) §5 二期坑）
5. ✅ 权限三落点：路由 `on_load` 守卫 / 事件处理器 `_require_admin` / 私有数据 computed var（`states/admin/base.py` 提供 `_require_admin`，[09](09-认证与权限模块.md) §3/§4）

验收：未登录访问 `/profile` 重定向到 `/login`；普通用户访问 `/admin/*` 被拒；预渲染不泄露私有数据。✅

### P3 · `/profile` 自助资料 ✅（2026-08-20）

任务：校内简称 / 曾用名维护，OJ 账号增删，绑定选手申请表单 + 待审批状态展示（[08](08-前端与Web交互模块.md) §4.3）。
admin-only 字段只读展示并注明原因。

验收：走通「注册 → 提交绑定 → 管理员批准 → 页面显示已绑定」全链路。✅（审批正式 UI 已在二期完成，见 `states/admin/users.py`）

**坑**：reflex 0.9.7 computed var `cache=True` 无 interval = 永不失效 → 自助字段 / OJ 账号 / 列表类 var 一律 `cache=False`，否则同会话二次操作读到旧快照（连加 OJ 账号会覆盖前一个）。

### P4a · `/admin/players` 选手 CRUD ✅（2026-08-24）

任务：

- `AdminPlayersState(AdminState)`：`players` 列表（含 `status`/`grade` 筛选）、弹窗表单（`rx.dialog`）建/改选手
- 批量操作：`mark_left` 软删（`delete_player` 物理删留 CLI，Web 端主要用软删）
- 字段：`PlayerCreate`/`PlayerUpdate`（用 core 的 Pydantic 校验）；`PlayerValidationError` 消息直接展示到字段（08 §6）
- 写操作首行 `_require_admin()`，审计 `audit_api.record(action="player.create|update|delete", ...)`

验收：admin 浏览器完成选手新增/改资料/软删，唯一性冲突（如 OJ 账号已绑他人）字段级显示。✅ 已完成；新增 7 条 Web 回归测试，core 73 + web 46 全绿，Reflex production frontend export 通过。

### P4b · `/admin/teams` 队伍 CRUD ✅（2026-08-24）

任务：队伍列表、按队员集合建队（`TeamCreate(members=...)`）、`member_key` 冲突时提示已存在的队、别名编辑与删除。用 core `team.api` 的 `find_by_members` 做冲突预检；成员 ID 通过 `player.api` 校验。

队伍身份由成员集合决定：Web 编辑遵循 `skill/team-manage/SKILL.md` 的约束，仅追加别名，不原地修改 `members`；换员请新建队伍。创建、更新、删除均写入 `team.create|update|delete` 审计日志。

验收：admin 浏览器完成队伍建改删，同队员集合建重队被提示。✅ 已完成；新增 8 条 Web 回归测试，core 73 + web 54（总计 127）全绿，Reflex production frontend export 通过。

### P4c · `/admin/contests` + `/admin/audit` ✅（2026-08-24）

任务：

- `/admin/contests`：比赛列表（按 `source_type` 切 formal/training）+ 文本搜索 + 删除；core `contest.api.delete_contest` 清理 standings，并同步删除 `event_id` 以 `{contest_id}#` 开头的派生 `RatingEvent`
- `/admin/audit`：审计日志列表，按用户名/用户 ID、`action`、起止日期筛选；只读（写仅由各业务操作触发）
- 新增 `xcpc_core.audit.api.list_logs()` 作为审计查询入口，Web 不直接读 core 表

验收：删除比赛后榜单与成绩消失；审计可按 user/action 筛出绑定审批与 CRUD 记录。✅ 已完成；新增 6 条 Web 回归测试，core 73 + web 60（总计 133）全绿，Reflex production frontend export 通过。

### P4d · `/admin/import` 在线导入五步 ✅（Web 集成 2026-08-25，验收通过 2026-09-10）

任务：上传 → 填元信息（`contest_id`/日期/`contest_type`）→ 解析预览（队数/本校/奖牌线）→ 未匹配项人工决策（新建选手 or 指定现存）→ 确认写入。解析结果先落 `ImportBatch(status=staged)`，确认才写正式表；长解析 `@rx.event(background=True)` 不进写事务（[08](./08-前端与Web交互模块.md) §4.4、[12](./12-开发流程建议.md) §8）。写 `import.confirm` 审计。

实现：新增 staged importer API（`stage_formal_xlsx` / `confirm_import_batch` / `discard_import_batch`），并接入 `/admin/import`。上传文件使用安全临时路径，确认、取消及重新上传时清理；解析阶段不创建正式 Player / Team / Contest，确认阶段以单个 core DB transaction 写入，提交成功后再归档 raw JSON。

验证：真实省赛 xlsx 已走通 staged → confirmed 全流程（解析 312 支队伍、6 条正式成绩、18 个未匹配选手）；core + web 共 138 条测试通过，Reflex frontend export 通过。浏览器手工验收已于 2026-09-10 由管理员完成，全程未发现问题，三期关闭。

### P5 · 详情页与图表

任务：`/players/{player_id}`（信息 + 参赛记录 Tab + Plotly Rating 曲线）、`/contests/{contest_id}`（formal/training 同页按 format 切列）、`/about`（[08](08-前端与Web交互模块.md) §4.2）。
依赖 `reflex-components-plotly`；曲线超 500 点按赛年聚合（[08](08-前端与Web交互模块.md) §7）。
注意：Rating 曲线在真实公式（四期）落地前展示的是 placeholder 数据，可先上。

进度：`/about` ✅（2026-09-11，纯静态「数据与赛季说明」页，导航栏加「关于」入口，冒烟测试 test_about_page.py；注意测试不得导入 app 模块——其顶层 rx.App() 会破坏 conftest 状态链基建）。两个详情页与 standings_table / oj_link 组件未开始。

验收：点榜单行的选手名进入详情页，记录与曲线与 DB 数据一致。

### P6 · 权重试算

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

*文档版本：v1.9 — P5 之 /about 静态页完成（2026-09-11）。*
