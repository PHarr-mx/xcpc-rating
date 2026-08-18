# 开发进度

> 最近更新：2026-08-18 · 对照 [docs/13-实施路线图.md](docs/13-实施路线图.md)
>
> 记录原则：只记「结论 + 日期」，设计细节留在 `docs/`，变更细节看 git log。

## 总体状态

一期「地基」已完成；二期「认证」进行中（P2a/P2b/P2c 已完成，P2d 开始前）。

## 分期进度

| 期 | 内容 | 状态 | 备注 |
|----|------|------|------|
| 一期 | 地基 | ✅ 已完成 | P0 骨架 + P1 榜单页均完成 |
| 二期 | 认证 | 🔨 进行中 | P2a/P2b/P2c 完成，P2d 开始前；拆分见 §二期中详述 |
| 三期 | 管理后台 | ⬜ 未开始 | |
| 四期 | 业务补齐 | ⬜ 未开始 | |
| 五期 | 上线 | ⬜ 未开始 | |

## 一期明细

- ✅ 2026-08-02 `pyproject.toml` 统一打包（uv，Python 3.13），`xcpc_core` 单顶层包；`reflex==0.9.7` 声明为可选依赖 `[web]`
- ✅ 2026-08-02 SQLite 建表（`xcpc_core/db/tables.py`）+ store 重构为 repository + `migrate` 一次性迁移（幂等）
- ✅ 2026-08-02 player / team CRUD 六件套（含 CLI），正式赛导入（raw + DB 双写，四川省赛数据已入库归档）
- ✅ 2026-08-02 contest 模块（Contest/Standing upsert）、rating 引擎（placeholder 公式）
- ✅ 2026-08-17 board 榜单聚合（`BoardSnapshot`、竞赛排名、`delta_recent`、`data_version` 进程内缓存）
- ✅ 2026-08-18 Reflex 骨架（`xcpc_web/`，P0 完成）：reflex init 脚手架、包骨架、首页展示真实数据、`reflex run` 起成功
- ✅ 2026-08-18 `/` 榜单只读页（P1 完成）：BoardState 状态管理、筛选/排序/搜索、表格渲染、元信息展示
- ⬜ `xcpc-data update` CLI（`xcpc-site build|deploy` 随静态站方案废弃，可砍）

**一期完成标志**：能用真实数据在浏览器看到榜单。✅ 已达成。

## 二期明细（进行中，2026-08-18）

> 认证是 web 层（Reflex SQLModel）职责，`UserProfile`/`BindingRequest` 存在 `xcpc_web.db`，经 `rx.session()` 访问；`xcpc_core` 不 import 这些模型。核心 DB 与 web DB 分离 → `bound_player_id`/`player_id` 无法用跨库外键，改为 service 层校验存在性。

- ✅ 2026-08-18 P2a 表结构：`xcpc_web/states/auth_models.py` 定义 `UserProfile` / `BindingRequest`（SQLModel，FK → `localuser.id`；跨库 player FK 已移除）；`rxconfig.py` 的 `db_url` 指向绝对路径 `data/db/xcpc_web.db`；`pyproject.toml` 追加 `reflex-local-auth>=0.5.0`（顺带 `sqlmodel`、`bcrypt`）
- ✅ 2026-08-18 P2b AuthState + CLI：`states/auth.py` 的 `AuthState(LocalAuthState)` 提供缓存 computed var `profile` / `is_admin` / `bound_player_id` / `is_bound`；`xcpc_web/create_admin.py` 一键创建首个 admin（同一事务写 `LocalUser` + `UserProfile(role=admin)`），**已实测跑通**（`xcpc_web.db` 四表建齐、admin 入库）
- ✅ 2026-08-18 P2c `/login` `/register` 页 + 路由接线：`pages/login.py`（绑 `LoginState.on_submit`，错误 callout、注册链接）、`pages/register.py`（绑 `ExtendedRegistrationState.handle_registration`，成功态提示）、`xcpc_web.py` 注册 `/login` `/register` 路由；`reflex run` 编译通过、两路由 200
- ✅ 2026-08-18 P2c 注册扩展修正：踩坑后改为覆写 `_register_user` + 完整实现 `handle_registration`（reflex 0.9.x 中 `super()` 调用事件处理器是**异步入队**，且继承的 handler 注册在基类路径上、跑在基类实例上 → 读 `self.new_user_id` 拿不到新值）。现 `handle_registration` 在本类定义，`_register_user` 在**同一事务**写 `LocalUser` + `UserProfile(role=member)`，经 Socket.IO 后端 E2E 实测通过（注册成功→`new_user_id`→跳 `/login`；登录 admin→`LocalAuthSession` 建立）
- 🔨 2026-08-18 P2d `/profile` 自助资料 + 绑定申请（下一 Part）
- ⬜ P2e admin 权限守卫三落点
- ⬜ P2f admin 概览 + 绑定审批 UI

