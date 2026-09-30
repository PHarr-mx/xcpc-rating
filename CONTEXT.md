# 会话上下文

> 最近更新：2026-10-01 · 本文记录「最近一次盘点对话」的结论，供下次打开快速恢复；进度本体见 [PROGRESS.md](PROGRESS.md)，计划与剩余工作见 [docs/08-路线图.md](docs/08-路线图.md)。

## 项目当前状态（2026-10-01）

- **里程碑：一期 ✅ 二期 ✅ 三期 ✅**；四期进行中：公式定案 + P-R1 + 积分制 v1 已落地
- **Web P0–P5 全部完成**；新布局（顶栏大类 + 恒显侧边栏）已上线
- **比赛统一化改造 P-U1 已落地（2026-10-01，按 CONTEST_UNIFICATION_PLAN.md）**：
  - 新表 `tier`（赛事等级=系数，config 种子 + 兜底「未分级」）与 `awardlevel`（奖项基线 金100/银60/铜30/优胜20），迁移 `0003_unify_contest`；真库已升级并验证存量映射（省赛→ICPC 省赛 0.7 计排名不计积分，测试积分场→`points_{id}` 计积分可申报）
  - `contest` 表改造：`format: icpc|ioi` × `entity: player|team` × `tier_id` + `max_value`/`scoring: formula|award_only`/`counts_for_points`/`counts_for_ranking`/`allow_claims`；旧列 source_type/contest_type/division/weight/rated **已删除**
  - `pointsevent` 已删表并入 contest；`pointsclaim`/`pointsentry` 改挂 `contest_id`，claim 支持 award 申报（value/rank 可空）
  - 新 `xcpc_core/tier/` 模块（六件套）；Web 新页 `/admin/tiers`（等级+奖项同页管理）、`/admin/contests` 统一创建表单、`/admin/points` 只留审批、`/points` 表单按 scoring 切换
  - core 195 + web 106 全绿；浏览器验收通过（临时管理员 pu1_verify 已删）
- 两轨制修订（D1）：「仅训练赛生效」→ 逐场 `counts_for_ranking`；榜单「仅正式赛」mode 已删除（`BoardMode = Literal["all"]`），formal_only URL 参数被忽略
- formal/OJ 仍为 placeholder_v0；P-U2（计分接线）与 P-U3（通用 JSON 导入）未开始

## 最近几次会话做了什么（2026-09-26 → 10-01）

1. **alembic 引入（旁路项一，已提交 `bbea601`）**：`db/migrations/`（基线 `0001_baseline`）+ `run_migrations` 自愈式接线 + 4 条守护测试（漂移检测关键）；真库已 stamp。**改 tables.py 必须配迁移，漏写被 `test_models_match_migrations_no_drift` 拦下**。
2. **formal 导入 DTO 前置校验（旁路项二，已提交 `94d0c7a`）**：解析结果四不变量进 model_validator；`contest_id` 防路径穿越（原直接拼 raw 文件名的窟窿）；contest_type 权重表查证前置到打开文件前、报错列出合法类型；16 条测试。
3. **Rating 公式定案 + P-R1（本次会话）**：
   - 拍板（用户）：候选 A（AtCoder 式）、同队三人同分、负分照实显示、仅训练赛生效、Center 统一 800 暂不分档；**队伍 APerf = 队伍自身历史队 Perf 加权平均（非队员均值）→ 换员即新队先验重置**。
   - 实现：`rating/formula_params.py`（常量集中）+ `formula.py`（solve_perf 二分 / 0.9^i×权重加权平均 / f(n) / g 变换）+ `replay.py`（`AtcoderReplayEngine`：场次×日期重放、打星参与方程不入历史、并列名次取平均、周期窗口全 Center 重放）+ `ReplayEventScore` 模型；21 条新测试（含闭式解与收敛数值断言）。
   - 文档：规格并入 docs/04 §2.1、§3 定案记录表更新、路线图 §3/§4 勾选。
