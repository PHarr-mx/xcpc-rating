# 会话上下文

> 最近更新：2026-09-26 · 本文记录「最近一次盘点对话」的结论，供下次打开快速恢复；进度本体见 [PROGRESS.md](PROGRESS.md)，计划与剩余工作见 [docs/08-路线图.md](docs/08-路线图.md)。

## 项目当前状态（2026-09-28）

- **里程碑：一期 ✅ 二期 ✅ 三期 ✅**；四期（业务补齐）进行中：**公式定案 + P-R1 已落地**，训练赛录入未开始
- **Web P0–P5 全部完成**：榜单 `/`、认证、`/profile`、管理后台 P4a–P4d、`/about`、`/players/{id}`、`/contests/{id}`、URL query 同步、赛年/赛季筛选
- **四期业务定案完成（2026-09-28 拍板）**：训练赛 Rating = **AtCoder 式表现分体系**（规格 docs/04 §2.1）——同队三人同分、负分照实显示、仅训练赛生效；**P-R1 重放引擎已落地**（core 159 + web 94 全绿）
- **生涯积分制（第二轨）规格讨论中**（2026-09-30）：UCup 式单场分（去 GP30、≥1 题门槛、maxSolved/n_teams 管理员配置）+「场次配置 → 选手认证 → 审核记分」工作流；底稿 RATING_FORMULA_PLAN.md §9，**实现与训练赛录入相互独立**
- 旁路二项已清（alembic + DTO 前置校验，均已提交）；formal/OJ 仍为 placeholder_v0

## 最近几次会话做了什么（2026-09-26 → 09-28）

1. **alembic 引入（旁路项一，已提交 `bbea601`）**：`db/migrations/`（基线 `0001_baseline`）+ `run_migrations` 自愈式接线 + 4 条守护测试（漂移检测关键）；真库已 stamp。**改 tables.py 必须配迁移，漏写被 `test_models_match_migrations_no_drift` 拦下**。
2. **formal 导入 DTO 前置校验（旁路项二，已提交 `94d0c7a`）**：解析结果四不变量进 model_validator；`contest_id` 防路径穿越（原直接拼 raw 文件名的窟窿）；contest_type 权重表查证前置到打开文件前、报错列出合法类型；16 条测试。
3. **Rating 公式定案 + P-R1（本次会话）**：
   - 拍板（用户）：候选 A（AtCoder 式）、同队三人同分、负分照实显示、仅训练赛生效、Center 统一 800 暂不分档；**队伍 APerf = 队伍自身历史队 Perf 加权平均（非队员均值）→ 换员即新队先验重置**。
   - 实现：`rating/formula_params.py`（常量集中）+ `formula.py`（solve_perf 二分 / 0.9^i×权重加权平均 / f(n) / g 变换）+ `replay.py`（`AtcoderReplayEngine`：场次×日期重放、打星参与方程不入历史、并列名次取平均、周期窗口全 Center 重放）+ `ReplayEventScore` 模型；21 条新测试（含闭式解与收敛数值断言）。
   - 文档：规格并入 docs/04 §2.1、§3 定案记录表更新、路线图 §3/§4 勾选；RATING_FORMULA_PLAN.md 保留为积分制讨论底稿（§9 暂缓）。

更早（2026-09-10 → 09-15）：三期关闭、GAP 评估并入路线图、榜单 URL query 同步、data_version 写路径自动 bump、`/about`、P5 详情页（players/contests + recharts）、docs 九篇重构、赛年/赛季筛选真实生效、测试盲区补齐、推送 `90b0cef..aa412c0`。

更早（2026-09-10 → 09-15）：三期关闭、GAP 评估并入路线图、榜单 URL query 同步、data_version 写路径自动 bump、`/about`、P5 详情页（players/contests + recharts）、docs 九篇重构、赛年/赛季筛选真实生效、测试盲区补齐、推送 `90b0cef..aa412c0`。

## 关键技术结论（下次开发直接复用，避免重踩）

### alembic 约定（2026-09-26 起）
- **改 `tables.py` 必须生成迁移**：`uv run python -m xcpc_core.db.migrations.revision -m "..."`（autogenerate 拿 metadata 与 head 状态真库 diff，**生成后人工核对再提交**）；漏写会被 `test_models_match_migrations_no_drift` 拦下。
- 测试内存库**不走 alembic**（自开连接 `:memory:` 建完即丢），conftest 继续 `Base.metadata.create_all`；`run_migrations` 对 `:memory:` 显式抛错。
- `env.py` 开 `render_as_batch=True`：SQLite ALTER 受限，加列/改列走 batch，别手写裸 `op.add_column` 之外的 SQLite DDL。
- 认证库 `xcpc_web.db` 不在迁移体系内（SQLModel `ModelRegistry` 独立 metadata，`create_admin.py` 建）；若将来动它再单独收编。