**二期完成标志**：未登录访问 `/profile` 重定向 `/login`；普通用户访问 `/admin/*` 被拒；可提交绑定申请；CLI 可建首个 admin（✅ 已验证）。

## 实测快照（2026-08-18）

- 测试：72 passed
- DB（core，`data/db/xcpc.db`）：24 选手 / 8 队伍 / 1 正式赛（8 standings）；`ratingevent`、`auditlog`、`ojcontest` 等表为空
- DB（web，`data/db/xcpc_web.db`，新增）：`localuser` / `localauthsession` / `userprofile` / `bindingrequest` 四表已建；admin 用户已创建（`localuser.id=1`，`userprofile.role=admin`）
- P2c E2E 实测（Socket.IO 后端事件）：注册 → `LocalUser` + `UserProfile(role=member)` 同事务写入；登录 → `LocalAuthSession` 建立。测试账号已清理
- 榜单：`board()` 输出 21 行，`algorithm=placeholder_v0`（数值无业务含义，真公式在四期）
- `data/raw/training/`、`data/public/` 为空

---

## 二期 · 认证 — 开发计划

> 关联：[09-认证与权限模块](./docs/09-认证与权限模块.md) · [08-前端与Web交互模块](./docs/08-前端与Web交互模块.md) · [14-Web开发拆分计划](./docs/14-Web开发拆分计划.md)

### 1. 目标

让「校内成员以个人身份登录 → 申请绑定选手 → admin 审批 → 自助维护个人信息」全链路可用；admin 获得完整的管理入口。

**完成标志**：未登录访问 `/profile` 被重定向到 `/login`；普通用户访问 `/admin/*` 被拒；用户可提交绑定申请；已有管理员可通过 CLI 创建。

### 2. Part 拆解

| Part | 内容 | 依赖 | 预计工作量 | 验收要点 |
|------|------|------|-----------|---------|
| **P2a** | dep + 表结构 | 无 | 0.5d | `UserProfile` / `BindingRequest` 写入 DB，`create_all` 验证 |
| **P2b** | `AuthState` + CLI 创 admin | P2a | 0.5d | 可注册/登录/登出；CLI 创建首个 admin |
| **P2c** | `/login` `/register` UI | P2b | 0.5d | 登录成功后跳回来源页；注册自动建 UserProfile |
| **P2d** | `/profile` 自助资料 + 绑定申请 | P2b | 1d | 提交绑定 → admin 审批 → 页面显示已绑定 |
| **P2e** | admin 权限守卫三落点 | P2b | 1d | 路由守卫 / 事件处理器 / computed var 均拒绝未授权请求 |
| **P2f** | admin 概览 + 绑定审批 UI | P2c+e | 1d | `/admin/users` 列表待审批 → 通过/拒绝 → UserProfile.bound_player_id 更新 |

**顺序约束**：P2a→P2b→(P2c ∥ P2e)→P2d/P2f。P2d 和 P2f 可并行但需 P2b/P2c/P2e 就绪。

此 Part 完成即二期关闭。

### 3. 具体任务清单

#### P2a · DB 表结构扩展

> ⚠️ 实际实现已偏离本小节：表改为 web 层 SQLModel（`xcpc_web/xcpc_web/states/auth_models.py`），存 `xcpc_web.db`，经 `rx.session()` 访问；未入 `xcpc_core/db/tables.py`。下方代码块为原设计参考。

**文件修改：**
- `xcpc_core/db/tables.py`：追加 `UserProfile`、`BindingRequest`

```python
class UserProfile(Base):
    __tablename__ = "userprofile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("localuser.id"), unique=True, index=True)
    role: Mapped[str] = mapped_column(String, default="member")        # member|admin
    bound_player_id: Mapped[str | None] = mapped_column(
        ForeignKey("player.id"), unique=True
    )                                                                   # null = 未绑定
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

class BindingRequest(Base):
    __tablename__ = "bindingrequest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("localuser.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player.id"), index=True)
    reason: Mapped[str | None] = mapped_column(String)                 # 申请说明
    status: Mapped[str] = mapped_column(String, default="pending")     # pending|approved|rejected
    reviewed_by: Mapped[int | None] = mapped_column(Integer)           # admin localuser.id
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
```

