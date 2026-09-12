# Web 与认证

> 定位：**参考 + 待建**。关联：[01-架构与数据流](01-架构与数据流.md) · [03-比赛与导入](03-比赛与导入.md) · [04-Rating与榜单](04-Rating与榜单.md) · [07-开发流程](07-开发流程.md)

Reflex 应用（`xcpc_web/`，锁 0.9.7）。Web 层只做 UI 与状态：**不写 SQL、不承载业务规则**，
State 只做「读表单 → 调 `xcpc_core` API → 转视图模型 → 写 state var」。

> 实现状态：榜单页、认证、`/profile`、管理后台 7 页（含在线导入五步）均已上线；
> 选手/比赛详情页与权重试算页待建。

---

## 1. 技术栈

| 项 | 选型 |
|----|------|
| 框架 | Reflex **0.9.7 锁版本**（升级作独立任务） |
| 组件包 | `reflex-components-core` + `-lucide`（随 Reflex 分包，独立版本） |
| 图表 | `reflex-components-plotly`（⬜ 未引入，随详情页） |
| 认证 | `reflex-local-auth` 0.5.0 |
| 手写 JS/TS | **无** |

安装 `uv sync --extra web`；启动 `cd xcpc_web && ../.venv/bin/reflex run`（端口 3000）。

## 2. 分层约定

- **视图模型**：不把 Pydantic BaseModel 塞进 state var（序列化不稳）。`states/views.py` 用 `rx.Base` 定义视图层 DTO 并负责「领域模型 → 视图模型」转换，附带精确控制哪些字段进浏览器。
- **数据流**：State 事件处理器内直接调 `xcpc_core.<模块>.api`（同进程 Python，无 HTTP API 层）。
- **长任务**：xlsx 解析等用 `@rx.event(background=True)`，且不放写事务里。

## 3. 路由表（实现状态）

| 路径 | 页面 | 权限 | 状态 |
|------|------|------|------|
| `/` | 榜单（默认 all + career；筛选同步 URL query） | guest | ✅ |
| `/about` | 数据与赛季说明（静态） | guest | ✅ |
| `/login` `/register` | 认证 | guest | ✅ |
| `/profile` | 我的资料、OJ 账号、绑定状态 | member | ✅ |
| `/admin` | 概览 + 待审批计数 | admin | ✅ |
| `/admin/users` | 用户与绑定审批 | admin | ✅ |
| `/admin/players` | 选手 CRUD | admin | ✅ |
| `/admin/teams` | 队伍 CRUD | admin | ✅ |
| `/admin/contests` | 比赛列表与删除 | admin | ✅ |
| `/admin/audit` | 审计日志筛选（只读） | admin | ✅ |
| `/admin/import` | xlsx 在线导入五步 | admin | ✅ |
| `/players/{player_id}` | 选手详情 | guest | ⬜ |
| `/contests/{contest_id}` | 比赛详情（formal/training 同页按 format 切列） | guest | ⬜ |
| `/admin/rating` | 权重试算 | admin | ⬜（P6，前置四期公式） |

路由注册：`xcpc_web/xcpc_web.py`（`app.add_page`，含各页 `on_load`）。

## 4. State 划分

| State | 职责 | 状态 |
|-------|------|------|
| `AuthState(LocalAuthState)` | 全局认证基类：`is_admin` / `bound_player_id` / `is_bound` computed var | ✅ |
| `BoardState` | 榜单页（mode/period/search/sort + URL query 同步） | ✅ |
| `ProfileState` | 自助改资料、OJ 账号、绑定申请 | ✅ |
| `AdminState`（基类） | 权限守卫 `_require_admin()` | ✅ |
| `AdminOverview/Users/Players/Teams/Contests/Audit/ImportState` | 管理后台各页 | ✅ |
| `PlayerDetailState` / `ContestDetailState` | 详情页 | ⬜ |
| `RatingLabState` | 权重试算（draft_weights / preview_rows / diff_vs_current） | ⬜ |

