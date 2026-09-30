# 比赛统一化改造方案（评审稿）

> 2026-09-30 · 按用户设想细化，**审核通过后动工**；定案后并入 docs/03、04 并删除本稿。

## 1. 目标与对既有决策的修订

把「正式赛 / 训练赛 / 积分场次」三套并列概念统一为一个**比赛**实体：

- **一个入口创建**（管理员 Web 表单）：选赛制（ICPC/IOI）、参与形式（个人/团队）、赛事等级，填基础信息（时间、参与人数、max_value 等）；
- **赛事等级**由管理员前端 CRUD，等级决定**积分系数**（系数同页管理）；
- **比赛数据两通道**：管理员导入，或选手申报（认证-审核流）；
- **逐场双开关**：管理员决定该场记入积分 / 记入排名；
- 成绩行支持**获奖信息**；
- 未公开完整排名的比赛：创建时勾选「**积分只由奖项决定**」，此类比赛强制只能记积分、不能记排名。

**对既有决策的修订（需知悉）**：
1. 两轨制 Q3「Rating 仅训练赛生效」→ 被**逐场 `counts_for_ranking` 开关**取代：任何有完整名次数据的比赛都可进排名；数据不全（award_only）的比赛被规则天然排除。训练赛/正式赛从「体系隔离」降级为「赛事等级标签」。
2. 积分公式引入**等级系数**（此前无权重）。

## 2. 统一数据模型

### 2.1 新表 `tier`（赛事等级，前端 CRUD）

`id, name（如 ICPC 区域赛/省赛/校赛/周训练）, coefficient（float，积分系数）, sort_order`

初始数据迁移：把 `contest_weights.yaml` 的 formal_types + training_divisions 权重映射为初始等级（系数 = weight/100）。

### 2.2 新表 `awardlevel`（奖项基线分，与 tier 同页管理）

`id, name（金/银/铜/优胜…）, base_points（建议初始 金100/银60/铜30/优胜20）, sort_order`

最终奖项分 = 基线 × tier.coefficient。

### 2.3 `contest` 表改造（统一比赛）

| 处置 | 字段 |
|------|------|
| 保留 | id, title, date, competition_year, season, n_teams(原 total_teams), school_teams_count, source_file |
| 变更 | `format`: icpc\|ioi（赛制，原 team_xcpc/solo_xcpc/oi 三值拆开） |
| 新增 | `entity`: player\|team（参与形式，从 format 拆出，与积分制对齐） |
| 新增 | `tier_id` → tier（赛事等级，替代 contest_type/division/weight） |
| 新增 | `max_value`（全场最高解题数/得分，formula 模式参数） |
| 新增 | `scoring`: formula\|award_only（计分方式） |
| 新增 | `counts_for_points` / `counts_for_ranking`（双开关，bool） |
| 新增 | `allow_claims`（允许选手申报，默认开；导入的正式赛可关） |
| 废弃 | contest_type, division, weight, weight_source, rated, source_type（语义由 tier 与 flags 承载） |

**约束**（DTO validator + service）：`scoring=award_only ⇒ counts_for_ranking=False`；`counts_for_ranking=True ⇒ scoring=formula`；formula 场次 `max_value ≥ 1`。

### 2.4 `pointsevent` 废弃 → 并入 contest

字段映射：title/date/entity 直迁；kind: solved→icpc、score→ioi；max_value/n_teams 直迁。迁移 `0003`：搬数据 → 删表。

### 2.5 `pointsclaim` → 通用认证（选手申报通道）

- `event_id` → `contest_id`（FK 改指 contest）；
- 新增 **award 申报列**：award_only 场次必填（gold/silver/bronze/…，须在 awardlevel 内），value/rank 置空；
- 状态机与「驳回后可重提」的部分唯一索引不变（谓词相应调整为按 contest + owner + award 组合）。

### 2.6 `pointsentry`（流水）

- `event_id` → `contest_id`；payload 快照增加 tier 系数；
- 计分入口统一 `compute_points(contest, result)`：
  - **formula**：`100 × (value/max_value) × 名次百分位 × tier.coefficient`
  - **award_only**：`awardlevel.base_points × tier.coefficient`
- 双账本（队伍赛三人共享）与审计不变。

### 2.7 `standing`（成绩行）

- `award` 列已有 ✓——award_only 场次允许「只有 award、无 solved/rank」的行；
- RatingEvent 生成只取 `counts_for_ranking=True` 的比赛；无 rank 的行天然跳过。

## 3. 排名与积分的计算口径