4. **积分制 v1 实现（本次会话续）**：
   - core：`xcpc_core/points/`（formula/service/api/exceptions/models + DI `configure_session`），三表 `pointsevent`/`pointsclaim`/`pointsentry`（迁移 `0002_points`）；**部分唯一索引带 `status != 'rejected'` 谓词**——驳回后可重提，这个坑在 autogenerate 后人工核对时发现并修正。
   - 工作流：管理员配置场次（entity=player|team、kind=solved|score、max_value、n_teams）→ 选手/按队提交认证 → 审核通过同事务写双 owner 流水 + auditlog（points.approve/reject）；改配置不溯及（流水带参数快照）。
   - 复合分：队伍榜 = 0.6×团队积分 + 0.4×Σ(成员个人积分 − team_context=本队)，求和口径；个人榜直加，left 不出榜。
   - Web：`/admin/points`（创建场次 + 待审认证通过/驳回）、`/points`（提交认证 + 我的认证 + 双榜），审计筛选动作已加 points.*。
   - 待办：**浏览器手工验收**（项目惯例的里程碑关闭动作）；P4 正式赛免认证直录、P5 防刷上限（最好 N 场）未实现，见 §9.5。

5. **前端美化 + 比赛统一化 P-U1（09-30 → 10-01）**：
   - 布局定案并上线（顶栏四大类 + 侧边栏小项，`page_shell(section=, subsection=)` 字面量高亮）；主题在 rxconfig.py 的 RadixThemesPlugin。
   - P-U1 按评审稿全量落地（详见顶部「项目当前状态」）；关键决策：D1 重排名口径（原始名次保留给积分百分位，内部重排名 1,2,3…并列取平均喂 Perf 方程，`<2` 实体场次跳过）、D6 存量映射（省赛保留，测试积分场并入）。
   - 迁移 `0003` 是**手写重建式**：运行时连接 `PRAGMA foreign_keys=ON` 且事务内 pragma 是 no-op，rename/drop 父表会被隐式 DELETE 卡住 → 先把五张表数据读进内存、按「子表→父表」drop、再建新表回插。downgrade 只还原结构不回搬数据。
   - board「仅正式赛」模式随 source_type 删除而移除；`RatingEvent.source_type="contest"`，占位计算器按 `(format, entity)` 路由，payload 用 `internal_rank`/`n_recorded`（重排名口径）。

更早（2026-09-10 → 09-15）：三期关闭、GAP 评估并入路线图、榜单 URL query 同步、data_version 写路径自动 bump、`/about`、P5 详情页（players/contests + recharts）、docs 九篇重构、赛年/赛季筛选真实生效、测试盲区补齐、推送 `90b0cef..aa412c0`。

## 关键技术结论（下次开发直接复用，避免重踩）

### alembic 约定（2026-09-26 起）
- **改 `tables.py` 必须生成迁移**：`uv run python -m xcpc_core.db.migrations.revision -m "..."`（autogenerate 拿 metadata 与 head 状态真库 diff，**生成后人工核对再提交**）；漏写会被 `test_models_match_migrations_no_drift` 拦下。
- 测试内存库**不走 alembic**（自开连接 `:memory:` 建完即丢），conftest 继续 `Base.metadata.create_all`；`run_migrations` 对 `:memory:` 显式抛错。
- `env.py` 开 `render_as_batch=True`：SQLite ALTER 受限，加列/改列走 batch，别手写裸 `op.add_column` 之外的 SQLite DDL。
- 认证库 `xcpc_web.db` 不在迁移体系内（SQLModel `ModelRegistry` 独立 metadata，`create_admin.py` 建）；若将来动它再单独收编。