`BoardState` 要点：mode/period_type/period_id/search/sort_by；`@rx.var(cache=True)` 调 `board_api.board()`；
**筛选同步 URL query 已实现**——`on_load` 从 `router.page.params` 恢复（非法值白名单忽略），
`set_*_sync_url` 事件经 `rx.redirect(path, replace=True)` 写回，默认值不进 URL。

## 5. 已实现页面要点

- **榜单页 `/`**：表格（rank/player_id/name/grade/rating/events/delta_recent）；`status=left` 不显示、`retired` 带标记；页脚展示 algorithm + data_version + generated_at；搜索/筛选实时生效。
- **`/profile`**：绑定申请表单 + 待审批状态；自助字段（handle/aliases/OJ 账号）编辑；admin-only 字段只读展示并注明原因（比隐藏更好，避免用户以为功能坏了）。
- **`/admin/import` 五步**：上传 → 元信息 → 解析预览 → 未匹配人工决议 → 确认写入；staged 暂存（见 [03-比赛与导入](03-比赛与导入.md) §2.4）。
- **`/about`**：数据与赛季说明静态页。
- 组件：`layout.py`（page_shell：导航 + 内容 + 页脚）、`board_table.py`、`period_selector.py`。

## 6. 待建页面与组件

| 项 | 设计要点 |
|----|----------|
| `/players/{id}` | 基本信息 + OJ 账号 + 参赛记录 Tab（正式/训练/OJ）+ Plotly Rating 曲线（按 mode 过滤，超 500 点按赛年聚合）；绑定本人时右上角「编辑我的资料」入口 |
| `/contests/{id}` | 比赛详情，formal/training 同页按 `format` 切列 |
| `standings_table.py` | 成绩表组件，按 format 切列 |
| `oj_link.py` | 平台 profile 外链，URL 模板集中在 config |
| `form_fields.py` | 表单控件 + 错误提示 |
| `rating_chart.py` | Plotly 折线（曲线在真实公式落地前可展示 placeholder 数据） |
| `/admin/rating` | 左调权重右看 diff；试算不落库不进缓存，「应用」才写 YAML + bump data_version + 记 `weights.apply` 审计 |

**错误与加载态**：数据加载 `rx.skeleton`；资源不存在 404 + 返回榜单；表单校验失败展示 core 异常消息（字段级）；WebSocket 断开用 Reflex 内置重连。**性能**：校内规模全量渲染一次即可，超 2000 行再考虑虚拟滚动；Plotly 仅详情页引入。

## 7. 认证与权限（已实现）

### 7.1 选型与双表

`reflex-local-auth` 提供 `LocalUser`（凭据）/ `LocalAuthSession`（会话）/ `LocalAuthState` / `@require_login`；
本项目加两张 web 层 SQLModel 表（`states/auth_models.py`，存 **`data/db/xcpc_web.db`**，与 core 分库）：

- `userprofile`：`user_id` UNIQUE、`role`（member/admin）、`bound_player_id` UNIQUE（一个选手最多绑一个用户）
- `bindingrequest`：`user_id`、`player_id`、`reason`、`status`（pending/approved/rejected）、`reviewed_by/at`

首个 admin 由 CLI 创建：`create_admin.py --username … --password …`（`--reset-password` 可重置密码并使旧会话失效）。

### 7.2 角色

| 角色 | 能做 |
|------|------|
| guest | 看榜单、详情页、about |
| member | guest + 改**自己**的自助字段（OJ 账号/别名/handle） |
| admin | 全部 CRUD、导入、审批绑定、看审计日志、权重试算 |

member 的写权限严格限定在服务端从 session 推出的 `bound_player_id` 上，**不接受客户端传入的 ID**。

### 7.3 权限校验的三个落点（本项目实现于 `states/admin/base.py`）

**Reflex 会静态预渲染页面**——写在组件树里的常量进 HTML，对所有人可见。`rx.cond` 隐藏按钮只是体验优化，不是安全边界。

