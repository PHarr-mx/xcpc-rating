# 功能缺失评估 · 计划（评审稿）

> **状态：评审稿，待评审。** 本文不是正式报告，而是撰写正式报告前的完整评估计划 + 三路调研已核实的结论，供逐条评审。
> 日期：2026-09-10 ｜ 调研基线：main @ 7fbfea2
> **评审进展（2026-09-10）**：管理员确认三期浏览器手工验收已通过、未发现问题 → §3-① 关闭；docs/13（升 v1.6）、docs/14（升 v1.7）状态已回写为三期 ✅。
> 评审通过后：按本文结构撰写正式报告 `GAP_REPORT.md`（保存于项目根目录）；届时**不改任何代码、不改 docs/**。本文可保留作评审记录或删除。

---

## 0. 文档目的与状态

- **目的**：回答「现在还有哪些功能是缺失的」。以 docs/ 规划文档为基准、以代码实况为证据，给出一份可核查、可排序的缺失清单，作为正式报告 `GAP_REPORT.md` 的蓝本。
- **性质**：评审稿。所有结论均附证据（`文件:行号` 或 docs 章节），不含臆测；与文档状态标记不一致的代码层新发现单独标注。
- **评审关注点建议**：① 分级（A–F）是否符合你的优先级直觉；② 「待定/可选」项是否单列得当；③ 第 5 节落地顺序是否认可；④ 是否有遗漏的缺失项或证据错误。

## 1. 调研方法与信息来源

三路并行只读探索，交叉验证后汇总：

| 路径 | 覆盖范围 | 主要信息源 |
|------|----------|-----------|
| 规划文档层 | docs/ 全部 15 个文档（01–14、DESIGN.md、skills.md） | 里程碑状态标记、各模块设计章节、开放问题 |
| 后端实现层 | `xcpc_core/`（player/team/contest/importer/rating/board/db/utils/audit）+ data/ + 测试 | 代码实况、placeholder 标记 grep、表模型、测试覆盖 |
| 前端与运维层 | `xcpc_web/`、skill/、仓库根、部署相关 | 路由清单、认证/权限实现、console_scripts、部署产物有无 |

**证据约定**：`路径:行号` 为代码证据；「docs/NN §X」为文档证据；引用原文时用引号标出。

## 2. 现状核实摘要

### 2.1 里程碑进度（docs/13-实施路线图.md v1.5，2026-08-25）

| 期 | 内容 | 文档状态 | 核实结论 |
|----|------|----------|----------|
| 一期 · 地基 | 打包、建表、JSON 迁移、contest/rating 骨架、board、Reflex 骨架、`/` 榜单页 | ✅ 已完成（2026-08-18） | 一致 |
| 二期 · 认证 | reflex-local-auth、角色与绑定审批、`/profile`、审计日志 | ✅ 已完成（2026-08-20） | 一致 |
| 三期 · 管理后台 | 选手/队伍 CRUD、xlsx 在线导入 + 交互式匹配（P4a–P4d） | ✅ 已完成（2026-09-10） | 本轮评审确认验收通过后已回写：docs/13 v1.6、docs/14 v1.7 三期 ✅（原唯一遗留 §3-① 关闭） |
| 四期 · 业务补齐 | 训练赛录入、Rating 计算器实现、权重试算页、图表 | ⬜ 未开始 | 一致 |
| 五期 · 上线 | systemd + Caddy + 备份 cron | ⬜ 未开始 | 一致 |

CONTEXT.md 自评：整体进度约 55–60%，「分水岭在四期」。

### 2.2 事实底盘

- **前端路由（10 条，已核实 `xcpc_web/xcpc_web/xcpc_web.py:26-74`）**：`/`（公开榜单）、`/login`、`/register`、`/profile`、`/admin`（概览）、`/admin/users`（绑定审批）、`/admin/players`、`/admin/teams`、`/admin/contests`、`/admin/audit`、`/admin/import`（在线导入）。**没有**详情页、about、权重试算页。
- **数据库（16 张表，`xcpc_core/db/tables.py`）**：Player、OJAccount、PlayerAlias、Team、TeamMember、TeamAlias、Contest、Standing、StandingMember、OJContest、OJContestResult、OJSnapshot、RatingEvent、Meta、AuditLog、ImportBatch。其中 **OJ 三表为零读写代码**。
- **CLI 入口（pyproject console_scripts）**：仅 `xcpc-player`、`xcpc-team` 两个。无 web/export/data 相关入口。
- **测试**：core 侧 11 个测试文件（player/team/contest/importer/rating/board/plog）；web 侧 10 个文件约 1358 行（State 层，含导入五步流程）。**无浏览器端 E2E 测试**；根 `pyproject.toml` 的 `testpaths = ["xcpc_core"]`，web 测试需单独指定运行。
- **近期相关提交**：三期管理后台 P4a–P4d（36c7f20）、create_admin `--reset-password`（97c1905）、预备队员状态（efcd257）、核心 API session 泄漏修复（8d3cb12）。
- **部署产物**：无 Dockerfile、docker-compose、systemd unit、Makefile、Caddyfile、scripts/ 或 bin/ 目录。部署形态只存在于 docs/11 设计文档。

## 3. 缺失功能明细（按优先级六档，共 14 项）

> 每项含：现状 / 证据 / 影响 / 范围估算。范围估算为粗粒度（改动面），供评审排序用，非工期承诺。

### A. 收尾项（已完成功能的最后一公里）

#### ① 三期浏览器手工验收 ✅ 已完成（2026-09-10，评审确认）
- **原状**：P4a–P4d 的 Web 集成、自动化测试、staged→confirmed 导入流程均已完成并写测试，唯余浏览器手工验收未做（docs/13 v1.5 原话：「由于当前环境无法绑定 Reflex 前端端口，仍需浏览器手工验收后将三期状态改为 ✅」）。
- **闭环**：2026-09-10 管理员确认手工验收通过、全程未发现问题；docs/13 升 v1.6、docs/14 升 v1.7，三期标记 ✅。本项从缺失清单移除，此处保留作评审记录。

#### ② 榜单筛选条件同步 URL query ✅ 已完成（2026-09-11）
- **原状**：`/` 榜单页的 mode/period 筛选只落在 State，不写 URL（docs/14 P1 第 6 项 ⬜）。
- **闭环**：2026-09-11 实现——`BoardState.on_load` 从 URL query 恢复筛选（非法值忽略），`set_mode_sync_url` / `set_period_sync_url` / `set_search_sync_url` 经 `rx.redirect(replace=True)` 写回 URL；默认值不进 URL。新增回归测试 `xcpc_web/tests/test_board_url_sync.py`（10 条）；core 77 + web 78 全绿。docs/14 升 v1.8。本项从缺失清单移除，此处保留作评审记录。

### B. 四期核心业务（分水岭，未开始）

#### ③ Rating 真实公式（替换 placeholder_v0）
- **现状**：评分公式为占位实现——各事件按「名次百分位 × 权重」线性折算后**纯求和**，无任何 Elo 类特征（无对手实力建模、无期望胜率、无 K 因子、无初始分/收敛、无时间衰减，事件可无限累加不封顶）。榜单数值无业务含义（CONTEXT.md：「榜单 algorithm 为 placeholder_v0，数值无业务含义」）。
- **证据**：
  - `xcpc_core/rating/calculators.py:3`：「占位公式 placeholder_v0（docs/06 §2.5）——非最终业务规则」；
  - Formal 公式 `calculators.py:38`：`max(0, (total_teams - rank + 1)/total_teams * 1000 + solved * 50)`；训练赛组队/个人/OI `:51/:63/:75`；OJ 两类 `:104/:115`；
  - `engine.py:65`：`rating = round(sum(各事件得分))`；
  - 版本号贯穿：`db/tables.py:195`（meta.rating_algorithm 默认值）、`board/models.py:16`（DEFAULT_ALGORITHM）；
  - docs/06 开放问题原话：「Rating 正式公式 — 待定，当前 placeholder_v0」。
- **影响**：系统的核心价值（Rating 统计）尚未成立；榜单页、详情页、图表均建立在该数值之上。
- **范围估算**：大。前置是**公式本身待定**（业务决策，docs/06 §2.6 列了方向：加权 Elo、队内分摊、时间衰减等）；落地为 docs/06 设计的 `BaseRatingCalculator` 继承体系替换、engine 聚合策略、算法版本号与 board 缓存联动、全部相关测试重写。

#### ④ 训练赛录入（training 数据源）
- **现状**：表结构/DTO/权重配置**已备好但零入口**——contest 合表支持 `source_type="training"` 与 `division` 字段，`contest_weights.yaml` 已有 `training_divisions`（div1+2=100 / div1=95 / div2=70 / div3=60），但无任何导入 API/importer/CLI；rating 事件生成对 training 只有占位分支；`data/raw/training/` 为空目录。
- **证据**：
  - `xcpc_core/importer/models.py:8`：`SourceFormat = Literal["xcpcio_xlsx"]`（唯一格式）；`models.py:42-54`：`FormalImportParams.format` 写死 `"team_xcpc"`；
  - grep 全包无 `stage_training` / `import_training` / `load_training_weight`（`importer/weights.py` 只有 `load_formal_weight`）；
  - `xcpc_core/rating/events.py:3`：「当前数据源只有 formal；training/OJ 的数据源到位后在此扩展」；`:49`：「# training 占位：组队用 team_count/size，个人用 player_count」；
  - docs/03 §4 设计了三种 format（team_xcpc/solo_xcpc/oi）× 四档 division；docs/04 中 `data/raw/training/` 标注「（设计中）」。
- **影响**：Rating 的第二大数据源缺失；且 docs/03 开放问题「训练赛成绩如何摊到选手 — 待定」是公式落地的业务前置之一。
- **范围估算**：大。训练赛录入形式（在线表单/导入格式）需先定，然后 importer（staged 流程复用与否）、division→weight 加载器、事件生成 training 分支、raw 归档路径（`raw/training/`）、测试。

#### ⑤ 权重试算页 `/admin/rating`（P6）
- **现状**：完全未开始。
- **证据**：docs/14 P6 无状态标记，且前置写明「四期 Rating 计算器已实现，试算才有业务含义」；docs/08 §4.5 设计了 RatingLabState（draft_weights / preview_rows / diff_vs_current）。
- **影响**：无试算能力时，正式公式调参只能改配置→重算→看结果，风险高。
- **范围估算**：中。新页面 + State + 「不落库的试算路径」（core 需支持 dry-run 计算），强依赖 ③。

#### ⑥ 图表（Plotly Rating 曲线）
- **现状**：完全未开始；`rating_chart.py` 组件不存在。
- **证据**：docs/13 四期第 4 项；docs/14 P5 提及「Rating 曲线在真实公式（四期）落地前展示的是 placeholder 数据，可先上」；代码核实 `xcpc_web/` 无该组件。
- **影响**：选手 Rating 随时间变化不可视化（依赖 ③ 之后数据才有意义）。
- **范围估算**：中。组件 + 依赖 ⑦ 的详情页挂载点。

### C. P5 详情页与组件（docs/14 P5，未开始）

#### ⑦ 三个详情页 + 三个组件
- **现状**：`/players/{id}`、`/contests/{id}`、`/about` 三条路由及配套组件 `standings_table.py`（按 format 切列成绩表）、`oj_link.py`（OJ 外链）、`form_fields.py`（表单控件）在代码中均不存在。
- **证据**：docs/14 P5 无状态标记（未开始）；代码核实 `xcpc_web/pages/` 仅 index/login/register/profile/admin×7，components/ 仅 layout、board_table、period_selector。
- **影响**：公开侧目前只有一张榜单总表；选手个人页（Rating 曲线、分 Tab 成绩、绑定本人后「编辑我的资料」入口）与比赛详情页（榜单系统面向「展示」的核心体验）缺失。
- **范围估算**：中-大。三个页面 + 三个 State（PlayerDetailState/ContestDetailState 等）+ 组件；`/about` 为静态页可先行。core 侧预计仅需少量只读查询补充（如按选手聚合全部事件、按比赛取 standings 展示形态）。

### D. 五期上线（未开始）

#### ⑧ 部署与运维三件套
- **现状**：systemd service、Caddy 反代、SQLite 备份 cron、生产 `rxconfig`（api_url/环境变量）全部只有设计文档，无可执行产物。
- **证据**：docs/11 全文为设计（Caddyfile、`reflex export --frontend-only` + rsync、systemd unit、`30 4 * * * sqlite3 .backup` 均为文档示例）；仓库核实无 Dockerfile/systemd/Makefile/scripts 目录；`rxconfig.py` 仅本地开发配置；docs/13 五期 ⬜ 未开始，完成标志「公网可访问」。
- **影响**：系统只能在开发机跑；无备份策略，SQLite 单文件数据有丢失风险。
- **范围估算**：中。以服务器环境为准：Caddyfile + systemd unit + 备份脚本/cron + rxconfig 生产化 + 部署文档落地为脚本。

### E. 数据源扩展（设计已备、代码为零或可选）

#### ⑨ OJ 数据源（oj_contest / oj_practice）
- **现状**：OJContest / OJContestResult / OJSnapshot 三张表**零读写业务代码**；OJ 类事件无生成代码；`OjContestCalculator`/`OjPracticeCalculator` 已写好但永远不会被实际数据触发；OJAccount（4 平台）表已有、`/profile` 已支持自助填写，但没有任何抓取/同步。
- **证据**：`db/tables.py:130/:141/:155`（三表定义）；grep 全包仅 tables.py 自身引用；docs/04 §8 开放问题「OJ 数据导入（contests/snapshots）二期后再定适配器」；docs/08 §8 MVP 明确「不包含 OJ 数据在线导入」。
- **影响**：三表 + 两计算器 + oj 权重配置（`contest_weights.yaml` 的 `oj` 节，注释「算法待定」）构成完整设计，但整条链路不通；是否做属于**范围决策**（先于代码决策）。
- **范围估算**：大（且不确定）。需先定适配器方案（爬虫/API/手工导入）与各 OJ Rating 归一化（docs/06 开放问题「待定」）。

#### ⑩ `data/public/` 只读导出与 xcpc-data CLI
- **现状**：docs/05 整模块「降级为可选」；`xcpc-data export` / `dump-json` CLI 未编写；`data/public/` 目录存在但无产出代码。
- **证据**：docs/05 v2.0 状态「设计（可选）」；docs/13 §5 开放问题「`data/public/` 只读导出是否有外部消费者 — 待确认，无则可完全砍掉」；docs/11:78 已声明「原『数据 cron（xcpc-data export）』删除——数据是运行时算的」；AGENTS.md 亦注明「`xcpc-data update` / `xcpc-site build|deploy` 尚未编写」。
- **影响**：无外部消费者即可砍掉；属于**待确认后的取舍**，非必然缺口。
- **范围估算**：小（做或砍都是小动作）；先走确认流程。

### F. 工程健壮性（不影响功能演示，但影响正确性/演进）

#### ⑪ `meta.data_version` 无自动 bump，榜单缓存失效靠手动 ✅ 已完成（2026-09-11）
- **原状**：board 缓存 key 含 data_version，失效设计上依赖写路径 bump `meta.data_version`，但 core 内没有任何 bump 实现，`invalidate()` 也无调用方——缓存 key 永远不变，进程存活期间榜单页持续命中旧快照（代码层新发现，docs 未记载）。
- **闭环**：2026-09-11 实现——新增 `xcpc_core/db/meta.py` 的 `bump_data_version(session)`（只 flush 不 commit，随调用方事务原子提交/回滚）；player service 的 create/update/delete 与 contest service 的 save/delete 在业务写前调用（importer 确认、一步式导入、补队经这两个 service 自动覆盖；CLI 与 Web 同享）。`invalidate()` 保留为手动兜底。新增回归测试 `xcpc_core/tests/test_data_version_bump.py`（7 条，含端到端缓存失效链路）；core 84 + web 78 全绿。本项从缺失清单移除，此处保留作评审记录。

#### ⑫ alembic 迁移未引入
- **现状**：schema 演进靠 create_all + 一次性 migrate 脚本。
- **证据**：docs/10 §5「开发期用 create_all，schema 稳定后引入 alembic」；docs/01 §1 中 `alembic/` 目录为规划项未建。
- **影响**：四期若改 rating/contest 相关表结构，生产库无受控迁移路径。
- **范围估算**：小-中。引入 alembic + 首版 baseline。

#### ⑬ 测试盲区
- **现状**：`utils/calendar.py`（赛年/赛季边界）、`audit/api.py`、`db/migrate.py`、importer staged 的 confirm/discard（core 层）、`TrainingOiCalculator`、`OjPracticeCalculator`、TrainingDispatcher、未知 format 报错路径均无测试。
- **证据**：core 测试文件清单核实（11 个），逐模块比对。
- **影响**：四期动 rating/训练赛时，这些路径恰是改动热点，无回归保护。
- **范围估算**：小-中，可随四期开发顺带补。

#### ⑭ formal 导入 DTO 校验偏弱
- **现状**：`FormalImportParams.contest_type` 必填但合法性只靠 `load_formal_weight` 在读取时 `raise ValueError` 兜底；`total_teams` 无校验（仅注释约定 formal 必填）。
- **证据**：`xcpc_core/importer/models.py:42-54`；`importer/weights.py:16-17`（未知 contest_type 抛错）；`contest/models.py:34` 注释「formal 必填 total_teams」无校验实现。
- **影响**：错误参数报错时机晚、信息偏底层；Web 导入五步流程的报错体验依赖此。
- **范围估算**：小。Pydantic 校验器前移。

## 4. 「待定 / 可选」开放问题清单（单列，与承诺功能区分）

> 以下为 docs 中明确标「待定/可选/再议」的事项。它们不是「已规划未做」，而是「决策未关」；评审时可顺手给出决策，即可从本清单移入 §3 或移出范围。

| # | 事项 | 文档出处 | 现状备注 |
|---|------|----------|----------|
| 1 | 密码找回（无邮件服务，建议 admin 重置） | docs/09 §8 | CLI 侧已实现（`create_admin.py --reset-password`，97c1905），**UI 侧无 admin 重置入口** |
| 2 | 自由注册限制（邀请码 / 域名白名单） | docs/09 §8 | 原话「否则公网会有垃圾注册」；五期上线前需决策 |
| 3 | 队伍详情页 | docs/08 §9「二期再议」 | 未议 |
| 4 | 深色模式 | docs/08 §8 | 明确不包含 |
| 5 | 上传文件大小上限 | docs/08 §9「待定，设 10MB 足够」 | 未实现限制 |
| 6 | 训练赛成绩如何摊到选手 | docs/03 开放问题 | ③④ 的业务前置 |
| 7 | OJ Rating 归一化 | docs/06 开放问题 | ⑨ 的业务前置 |
| 8 | 是否展示「置信度」 | docs/06 开放问题 | 随公式设计 |
| 9 | `data/public/` 只读导出去留 | docs/05、docs/13 §5 | 「无外部消费者则可完全砍掉」 |
| 10 | `xcpc-data dump-json` / `data/processed/` 彻底删除 | docs/10 §8 | 仅「建议」状态 |

## 5. 建议落地顺序（含依赖说明）

```
① 三期浏览器验收 ✅ 已完成（2026-09-10，三期已关闭）
② URL query 同步 ✅ 已完成（2026-09-11）
        │
        ▼
⑦ P5 详情页（/about 可先行；Rating 曲线挂点留出）
        │
        ▼
【四期 · 分水岭】
 ③ 公式定案（业务决策：加权 Elo / 分摊 / 衰减 ← 依赖 6、8 号开放问题）
   → ③ 计算器落地 → ④ 训练赛录入（含 6 号决策）→ ⑤ 试算页 → ⑥ 图表
   （③④⑤⑥ 之间：⑤⑥ 依赖 ③；④ 可与 ③ 并行推进，事件生成在 events.py 汇合）
        │
        ▼
【五期 · 上线】⑧ 部署三件套（前置：2 号开放问题——注册限制需在公网前定案）
        │
  旁路：F 档（⑪⑫⑬⑭）建议随四期开发顺带处理，⑪ 可提前单独做
  取舍：⑨ OJ、⑩ 导出 —— 走「确认后再定」流程，不排入主线
```

要点：四期是全项目分水岭（CONTEXT.md 原话），其第一步不是写代码而是**公式与分摊规则的业务定案**；⑪（data_version bump）是唯一建议提前的健壮性项，因为在线导入已在三期投产使用。

## 6. 下一步行动清单（三期关闭后）

> 三期已于 2026-09-10 关闭（§3-①）。以下按「先易后难、先决策后编码」排序，括号内编号对应 §3 缺失项与 §4 开放问题。

**第一步 · 零依赖小项（可立即开工，互不阻塞）**

1. **URL query 同步（②）** ✅ 已完成（2026-09-11）。
2. **data_version 自动 bump（⑪）** ✅ 已完成（2026-09-11）：`db/meta.py` + player/contest service 写路径接线 + 7 条回归测试。
3. **`/about` 静态页（⑦ 的一部分）**：无数据依赖，可随手先上。

**第二步 · P5 详情页主体**

4. `/players/{id}`、`/contests/{id}` 两个详情页 + `standings_table` / `oj_link` / `form_fields` 组件；core 侧补只读查询（按选手聚合事件、按比赛取 standings）。Rating 曲线先挂占位数据的图表骨架，四期公式落地后填真值（docs/14 P5 原话：「可先上」）。

**第三步 · 四期启动 = 业务定案（写代码前必须拍板）**

5. **Rating 公式定案（③ 的前置）**：加权 Elo / 队内分摊 / 时间衰减 / 初始分与封顶怎么定（即开放问题 #6、#8）→ 产出写进 docs/06 的公式规格。
6. **训练赛分摊规则定案（④ 的前置）**：训练赛成绩如何摊到选手（开放问题 #6）。

**第四步 · 四期实现（依赖上一步定案）**

7. `BaseRatingCalculator` 继承体系替换 placeholder_v0（算法版本号、board 缓存联动、相关测试重写）。
8. 训练赛录入（staged importer 是否复用 + division→weight 加载器 + events training 分支 + `raw/training/` 归档）。
9. 权重试算页 `/admin/rating`（试算不落库、不进缓存）。
10. Plotly 图表挂到详情页。

**第五步 · 五期上线前**

11. **注册限制决策（开放问题 #2）**：公网前必须定（邀请码或域名白名单，否则垃圾注册）。
12. **部署三件套（⑧）**：Caddyfile + systemd unit + 备份 cron + rxconfig 生产 `api_url`。

**贯穿纪律**：每步合入前两套测试全绿（`uv run python -m pytest xcpc_core -v` + `cd xcpc_web && ../.venv/bin/python -m pytest tests -v`）；四期动表结构前先引入 alembic（⑫）。

## 7. 批准后的下一步

评审通过本计划后，按本文结构撰写正式报告 `GAP_REPORT.md` 保存至项目根目录：

- 结构与本文一致（总览 → 明细 → 开放问题 → 顺序），措辞转为正式报告体；
- 不改任何代码、不改 docs/；
- **验收标准**：① 位置正确（根目录 `GAP_REPORT.md`）；② 每条缺失项均带可核查证据（文件:行号 / docs 章节）；③ 结论与 docs/13 v1.6、docs/14 v1.7 状态标记一致，代码层新发现（⑪ data_version、OJ 表零代码、测试盲区、DTO 校验）单独标明来源为代码核实；④ 开放问题与承诺功能严格分列。
