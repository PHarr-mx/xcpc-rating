# Web 交互与页面（Reflex）

> **状态：提案 · 待评审 · 未实施**
> 隶属于 [09-Reflex-Web改造提案](./09-Reflex-Web改造提案.md)
> 关联：[08-前端展示模块](./08-前端展示模块.md)（Vue 版，本文取代之） · [11-认证与权限](./11-认证与权限模块.md) · [07-榜单模块](./07-榜单模块.md)

本文定义 Reflex 应用的 State 划分、路由、页面与组件。
采纳后取代 [08-前端展示模块](./08-前端展示模块.md)。

---

## 1. 技术栈

| 项 | 选型 | 说明 |
|----|------|------|
| 框架 | Reflex 0.9.x | 锁死具体版本，见 [09](./09-Reflex-Web改造提案.md) §8 |
| 组件 | `reflex-components-core` + `-lucide`（图标） | 随 Reflex 分包发布，各自独立版本 |
| 图表 | `reflex-components-plotly` | 原计划的 ECharts 无 Reflex 封装，不值得写 custom component |
| 认证 | `reflex-local-auth` | 见 [11](./11-认证与权限模块.md) |
| 手写 JS/TS | **无** | 全部 Python |

---

## 2. State 划分

| State | 职责 | 关键 var |
|-------|------|----------|
| `AuthState` | 继承 `reflex_local_auth.LocalAuthState`，全局基类 | `is_authenticated`（库提供）`is_admin` `bound_player_id`（本项目加，均为 computed var） |
| `BoardState` | 榜单页 | `mode` `period_type` `period_id` `search` `sort_by` `rows` |
| `PlayerDetailState` | 选手详情 | `player` `rating_history` `records_by_source` |
| `ContestDetailState` | 比赛详情 | `contest` `standings` |
| `ProfileState` | 自助改资料 | `my_oj_accounts` `binding_status` `form_error` |
| `AdminPlayerState` | 选手 CRUD | `players` `editing` `dialog_open` |
| `AdminTeamState` | 队伍 CRUD | `teams` `editing` |
| `AdminContestState` | 比赛列表与删除 | `contests` |
| `ImportState` | xlsx 在线导入 | `upload_progress` `staged_rows` `unmatched` `resolutions` |
| `RatingLabState` | 权重试算 | `draft_weights` `preview_rows` `diff_vs_current` |
| `AdminUserState` | 用户与绑定审批 | `users` `pending_bindings` |

### 2.1 视图模型：不要把 Pydantic BaseModel 塞进 state var

Reflex 的状态序列化对 Pydantic v2 `BaseModel` 支持不稳。
在 `xcpc_web/states/views.py` 用 `rx.Base` 或 dataclass 定义一层视图模型，
由该模块负责「领域模型 → 视图模型」转换：

```python
class BoardRowView(rx.Base):
    rank: int
    player_id: str
    name: str
    grade_label: str
    rating: int
    event_count: int
    delta_recent: int
```

附带好处：能精确控制哪些字段进浏览器。领域模型里的内部字段不会误传。

### 2.2 BoardState：文件矩阵消失

[05-数据导出与发布](./05-数据导出与发布模块.md) §5.4 要为 `mode × period` 每个组合预生成
一个 JSON（`ratings/formal_only/season_2025-春学期.json` 等）。

Reflex 里筛选条件只是 state var，切换即重查：

```python
class BoardState(rx.State):
    mode: str = "all"                    # formal_only|all
    period_type: str = "career"          # career|competition_year|season
    period_id: str = ""
    search: str = ""
    sort_by: str = "rank"

    @rx.var(cache=True)
    def rows(self) -> list[BoardRowView]:
        snap = board_api.board(self.mode, self.period_key, meta.data_version)
        return [to_view(r) for r in filter_and_sort(snap.rows, self.search, self.sort_by)]
```

`index.json` 与整套榜单文件目录都不再需要。
筛选条件仍应同步到 URL query（`/?mode=all&period=season&period_id=2025-春学期`）以便分享。

---

## 3. 路由

