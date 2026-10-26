# Web 与权限

Reflex 应用（`xcpc_web/`，锁 0.9.7）。Web 层只做 UI 与状态：**不写 SQL、不承载业务规则**，
State 只做「读表单 → 调 `xcpc_core` API → 转视图模型 → 写 state var」。

---

## 1. 技术栈

| 项 | 选型 |
|----|------|
| 框架 | Reflex **0.9.7 锁版本**（升级作独立任务） |
| 组件包 | `reflex-components-core` + `-lucide`（随 Reflex 分包，独立版本） |
| 图表 | Reflex 内置 `rx.recharts`（**未引入 plotly**；`reflex-components-plotly` 仅为 reflex 元包的传递依赖） |
| 认证 | `reflex-local-auth` 0.5.0 |
| 手写 JS/TS | **无** |

安装 `uv sync --extra web`；启动 `cd xcpc_web && ../.venv/bin/reflex run`（端口 3000）。

## 2. 分层约定

- **视图模型**：不把 Pydantic BaseModel 塞进 state var（序列化不稳）。`states/views.py` 用 `rx.Base` 定义视图层 DTO 并负责「领域模型 → 视图模型」转换，精确控制哪些字段进浏览器
- **数据流**：State 事件处理器内直接调 `xcpc_core.<模块>.api`（同进程 Python，无 HTTP API 层）
- **长任务**：xlsx 解析等用 `@rx.event(background=True)`，且不放写事务里

## 3. 路由表

| 路径 | 页面 | 权限 |
|------|------|------|
| `/` | 榜单（默认 all + career；筛选同步 URL query） | guest |
| `/about` | 数据与赛季说明（静态） | guest |
| `/login` | 登录 | guest |
| `/register` | **建号（admin-only）**：非管理员只看到说明，无表单 | admin |
| `/profile` | 我的资料、OJ 账号、绑定状态 | member |
| `/points` | 生涯积分：提交认证（按 scoring 切换表单）+ 我的认证 + 个人/队伍双榜 | member |
| `/players/{player_id}` | 选手详情：档案 + OJ 外链 + Rating 曲线 + 参赛记录 | guest |
| `/contests/{contest_id}` | 比赛详情：元信息 + 成绩表按 format 切列 | guest |
| `/admin` | 概览 + 待审批计数 | admin |
| `/admin/users` | 用户与绑定审批 + **批量建号** | admin |
| `/admin/players` | 选手 CRUD | admin |
| `/admin/teams` | 队伍 CRUD | admin |
| `/admin/contests` | 统一比赛管理：创建表单 + 列表与删除 | admin |
| `/admin/tiers` | 赛事等级（系数）+ 奖项基线分，同页 CRUD | admin |
| `/admin/points` | 积分认证审批 + 免认证直录 | admin |
| `/admin/rating` | 权重试算：调公式参数、看与当前榜单 diff | admin |
| `/admin/import` | 在线导入两通道（xlsx 五步 + JSON 两段） | admin |
| `/admin/audit` | 审计日志筛选（只读） | admin |

路由注册：`xcpc_web/xcpc_web.py`（`app.add_page`，含各页 `on_load`）。

## 4. State 划分

| State | 职责 |
|-------|------|
| `AuthState(LocalAuthState)` | 全局认证基类：`is_admin` / `bound_player_id` / `is_bound` computed var |
| `BoardState` | 榜单页（mode/period/search/sort + URL query 同步） |
| `ProfileState` | 自助改资料、OJ 账号、绑定申请 |
| `PointsState` | 积分页（提交认证 + 我的认证 + 双榜） |
| `PlayerDetailState` / `ContestDetailState` | 详情页 |
| `AdminState`（基类） | 权限守卫 `_require_admin()` |
| `AdminOverview/Users/Players/Teams/Contests/Tiers/Points/Rating/Audit/ImportState` | 管理后台 10 页 |
| `ExtendedRegistrationState` | 建号（admin-only，基类是 `RegistrationState` 而非 `AuthState`） |

**`BoardState` 要点**：mode/period_type/period_id/search/sort_by；`@rx.var(cache=True)` 调 `board_api.board()`；
筛选同步 URL query——`on_load` 从 `router.page.params` 恢复（非法值白名单忽略），
`set_*_sync_url` 事件经 `rx.redirect(path, replace=True)` 写回，默认值不进 URL。