| 手段 | 作用 | 是防护吗 |
|------|------|:---:|
| `@require_login` 装饰器 | 未登录跳登录页 | ❌ |
| `on_load` 守卫（`_require_admin` 第 1 层） | 无权限跳转走 | ❌ |
| `rx.cond` 隐藏组件 | 不显示按钮 | ❌ |
| **事件处理器内校验**（第 2 层） | 拒绝执行写操作 | ✅ |
| **computed var 内校验**（第 3 层，非 admin 返回空） | 私有数据不出库 | ✅ |

结论：真正的防护只有**事件处理器 + computed var**两处；`on_load`/`require_login` 是体验层。三处都要写，但作用要分清。`bound_player_id` 是 computed var 每次从会话推导，**不缓存在可写 state var**——否则客户端可借 setter 覆盖它改别人的选手。

### 7.4 绑定流程（已实现）

```
注册（同事务写 LocalUser + UserProfile，覆写 _register_user）
  → /profile 提交绑定申请（选 player_id + 说明）
  → admin 在 /admin/users 审批（unique 预检：选手已被他人绑定 / 申请者已绑他人）
  → 批准：写 bound_player_id + 自动驳回其余 pending
```

**不允许自助绑定**（否则任何注册用户可认领别人成绩）；换绑需 admin 先解绑。

### 7.5 审计

所有写操作落 `auditlog`（`xcpc_core/audit/api.py`，best-effort 跨库写，失败不回滚业务）：
`player.create|update|delete`、`player.oj.add|remove`、`team.create|update|delete`、
`contest.delete`、`import.confirm`、`binding.approve|reject`、（待建）`weights.apply`、`user.role.change`。
`diff_json` 只存变化字段；`/admin/audit` 按 user/action/日期筛选。

## 8. Web 测试基建

`xcpc_web/tests/conftest.py`（State 层测试，无浏览器）：

- 临时 web DB（`tmp_path` + monkeypatch `rxconfig.config.db_url`）+ 内存 core DB（`configure_store` 注入，真实库零接触）
- Reflex 0.9.7 状态链须手工构造：`_reflex_internal_init=True` + 完整父链（LocalAuthState → AuthState → 目标 State），继承 var 的读写委托给 parent_state
- 手工链不在 root 树里 → autouse fixture 把 `_mark_dirty` no-op（只影响 delta 序列化，不影响业务逻辑与 computed var 求值）
- 登录态 = 往 web DB 插 `LocalAuthSession` + 把 `auth_token` 设到链根
- 事件处理器经实例访问即绑定好的 callable，直接调用即执行函数体
- 注入 URL query：照运行时 processor 行为，赋 `state.router_data` 后再赋 `state.router = RouterData.from_router_data(...)`

**禁忌：测试中不得导入 `xcpc_web.xcpc_web`（app 模块）**——顶层 `rx.App()` + 全部 `add_page` 会初始化全局状态树，收集期导入即破坏上述基建（现象：跨测试 DB 复用、UNIQUE 冲突）。路由注册生效与否交给浏览器手工验收。

## 9. MVP 范围与开放问题

| 包含（已实现/规划） | 明确不包含 |
|----------------------|------------|
| 榜单页 + 筛选/搜索/URL 分享、选手/比赛详情、登录注册绑定、全部 admin 页 | 队伍详情页（再议） |
| 审计日志、Plotly Rating 曲线 | 深色模式 |
| 权重试算（P6） | OJ 数据在线导入 |
| 密码重置（CLI 已有；admin UI 待定） | 训练赛在线录入（随四期） |

开放问题（详见 08 路线图）：注册限制（邀请码/域名，公网前必须定）、密码找回 UI、上传文件大小上限（建议 10MB）、`retired` 绑定用户保留写权限 / `left` 自动解绑（建议状态）。

---

*docs/ v2 重构（2026-09-11）：合并原 08-前端与Web交互模块、09-认证与权限模块；实现差异（分库、staged 已落地、URL query 同步）已按代码现状修正。*