- `xcpc_core/db/session.py`：确保 `Base.metadata.create_all(engine)` 覆盖新表
- `xcpc_core/tests/test_auth_models.py`（新建）：ORM 建表 + 基本插入校验

**注意：** `localuser` / `localauthsession` 是库的表名。外键引用必须正确，否则迁移时才报错。

#### P2b · AuthState + CLI 创建 admin

**新增文件：**
- `xcpc_web/xcpc_web/states/auth.py` ✅（已实现）
- `xcpc_core/auth/cli.py`（新建 core CLI 模块）→ ⚠️ 实际改为 `xcpc_web/create_admin.py`（web 层 CLI）

**核心逻辑：**

```python
# states/auth.py
import reflex_local_auth

class AuthState(reflex_local_auth.LocalAuthState):
    """全局基类：继承库提供的 LocalAuthState，叠加本项目角色与绑定。"""

    @rx.var
    def profile(self) -> dict | None:
        if not self.is_authenticated:
            return None
        return auth_api.get_profile(self.authenticated_user.id)

    @rx.var
    def is_admin(self) -> bool:
        return self.profile is not None and self.profile.get("role") == "admin"

    @rx.var
    def bound_player_id(self) -> str | None:
        """computed var，每次从会话推导——不缓存在可写 state var。"""
        return self.profile.get("bound_player_id") if self.profile else None

# CLI 创建首个 admin
def create_admin():
    """命令行创建首个 admin 用户：输入用户名、密码后在同一事务内写入 LocalUser + UserProfile(role='admin')。"""
```

**API 层（core 侧）：**
- `xcpc_core/auth/api.py`（新建）：`get_profile(user_id)`、`list_pending_bindings()`、`approve_binding(request_id, admin_user_id)`、`reject_binding(request_id, admin_user_id)`
- `xcpc_core/auth/__init__.py`：re-export

#### P2c · `/login` / `/register` UI

> ✅ 已完成（见 §二期明细）。实现偏离：未直接复用库 `pages.login_page/register_page`，改为项目自绘 `pages/login.py` / `pages/register.py`（套 `page_shell`，中文文案）；注册扩展用 `_register_user` 覆写 + 本类完整实现 `handle_registration`（reflex 0.9.x `super()` 事件异步入队、继承 handler 注册在基类路径，详见 §二期明细）。

**新增文件：**
- `xcpc_web/xcpc_web/pages/login.py`
- `xcpc_web/xcpc_web/pages/register.py`

**复用库组件：** `reflex_local_auth` 提供 `LoginState` / `RegistrationState`，但需扩展 `RegistrationState` 使其在注册成功后的同一事务内插入 `UserProfile`。

关键行为：
- 登录后跳回来源页（reflex-local-auth 默认跳到 `/`）
- 注册成功后自动进入登录态
- 表单校验错误字段级展示

#### P2d · `/profile` 自助资料 + 绑定申请

**新增/修改文件：**
- `xcpc_web/xcpc_web/states/profile.py`
- `xcpc_web/xcpc_web/pages/profile.py`
- `xcpc_core/auth/service.py`（新建）：绑定申请/审批逻辑
- `xcpc_core/auth/views.py`（新建）：视图模型

**功能点：**
- 展示当前绑定的 `player_id`（或「未绑定」状态）
- 「申请绑定」表单：选择玩家名册中的 player_id + 填写理由
- 「编辑资料」区域（仅已绑定时可用 `oj_accounts`、`aliases`、`handle`）
- 「admin-only 字段只读展示并标注原因」（`name` / `grade` / `status`）

**权限规则（服务端强制执行）：**
- `add_oj_account()` 中取 `self.bound_player_id`（来自 session/computed var），不接受客户端传入 ID
- 已绑定后才允许 edit 自助字段

#### P2e · admin 权限守卫三落点

在已有的 `/admin/*` 路由上落地三个层次的防护：

① **路由 `on_load` 守卫（体验层）：**
```python
@rx.page(route="/admin", on_load=AdminOverviewState.on_load)
@reflex_local_auth.require_login
def admin() -> rx.Component: ...

class AdminOverviewState(AuthState):
    @rx.event
    def on_load(self):
        if not self.is_admin:
            return rx.redirect("/")
        # 校验通过后再拉数据
```

② **事件处理器内校验（真正的写操作防护）：**
```python
@rx.event
def handle_write(self):
    if not self.is_authenticated:
        return  # 或返回重定向
    if not self.is_admin:
        return rx.toast.error("需要管理员权限")
    # 执行业务逻辑
```