- **排名 = Rating 重放引擎**（AtcoderReplayEngine 不改），事件流只来自 `counts_for_ranking=True` 的比赛。名次口径（2026-09-30 与用户确认）：
  - **原始名次保留**：入库 standings 存全省/全场原始名次，积分百分位用它（外部比赛含金量的体现）；
  - **排名引擎做内部重排名**：事件生成时按原始名次排序转换为入库实体内部名次（1,2,3…，并列取平均）——原始全省名次直接喂方程会无解（r−0.5 可能超过入库实体数），重排名是数学上必须的一步；
  - 外部选手不入方程；曾被否决的替代方案：把外部队当 Center 幻影 entrant——等于假设外校全是新手，污染本校表现分；
  - 语义代价：排名 = 校内相对强度，跨校绝对强度信号丢失，由等级系数部分补偿；数据完整性由管理员把关；
  - 护栏：**入库实体 < 2 的场次跳过排名**（单实体 Perf 恒等于自身先验，纯噪声），事件生成时跳过并留日志；
- **排名侧权重 = tier.coefficient**（进 0.9^i 时间加权，`0.9^i × coefficient`）——顺便取代旧 division 权重机制，一个系数两处用；
- **积分百分位用原始名次**：`100 × (value/max_value) × ((n_teams − rank + 1)/n_teams) × tier.coefficient`，rank/n_teams 为全场原始值；
- **双 flag 事后变更只影响后续数据**，已记流水不溯及（快照机制不变）。

## 4. 数据两通道

### 4.1 管理员导入
- **正式赛 xlsx**（xcpcio 格式）：现有 importer 保留，产物写统一 contest（award 列已带）；
- **通用 JSON 模板**：训练赛及任意比赛（原「训练赛录入」方案并入此通道，含姓名匹配/自动建队复用）；
- 导入时可由数据回填 n_teams / max_value。

### 4.2 选手申报（认证流）
- `/points` 认证表单选比赛 → 按 scoring 出表单：formula 填 value/rank，award_only 选奖项；
- admin 审批 → 记分（同事务审计不变）；allow_claims=False 的场次不接受申报。

## 5. 对现有系统的处置清单

| 现有物 | 处置 |
|--------|------|
| contest_weights.yaml + load_formal/training_weight | 废弃 → tier 表（初始迁移） |
| pointsevent 表 | 数据迁入 contest 后删表 |
| source_type（formal/training） | 废弃；raw 归档统一 `data/raw/contests/{id}.json` |
| format 三值 | icpc/ioi + entity 二维 |
| rated / weight / weight_source 列 | 废弃 |
| 正式赛 xlsx 导入器 | 保留，产物写统一 contest |
| 积分认证流 | 保留，改挂 contest + award 申报 |
| 两轨制 Q3 | 修订为逐场 counts_for_ranking（见 §1） |

## 6. Web 改动清单

- `/admin/contests` 升级：统一创建表单（赛制/形式/等级/时间/人数/max_value/计分方式/双开关/allow_claims）+ 场次列表 + 数据导入入口；
- `/admin/tiers`（新）：赛事等级 CRUD + 系数 + 奖项基线分，同页管理；
- `/admin/points` → 认证审批：改挂 contest，支持奖项申报审核；
- `/points`：认证表单按 scoring 切换；双榜不变；
- `/contests/{id}` 详情页：展示等级/奖项/计分策略标签。

## 7. 实施分期

| 期 | 内容 | 估量 |
|----|------|------|
| **P-U1 数据与管理端** | tier/awardlevel 表 + 迁移（含存量映射）+ 管理页；contest 表改造 + 统一创建表单；claim/entry 改挂 contest；既有测试迁移 | ~1 天 |
| **P-U2 计算接线** | compute_points 统一（formula/award_only × 系数）；导入/认证 → 流水；counts_for_ranking → 事件流 + replay；/points 表单按 scoring 切换；详情页标签 | ~1 天 |
| **P-U3 通用 JSON 导入** | 通用 JSON 模板导入（含姓名匹配/自动建队），原训练赛录入方案并入 | ~半天 |

存量数据策略（数据量小）：省赛记录保留迁移；测试积分场与流水清空重灌。

## 8. 待拍板决策点

| # | 决策 | 推荐 |
|---|------|------|
| D1 | 记入排名 = 进 Rating 重放引擎（按实际入库实体的相对名次），取代「仅训练赛」旧决策 | 是 |
| D2 | 奖项基线分全局一套 × 等级系数（初始 金100/银60/铜30/优胜20） | 是 |
| D3 | 选手可申报 award_only 场次（申报奖项，admin 审核） | 是 |
| D4 | 排名权重 = tier.coefficient（进时间加权） | 是 |
| D5 | 创建表单加 allow_claims 开关（默认开） | 是 |
| D6 | 存量数据：省赛保留迁移，测试积分场清空重灌 | 是 |