| 路径 | 页面 | 权限 |
|------|------|------|
| `/` | 榜单（默认 `all` + `career`） | guest |
| `/players/{player_id}` | 选手详情 | guest |
| `/contests/{contest_id}` | 比赛详情（formal/training 同页，按 `format` 切列） | guest |
| `/about` | 数据与赛季说明 | guest |
| `/login` `/register` | 认证 | guest |
| `/profile` | 我的资料、OJ 账号、绑定状态 | member |
| `/admin` | 概览 + 待审批 | admin |
| `/admin/players` | 选手 CRUD | admin |
| `/admin/teams` | 队伍 CRUD | admin |
| `/admin/contests` | 比赛列表 | admin |
| `/admin/import` | xlsx 上传 + 交互式匹配 | admin |
| `/admin/rating` | 权重试算 + 重算 | admin |
| `/admin/users` | 用户与绑定审批 | admin |
| `/admin/audit` | 审计日志 | admin |

比赛详情合并为一个路由（原 [08](./08-前端展示模块.md) §4 分了 formal/training 两条），
与 [10](./10-数据存储与迁移-SQLite.md) §4.1 的合表一致。

每个 `/admin/*` 与 `/profile` 都要挂 `on_load` 守卫，且页内私有数据必经带权限判断的
computed var —— 见 [11](./11-认证与权限模块.md) §4。

---

## 4. 页面设计

### 4.1 榜单页 `/`

```
┌─────────────────────────────────────────────────────────┐
│  XCPC Rating              [关于] [登录 / 我的资料 ▼]      │
├─────────────────────────────────────────────────────────┤
│  算法：placeholder_v0    数据版本：12                     │
├─────────────────────────────────────────────────────────┤
│  (●) 全部数据  ( ) 仅正式赛                              │
│  [ 生涯 ] [ 2025赛年 ] [ 2025秋学期 ▼ ]   [搜索选手____]  │
├─────────────────────────────────────────────────────────┤
│  # │ 姓名   │ 年级   │ Rating │ 场次 │ 近期 │            │
│  1 │ 张三   │ 2023级 │ 2456   │ 15   │ +32  │            │
└─────────────────────────────────────────────────────────┘
```

与原 Vue 设计的差异：

- 搜索框实时过滤（服务端算，无需前端分页逻辑）
- 列排序点表头即可，`sort_by` 是 state var
- 不再展示 `built_at`（数据是实时的），改展示 `data_version`
- `status=left` 的选手不出现；`retired` 显示「退役」标记，数据与 Rating 保留

### 4.2 选手详情 `/players/{id}`

沿用原 [08](./08-前端展示模块.md) §5.2 布局。新增：

- 若当前用户绑定的就是本选手，右上角出现「编辑我的资料」入口
- Rating 曲线用 Plotly，支持按 `mode` 过滤

### 4.3 我的资料 `/profile`

```
┌─────────────────────────────────────────────────────────┐
│  我的资料                                                │
│  绑定选手：张三 (p001)          [已绑定]                  │
├─────────────────────────────────────────────────────────┤
│  校内简称  [zs________]                                  │
│  曾用名    [Zhang San] [×]   [+ 添加]                    │
├─────────────────────────────────────────────────────────┤
│  OJ 账号                                                 │
│  Codeforces  zhangsan_cf   [×]                           │
│  [平台 ▼] [handle______]  [+ 添加]                       │
├─────────────────────────────────────────────────────────┤
│  姓名 / 年级 / 状态 由管理员维护                          │
└─────────────────────────────────────────────────────────┘
```

未绑定时改为显示绑定申请表单（选择选手 + 填说明），已申请则显示待审批状态。

admin-only 字段以只读文本呈现并注明原因 —— 比隐藏更好，避免用户以为功能坏了。

### 4.4 在线导入 `/admin/import`

**这是本次改造的核心价值。** 现在导入 xlsx 要写一段 `python -c "from importer import ..."`。

```
步骤 1  上传          [选择 .xlsx]  [上传]
步骤 2  填元信息      contest_id / 日期 / contest_type（→ 自动查权重）
步骤 3  解析预览      312 队，本校 8 队，奖牌线自动推算
步骤 4  匹配未识别    ┌──────────────────────────────────────┐
                     │ 「李某某」 → [新建选手 ▼] [p003 李冉曦]│
                     │ 「王某」   → [新建选手 ▼]              │
                     └──────────────────────────────────────┘
步骤 5  确认写入      [取消]  [确认导入]
```