## 5. 布局与组件

- `layout.py`：`page_shell(section=, subsection=)` —— 顶栏四大类（榜单/积分/个人资料/系统管理）+ 恒显示侧边栏；高亮由各页显式传字面量（避开 Reflex 运行时读路由的 Var 时敏坑）
- `board_table.py` / `period_selector.py` / `standings_table.py` / `oj_link.py` / `rating_chart.py`

**详情页要点**：

| 项 | 设计要点 |
|----|----------|
| `/players/{id}` | 基本信息 + OJ 账号外链（`config.py` 模板）+ 参赛记录表 + Rating 累计曲线；`is_self` 由路由参数与服务端 bound_player_id 比对，绑定本人显示「编辑我的资料」；404 兜底 |
| `/contests/{id}` | 元信息一行 + 成绩表按 format 切列；队员姓名由 State 解析（include_left，历史成绩显示离队选手名字）；manually_added 行标「（打星）」 |
| `standings_table.py` | xcpc（解题/罚时）/ oi（得分）两套列，`rx.cond(is_oi, …)` 切换 |
| `oj_link.py` | 平台 profile 外链；URL 与展示文案在 State 侧预算成视图 dict（url 空串表示无链，避免 `href=None` 报错） |
| `rating_chart.py` | Rating 累计折线，用内置 recharts（零新增依赖） |

**动态路由**：`route="/players/[player_id]"`；参数运行时合并进 `router.page.params`（与 query 同通道），`on_load` 读取；`is_self` 直接读路由参数不依赖 on_load 时序。

**错误与加载态**：数据加载 `rx.skeleton`；资源不存在 404 + 返回榜单；表单校验失败展示 core 异常消息（字段级）；WebSocket 断开用 Reflex 内置重连。

---

## 6. 认证与权限

### 6.1 双表（web 层，存 `data/db/xcpc_web.db`）

`reflex-local-auth` 提供 `LocalUser`（凭据）/ `LocalAuthSession`（会话）/ `LocalAuthState` / `@require_login`；
本项目加两张 SQLModel 表（`states/auth_models.py`）：

- `userprofile`：`user_id` UNIQUE、`role`（member/admin）、`bound_player_id` UNIQUE（一个选手最多绑一个用户）
- `bindingrequest`：`user_id`、`player_id`、`reason`、`status`（pending/approved/rejected）、`reviewed_by/at`

首个 admin 由 CLI 创建：`create_admin.py --username … --password …`（`--reset-password` 可重置密码并使旧会话失效）。

### 6.2 角色

| 角色 | 能做 |
|------|------|
| guest | 看榜单、详情页、about |
| member | guest + 改**自己**的自助字段（OJ 账号/别名/handle）+ 提交积分认证 |
| admin | 全部 CRUD、导入、审批绑定、看审计日志、权重试算、建号 |

member 的写权限严格限定在服务端从 session 推出的 `bound_player_id` 上，**不接受客户端传入的 ID**。

### 6.3 权限校验的三个落点

**Reflex 会静态预渲染页面**——写在组件树里的常量进 HTML，对所有人可见。`rx.cond` 隐藏按钮只是体验优化，**不是安全边界**。

| 手段 | 作用 | 是防护吗 |
|------|------|:---:|
| `@require_login` 装饰器 | 未登录跳登录页 | ❌ |
| `on_load` 守卫（`_require_admin` 第 1 层） | 无权限跳转走 | ❌ |
| `rx.cond` 隐藏组件 | 不显示按钮 | ❌ |
| **事件处理器内校验**（第 2 层） | 拒绝执行写操作 | ✅ |
| **computed var 内校验**（第 3 层，非 admin 返回空） | 私有数据不出库 | ✅ |

**结论：真正的防护只有「事件处理器 + computed var」两处**；`on_load`/`require_login` 是体验层。三处都要写，但作用要分清。

`bound_player_id` 是 computed var 每次从会话推导，**不缓存在可写 state var**——否则客户端可借 setter 覆盖它改别人的选手。

### 6.4 建号（不开放自助注册）

系统**不允许个人注册**，账号一律由管理员创建。两条入口：