### Reflex 0.9.7 要点
- State 链手工构建：`_reflex_internal_init=True` + 父链（如 LocalAuthState→AuthState→目标 State）。
- **主题配置走 `rxconfig.py` 的 `rx.plugins.RadixThemesPlugin(theme=rx.theme(...))`**：`App(theme=...)` 在 0.9.0 已弃用且实测不生效；主题改动需重启服务（rxconfig 不热重载），app 模块改动对部分路由 HMR 会失效（"No module update found"），也需重启。
- **布局外壳**（2026-09-30 定案）：顶栏四大类（榜单/积分/个人资料/系统管理，按身份条件渲染）+ 恒显示侧边栏（类内小项）；各页显式传 `page_shell(section=, subsection=)` 字面量做高亮，「我的认证」在个人资料页。
- **动态路由参数不能声明同名 state var**（`DynamicRouteArgShadowsStateVarError`），从 `self.router.page.params` 读；`is_self` 等时敏判断也要直读 params 而非 on_load 设置的 var。
- Var 约束：不能 iterate/`or`/`bool()` 一个 Var；列表/字典视图在 State 里**预计算成 view dict**；`rx.cond` 构建时两个分支都求值（`href=None` 会炸，用 `""` 哨兵）；计算属性要 `cache=False`。
- `rx.redirect(path, replace=True)` = 客户端导航（URL 同步用）。

### 测试红线
- **测试里禁止 `import xcpc_web.xcpc_web`（app 模块）**：顶层 `rx.App()` 会破坏 conftest 手搭的 State 链，引发 49 个跨测试 DB 复用失败。
- conftest 用 `configure_session(session)` / `configure_store(store)` DI 注入内存 SQLite（player/team/contest/audit/importer/rating/board/points/tier 全部已接）；真实 DB 零改动。contest service 的 tier 兜底解析走**同会话** TierStore，不跨库。
- 测试命令：core `uv run python -m pytest xcpc_core -v`（根目录）；web `cd xcpc_web && ../.venv/bin/python -m pytest tests -v`。根 pyproject testpaths 只含 xcpc_core。

### 数据层约定
- board 缓存 key `(mode, period_key, data_version)`；写路径 bump（`db/meta.bump_data_version`）后缓存自动换 key。
- schema 唯一入口 `db.migrations.run_migrations`；`db/migrate.py` = schema 升级 + raw 灌数据（幂等）；raw→DTO 映射复用 `importer.formal._contest_create_from_document`（统一比赛模型 + tier 解析）。
- **运行时 SQLite 连接 `PRAGMA foreign_keys=ON`**（session.py 逐连接挂载）→ 迁移中 rename/drop 被子表引用的父表会被卡；重建式迁移先 stash 数据再按子→父顺序 drop（0003 即此模式）。
- 正式赛导入的 tier 解析：`tier_api.ensure_tier_for_contest_type(contest_type)`，config YAML 的 label/weight 为权威（缺失自动建），等级表可被管理端改名但导入会按 config 重建。
- `RatingEvent` 无 contest_id 字段，从 `event_id.split("#",1)[0]` 取前缀（与 delete_contest 约定一致）。
- openpyxl xcpcio 格式：A1 标题、第 2 行表头、第 3 行起数据；需 A–H 连续题列；只有获奖本校队进 standings。
- web 导入测试需要把 `contest_weights.yaml` **和** `school.yaml` 都拷进临时仓库。

## 下一步

1. **P-U2 计分接线（CONTEST_UNIFICATION_PLAN §7）**：compute_points 统一（formula/award_only × 系数，core 侧已就位）→ 导入/认证 → 流水全链路核对；`counts_for_ranking` 事件流已过滤，**board 训练/生涯榜切 `AtcoderReplayEngine`**（tier.coefficient 进 0.9^i 时间加权）+ 选手页曲线换 rating_after + `meta.rating_algorithm` 升版；详情页标签已做，可复查。
2. **P-U3 通用 JSON 导入**：任意比赛数据导入（姓名匹配/自动建队复用 formal 逻辑），原「训练赛录入」方案并入此通道。
3. 积分制遗留：P4 正式赛免认证直录、P5 防刷上限（RATING_FORMULA_PLAN §9.5）。
4. CONTEST_UNIFICATION_PLAN.md 定稿后并入 docs/03、04 并删除本稿（稿首注明）。
5. 挂起开放决策见 docs/08 §4：OJ 立项（#3）、注册限制（#4）为五期前阻塞项。

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