关键设计：**解析结果先落 `ImportBatch`（`status=staged`），确认后才写正式表。**
中途关页面不会产生半截数据；未匹配项由人工逐个决策，替代现在的
`auto_create_players=True` 盲目自动建号。

### 4.5 权重试算 `/admin/rating`

左侧调 `contest_weights.yaml` 各项权重，右侧实时显示榜单与当前版本的 diff：

```
  div1+2  [100]        # │ 姓名 │ 当前 │ 试算 │ 变化
  div1    [ 95]        1 │ 张三 │ 2456 │ 2501 │ ▲ (=1)
  div2    [ 70]        2 │ 李四 │ 2410 │ 2380 │ ▼ (2→3)
  省赛    [ 70]
                       [放弃]  [应用并重算]
```

试算不落库、不进缓存（见 [09](./09-Reflex-Web改造提案.md) §5）。
「应用」才写 YAML 并 bump `data_version`，记 `weights.apply` 审计。

### 4.6 其余管理页

| 页面 | 要点 |
|------|------|
| `/admin/players` | 表格 + 弹窗表单；批量补 `grade`（现有 24 人全为 0） |
| `/admin/teams` | 队员集合识别，`member_key` 冲突时提示已存在的队 |
| `/admin/contests` | 列表 + 删除（删比赛须级联删 standings 与 rating_events） |
| `/admin/users` | 绑定审批：申请人 / 目标选手 / 说明 / [批准] [驳回] |
| `/admin/audit` | 按 user / action / 时间筛选 |

---

## 5. 组件

沿用原 [08](./08-前端展示模块.md) §8 的划分思路，从 `.vue` 文件变为 Python 函数：

```
xcpc_web/components/
├── layout.py           # page_shell(nav + footer)、admin_shell
├── board_table.py      # rating 榜表格
├── period_selector.py  # 模式 × 时间维度
├── rating_chart.py     # Plotly 折线
├── oj_link.py          # 平台 profile 外链，URL 模板集中在 config
├── standings_table.py  # 比赛成绩表，按 format 切列
└── form_fields.py      # 表单控件 + 错误提示
```

`rx.icon` 传静态名称时会生成按图标的深层导入而非从 Lucide barrel 引入，
能显著减小产物体积 —— **图标名尽量写字面量，不要用变量**。

---

## 6. 加载与错误态

| 场景 | 处理 |
|------|------|
| 数据加载中 | `rx.skeleton` 骨架屏 |
| 选手/比赛不存在 | 404 提示 + 返回榜单 |
| 表单校验失败 | 字段级错误文本，来自 `xcpc_core` 抛出的异常消息 |
| 唯一性冲突 | `PlayerValidationError` 的消息直接展示（如「OJ 账号已绑定其他选手」） |
| WebSocket 断开 | Reflex 内置重连提示；不额外处理 |
| 权限不足 | `on_load` 重定向 + toast |

---

## 7. 响应式与性能

- 校内规模（< 500 选手）全量榜单一次渲染即可
- 超 2000 行再考虑虚拟滚动
- Rating 曲线超 500 点时按赛年聚合
- 移动端：表格横向滚动，MVP 可接受

---

## 8. MVP 范围

| 包含 | 不包含 |
|------|--------|
| 榜单页 + 模式/周期切换 + 搜索排序 | 队伍详情页 |
| 选手详情 + Rating 曲线 | 深色模式 |
| 登录/注册/绑定申请 + `/profile` | 密码找回（由 admin 重置） |
| `/admin/players` `/admin/import` | OJ 数据在线导入 |
| 审计日志 | 训练赛在线录入（四期） |

---

## 9. 开放问题

| 项 | 状态 |
|----|------|
| 榜单筛选是否同步到 URL | 建议同步，便于分享 |
| 上传文件大小上限 | 待定，xlsx 通常 < 1MB，设 10MB 足够 |
| 是否需要队伍详情页 | 原 08 文档亦未包含，二期再议 |

---

*文档版本：v1.0 — 提案，未实施。取代 [08-前端展示模块](./08-前端展示模块.md)（采纳后）。*