| 入口 | 场景 | 特点 |
|------|------|------|
| `/register`（admin-only） | 零星建 1–2 个 | 非 admin 只看到「仅限管理员」说明，无表单 |
| `/admin/users` 批量表单 | 首批开通、整届成员 | 每行 `用户名[,初始密码][,绑定选手ID]` |

两条入口都：服务端事件处理器内校验 admin、新账号默认 `member` 角色、
写 `user.create` / `user.batch_create` 审计。

**批量表单实现要点**：
- **逐行独立事务**——某行失败不影响其他行，结果按行报告（成功/跳过/失败 + 原因）
- 密码留空回落到「默认初始密码」；支持中文逗号分隔（用户常从表格粘贴）
- 第三列可选绑定选手，指定时校验该选手**未被他人绑定**（冲突则该行失败，不静默覆盖）
- 以 `#` 开头的行视为注释

> `ExtendedRegistrationState` 的基类是 `RegistrationState`（继承 `LocalAuthState`），
> **不在 `AuthState` 链上**，故它自己实现 `is_admin` computed var 从 UserProfile 推导。

### 6.5 绑定流程

```
建号（同事务写 LocalUser + UserProfile，覆写 _register_user）
  → /profile 提交绑定申请（选 player_id + 说明）
  → admin 在 /admin/users 审批（unique 预检：选手已被他人绑定 / 申请者已绑他人）
  → 批准：写 bound_player_id + 自动驳回其余 pending
```

**不允许自助绑定**（否则任何注册用户可认领别人成绩）；换绑需 admin 先解绑。

### 6.6 审计

所有写操作落 `auditlog`（`xcpc_core/audit/api.py`，best-effort 跨库写，**失败不回滚业务**）：

```
player.create|update|delete
team.create|update|delete
contest.create|delete
import.confirm | import.json_confirm
binding.approve|reject
points.approve|reject | points.auto_record
tier.create|update|delete
award.create|update|delete
user.create | user.batch_create
weights.apply
```

`diff_json` 只存变化字段（更新类操作记**前后值**）；`/admin/audit` 按 user/action/日期筛选。

> OJ 账号编辑与角色变更**无独立审计动作**（`player.oj.*`、`user.role.change` 是原设计预留名，代码中不存在）。

---

## 7. Web 测试基建

`xcpc_web/tests/conftest.py`（State 层测试，无浏览器）：

- 临时 web DB（`tmp_path` + monkeypatch `rxconfig.config.db_url`）+ 内存 core DB（`configure_store` 注入，真实库零接触）
- **Reflex 0.9.7 状态链须手工构造**：`_reflex_internal_init=True` + 完整父链（`LocalAuthState` → `AuthState` → 目标 State），继承 var 的读写委托给 parent_state
- 手工链不在 root 树里 → autouse fixture 把 `_mark_dirty` no-op（只影响 delta 序列化，不影响业务逻辑与 computed var 求值）
- **登录态** = 往 web DB 插 `LocalAuthSession` + 把 `auth_token` 设到**链根**（`LocalAuthState`）
- 事件处理器经实例访问即绑定好的 callable，直接调用即执行函数体
- 注入 URL query：照运行时 processor 行为，赋 `state.router_data` 后再赋 `state.router = RouterData.from_router_data(...)`
- `isolate_repo_root` autouse fixture：把 importer / lab 的 `find_repo_root` 重定向到 `tmp_path`，**防止测试写真实仓库的 `data/raw/`**

> ⚠️ **禁忌：测试中不得导入 `xcpc_web.xcpc_web`（app 模块）**——顶层 `rx.App()` + 全部 `add_page` 会初始化全局状态树，收集期导入即破坏上述基建（现象：跨测试 DB 复用、UNIQUE 冲突）。路由注册生效与否交给浏览器手工验收。

---

## 8. 明确不包含

| 项 | 说明 |
|----|------|
| 队伍详情页 | 未做，需求未定 |
| 深色/浅色切换 | 当前为固定暗色主题 |
| OJ 数据在线导入 | 随 OJ 数据源立项 |
| 密码找回 UI | CLI 可重置（`create_admin.py --reset-password`），无自助找回 |
| 上传文件大小上限 | 未设硬限制（建议 10MB） |