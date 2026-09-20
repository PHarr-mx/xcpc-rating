# 会话上下文

> 最近更新：2026-09-15 · 本文记录「最近一次盘点对话」的结论，供下次打开快速恢复；进度本体见 [PROGRESS.md](PROGRESS.md)，计划与剩余工作见 [docs/08-路线图.md](docs/08-路线图.md)。

## 项目当前状态（2026-09-15）

- **里程碑：一期 ✅ 二期 ✅ 三期 ✅（2026-09-10 浏览器手工验收通过后关闭）**；四期（业务补齐）、五期（上线）未开始
- **Web P0–P5 全部完成**：榜单 `/`、认证、`/profile`、管理后台 P4a–P4d、`/about`、`/players/{id}`、`/contests/{id}`、URL query 同步、赛年/赛季筛选
- 测试：core 118 + web 94 全绿；main 已推送远端（`aa412c0`），本地与远端同步，工作区干净
- Rating 仍为 `placeholder_v0`（名次线性分 + 做题加成，数值无业务含义）——这是四期要解决的核心
- 根目录有一个来历不明的未跟踪文件 `pelican-riding-bicycle.svg`（测试残留样式的图片，代码中无引用，未处理）

## 最近几次会话做了什么（2026-09-10 → 09-15，按提交顺序）

1. **三期关闭**：admin 用浏览器全程不敲 CLI 完成 CRUD/审批/导入五步，验收通过。
2. **缺失功能评估**：产出 `GAP_REPORT_PLAN.md` 评审稿（14 项分 A–F 六档），评审通过后逐项执行；执行完毕后该文件已删除，内容并入 [docs/08-路线图.md](docs/08-路线图.md)。
3. **榜单筛选同步 URL query**（`states/board.py`）：on_load 白名单解析 mode/period_type/search/period_id，`_sync_url()` 用 `rx.redirect(replace=True)` 客户端导航。
4. **`meta.data_version` 写路径自动 bump**（`db/meta.py` + player/contest service 接线）：选手/比赛写路径落库前 bump，榜单缓存自动失效；flush-only、事务原子。
5. **`/about` 静态页**：数据来源与赛季说明。
6. **P5 详情页**：
   - `/players/{player_id}`：档案 + OJ 外链（codeforces/atcoder/luogu 模板）+ 参赛记录表 + recharts 累计 Rating 曲线 + 本人「编辑我的资料」入口 + 404 兜底；core 侧新增 `rating.api.player_event_history`（按日期排序、累计 rating_after、contest 标题联查）。
   - `/contests/{contest_id}`：元信息行 + 成绩表按 format 切两套列（xcpc 解题/罚时 vs oi 得分）；队员姓名解析（含离队）、打星标记、奖项中文；404 兜底。
   - 组件：`oj_link` / `rating_chart`（内置 recharts 替代原计划 plotly，零新增依赖）/ `standings_table`；`form_fields` 取消（无消费方）。
   - 联动：榜单选手名 → 选手详情、选手页比赛名 → 比赛详情。
7. **docs 全量重写**：15 篇合并重组为 9 篇（README + 01–08 按主题），废弃文档删除留 Git 历史；`docs/08-路线图.md` 是剩余工作的权威来源。
8. **赛年/赛季筛选真实生效**：`calendar.resolve_period_dates` + `PeriodFilter` 模型层 validator 自动解析日期；board 周期下拉改为按数据覆盖范围生成具体选项（`board.api.available_periods`）。
9. **测试盲区补齐**：calendar、audit、migrate（端到端 + 幂等）、staged confirm/discard、TrainingOi/Solo/OjContest/OjPractice/Dispatcher 计算器；顺带修复 migrate 子函数无视 repo_root 参数的 bug。
10. **推送远端** 4 个提交（`90b0cef..aa412c0`）。

## 关键技术结论（下次开发直接复用，避免重踩）

### Reflex 0.9.7 要点
- State 链手工构建：`_reflex_internal_init=True` + 父链（如 LocalAuthState→AuthState→目标 State）。
- **动态路由参数不能声明同名 state var**（`DynamicRouteArgShadowsStateVarError`），从 `self.router.page.params` 读；`is_self` 等时敏判断也要直读 params 而非 on_load 设置的 var。
- Var 约束：不能 iterate/`or`/`bool()` 一个 Var；列表/字典视图在 State 里**预计算成 view dict**；`rx.cond` 构建时两个分支都求值（`href=None` 会炸，用 `""` 哨兵）；计算属性要 `cache=False`。
- `rx.redirect(path, replace=True)` = 客户端导航（URL 同步用）。

### 测试红线
- **测试里禁止 `import xcpc_web.xcpc_web`（app 模块）**：顶层 `rx.App()` 会破坏 conftest 手搭的 State 链，引发 49 个跨测试 DB 复用失败；app 模块语法错误也因此无测试兜底（曾踩过：两行 import 被误合并成一行）。
- conftest 用 `configure_session(session)` / `configure_store(store)` DI 注入内存 SQLite（player/team/contest/audit/importer/rating/board 全部已接）；真实 DB 零改动。
- 测试命令：core `uv run python -m pytest xcpc_core -v`（根目录）；web `cd xcpc_web && ../.venv/bin/python -m pytest tests -v`。根 pyproject testpaths 只含 xcpc_core。

### 数据层约定
- board 缓存 key `(mode, period_key, data_version)`；写路径 bump（`db/meta.bump_data_version`）后缓存自动换 key。
- `RatingEvent` 无 contest_id 字段，从 `event_id.split("#",1)[0]` 取前缀（与 delete_contest 约定一致）。
- openpyxl xcpcio 格式：A1 标题、第 2 行表头、第 3 行起数据；需 A–H 连续题列；只有获奖本校队进 standings。
- web 导入测试需要把 `contest_weights.yaml` **和** `school.yaml` 都拷进临时仓库。

## 下一步（docs/08-路线图 §3，按建议顺序）

1. **旁路二项（零依赖，随时可做）**：alembic 引入（四期动表结构前必须）+ formal 导入 DTO 前置校验（`total_teams`、`contest_type` 提前到 Pydantic 报错）。
2. **四期第一步 = 业务定案（写代码前必须拍板）**：① Rating 正式公式（加权 Elo / 队内分摊 / 时间衰减 / 初始分与封顶，见 docs/04 §2–3）；② 训练赛成绩分摊规则（均分 vs 按贡献）。助手已提议产出「公式决策稿」：2–3 个候选公式 + 用现有省赛数据算示例值 + 优劣与实现成本，供用户评审。
3. **四期实现（依赖定案）**：计算器替换（版本号 + 缓存联动 + 测试重写）→ 训练赛录入（导入入口 + `load_training_weight` + raw/training 归档）→ `/admin/rating` 试算页（P6，试算不落库）→ 图表升级。
4. **五期（四期后）**：先定**注册限制**（邀请码 / 域名白名单，公网前必须），再做部署三件套（生产 rxconfig、`reflex export` + rsync、systemd、Caddy、备份 cron，清单见 docs/06 §7）。
5. 挂起的 12 条开放决策见 docs/08 §4，其中仅 #1 公式、#2 分摊、#4 注册限制是阻塞项。

上次会话结束时的分叉点：**「alembic + DTO 前置校验」或「公式决策稿」，等用户二选一**，未拍板前不要擅自动工。

## 常用命令速查

```bash
source ./setup_env.sh                    # 环境激活（uv 版，项目根目录）
uv run python -m pytest xcpc_core -v     # core 测试
cd xcpc_web && ../.venv/bin/reflex run   # 开发服务器（3000/8000）
```