③ **computed var 内校验（私有数据出口）：**
```python
@rx.var
def pending_bindings(self) -> list[dict]:
    if not self.is_admin:
        return []   # 直接返回空，不让任何数据泄漏
    return auth_api.list_pending_bindings()
```

#### P2f · admin 概览 + 绑定审批 UI

**新增/修改文件：**
- `xcpc_web/xcpc_web/states/admin_users.py`
- `xcpc_web/xcpc_web/pages/admin_users.py`
- `xcpc_web/xcpc_web/pages/admin_overview.py`（新建 `/admin` 首页）

**功能点：**
- `/admin`：概览页，展示待审批数量、最近审计摘要（审计表查询待四期完善，先只显示数字）
- `/admin/users`：
  - 等待审批的绑定请求列表（user_id、请求 player_id、reason、created_at）
  - 「批准 / 拒绝」按钮，确认后更新 `UserProfile.bound_player_id` + `BindingRequest.status`
  - 用户列表（username、role、绑定状态、最后登录时间）
- 操作记入审计日志 `AuditLog`（action: `binding.approve` / `binding.reject`）

### 4. 安全注意事项

参考 [09-认证与权限模块.md](./docs/09-认证与权限模块.md) §4：

| 手段 | 作用 | 是否足够防护 |
|------|------|:---:|
| `@require_login` 装饰器 | 未登录跳转登录页 | ❌ |
| `on_load` 守卫 | 无权限时重定向 | ❌ |
| `rx.cond` 隐藏组件 | UX 优化 | ❌ |
| **事件处理器内校验** | 拒绝非法写操作 | ✅ |
| **computed var 内校验** | 私有数据不出库 | ✅ |

关键纪律：
1. `bound_player_id` **永远**通过 computed var 从当前会话推导，不用 setter 写死
2. 所有写事件处理器首行检查 `is_authenticated` / `is_admin` / `has_permission_on(pid)`
3. computed var 涉及敏感数据的，无条件在最前加 `if not self.is_xxx: return []`
4. 审计日志对每个写操作生效

### 5. 风险与应对

| 风险 | 应对 |
|------|------|
| `reflex-local-auth` 文档不足，API 可能和预期不符 | P2a 开始先做最小 PoC：跑通注册→登录→读 profile，验证库版本兼容 |
| 首次注册用户没有 admin 来给自己提升权限 | CLI 提供一键创建首位 admin 的命令 |
| 注册开放给任何人会产生垃圾账号 | 后续考虑邀请码或域名限制（Gmail/校内邮箱）；一期先开放 |
| 同一次注册需要同时写 `localuser` + `UserProfile`，跨库事务 | 使用 SQLAlchemy session 同一实例管理两张表的事务 |

### 6. 未完成项（留到三期以后）

- 🚫 邮件服务（密码找回不可用 → admin 手动重置）
- 🚫 自由注册开放策略确认（待定，建议加域名白名单）
- 🚫 guest 权限细化（目前全站只读对 guest 完全开放）

---

## 开放问题（同步自路线图 §5）

- `data/public/` 只读导出是否有外部消费者 —— 待确认，无则砍掉
- 队员自助绑定意愿 —— 待确认

## 日志

| 日期 | 事项 |
|------|------|
| 2026-08-02 | 一期地基主体完成：打包、SQLite、CRUD、导入、contest/rating |
| 2026-08-17 | board 榜单聚合完成（commit `5fff907`） |
| 2026-08-18 | 首次进度盘点；下一步：创建 `xcpc_web` Reflex 骨架 |
| 2026-08-18 | P0 Reflex 骨架完成（`xcpc_web/`，空壳页可运行，core 桥接通） |
| 2026-08-18 | P1 榜单只读页完成（BoardState、筛选/排序/搜索、表格渲染）；一期关闭 |
| 2026-08-18 | P2 认证开发计划出炉，分 6 个子 Part（P2a~P2f） |
| 2026-08-18 | P2a 完成：`UserProfile`/`BindingRequest` SQLModel 表 + web DB（`xcpc_web.db`）+ `reflex-local-auth` 依赖；跨库 player FK 移除改为 service 层校验 |
| 2026-08-18 | P2b 完成：`AuthState` + `create_admin.py` CLI，`create_all` 与首个 admin 创建实测通过（`localuser.id=1`） |
| 2026-08-18 | P2c 完成：`/login` `/register` 页 + 路由；修掉 reflex 事件继承/super 异步坑（改覆写 `_register_user` + 本类实现 `handle_registration`）；注册/登录 Socket.IO E2E 通过 |