### Reflex 0.9.7 要点
- State 链手工构建：`_reflex_internal_init=True` + 父链（如 LocalAuthState→AuthState→目标 State）。
- **动态路由参数不能声明同名 state var**（`DynamicRouteArgShadowsStateVarError`），从 `self.router.page.params` 读；`is_self` 等时敏判断也要直读 params 而非 on_load 设置的 var。
- Var 约束：不能 iterate/`or`/`bool()` 一个 Var；列表/字典视图在 State 里**预计算成 view dict**；`rx.cond` 构建时两个分支都求值（`href=None` 会炸，用 `""` 哨兵）；计算属性要 `cache=False`。
- `rx.redirect(path, replace=True)` = 客户端导航（URL 同步用）。

### 测试红线
- **测试里禁止 `import xcpc_web.xcpc_web`（app 模块）**：顶层 `rx.App()` 会破坏 conftest 手搭的 State 链，引发 49 个跨测试 DB 复用失败。
- conftest 用 `configure_session(session)` / `configure_store(store)` DI 注入内存 SQLite（player/team/contest/audit/importer/rating/board 全部已接）；真实 DB 零改动。
- 测试命令：core `uv run python -m pytest xcpc_core -v`（根目录）；web `cd xcpc_web && ../.venv/bin/python -m pytest tests -v`。根 pyproject testpaths 只含 xcpc_core。

### 数据层约定
- board 缓存 key `(mode, period_key, data_version)`；写路径 bump（`db/meta.bump_data_version`）后缓存自动换 key。
- schema 唯一入口 `db.migrations.run_migrations`；`db/migrate.py` = schema 升级 + raw 灌数据（幂等）。
- `RatingEvent` 无 contest_id 字段，从 `event_id.split("#",1)[0]` 取前缀（与 delete_contest 约定一致）。
- openpyxl xcpcio 格式：A1 标题、第 2 行表头、第 3 行起数据；需 A–H 连续题列；只有获奖本校队进 standings。
- web 导入测试需要把 `contest_weights.yaml` **和** `school.yaml` 都拷进临时仓库。

## 下一步（docs/08-路线图 §3 第四步，按建议顺序）

1. **训练赛录入（四期第 2 项）**：导入入口 + `load_training_weight` + events training 分支 + raw/training 归档（见 docs/03 §3.4）；这是 P-R2 接线的前置——没有训练赛事件，重放引擎无数据可算。
2. **P-R2 接线**：board 训练赛榜走 `AtcoderReplayEngine`（生涯/赛年/赛季三档）+ 选手详情页曲线换 rating_after 语义 + `meta.rating_algorithm` 升版。
3. **P-R4 试算页 `/admin/rating`**：两轨参数试算（不落库）。
4. **积分制（第二轨）v1**：规格见 RATING_FORMULA_PLAN.md §9（工作流已定，细节 P1–P5 待定）；**与训练赛录入相互独立，可并行或提前**，等用户定优先级。
5. 挂起的开放决策见 docs/08 §4：OJ 立项（#3）、注册限制（#4）为五期前阻塞项，其余不阻塞。

## 关键技术结论（下次开发直接复用，避免重踩）

### 训练赛 Rating（AtCoder 式，2026-09-28 定案）
- **改公式参数只动 `rating/formula_params.py`**（Center=800、尺度 400/6、衰减 0.9、首场膨胀 1.5、f 满额 1200）。
- 引擎是**重放式**（跨选手耦合、时间序依赖），不能塞进逐事件 `BaseRatingCalculator` 接口；消费入口统一 `AtcoderReplayEngine.compute_series(events, period=)`，输出 `ReplayEventScore{date, perf, rating_after}`。
- 事件要求：`event_id` 前缀 = contest_id；payload 必须有合法 `rank`；队伍成员名次必须一致（违反直接抛错）；打星 = `payload.unofficial=True`。
- 队伍先验 = **队伍自身历史**（team_id 分组），换员即新队（member_key 约定）先验回 Center；个人历史跨队累计、组队/solo 混流。
- 周期榜语义：窗口内以全 Center 重放（「这个赛年若从零开始」），与生涯全史重放并存。

## 常用命令速查

```bash
source ./setup_env.sh                    # 环境激活（uv 版，项目根目录）
uv run python -m pytest xcpc_core -v     # core 测试
cd xcpc_web && ../.venv/bin/reflex run   # 开发服务器（3000/8000）
uv run python -m xcpc_core.db.migrate    # schema 迁移 + raw 灌数据（幂等）
uv run python -m xcpc_core.db.migrations.revision -m "..."  # 改 tables.py 后生成迁移
```
