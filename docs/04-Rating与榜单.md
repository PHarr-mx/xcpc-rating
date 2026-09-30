# Rating 与榜单

> 定位：**参考 + 待建**。关联：[03-比赛与导入](03-比赛与导入.md) · [05-Web与认证](05-Web与认证.md) · [08-路线图](08-路线图.md)

- **rating 模块**（`xcpc_core/rating/`）：把统一事件流按 `source_type` 分发到计算器，算出选手得分
- **board 模块**（`xcpc_core/board/`）：把得分聚合成榜单快照（只读，缓存）

> 实现状态（2026-09-28）：**训练赛 Rating 公式已业务定案（§2.1，AtCoder 式表现分，P-R1 实现中）**；
> formal/OJ 暂沿用 placeholder_v0（§2.2），激励职能规划由生涯积分制（第二轨，暂缓讨论）承担。

---

## 1. 计算器架构

```
BaseRatingCalculator (ABC)                  compute() = base × weight / 100
├── FormalCalculator               "formal"        ✅（placeholder 公式）
├── TrainingDispatcher → 按 format 分发  "training"  🔜 骨架已写，无数据
│   ├── TrainingTeamXcpcCalculator    team_xcpc
│   ├── TrainingSoloXcpcCalculator    solo_xcpc
│   └── TrainingOiCalculator          oi
├── OjContestCalculator            "oj_contest"    🔜 已写，永不触发（无数据源）
└── OjPracticeCalculator           "oj_practice"   🔜 已写，永不触发（无数据源）
```

- 基类接口：`compute_base_score(event)`（抽象）+ 模板方法 `compute(event) = base * event.weight / 100`
- `RatingEngine`（`rating/engine.py`）编排：**过滤（mode/period）→ 逐事件算分 → 按 player 聚合得分序列（按 date 升序）**
- 权重：formal 按 `contest_type`、training 按 `division` 查 `contest_weights.yaml`（导入阶段写入事件）；OJ 用 `oj.contest_default` / `practice_default`
- 算法与流水线解耦：正式算法确定后只换对应子类，`meta.rating_algorithm` 版本号随之更新
- **训练赛重放引擎**（`rating/replay.py`，§2.1 定案的实现载体）：AtCoder 式公式跨选手耦合、按时间序依赖（第 r 名的表现分依赖当时全场先验），与逐事件计算器不同，须按场次 × 日期重放全场事件流

## 2. 现行公式

### 2.1 训练赛 Rating：AtCoder 式表现分（✅ 定案 2026-09-28）

> 来源：AtCoder Rating System ver. 1.00（2016 官方文档）。语义：回答「谁现在更强」——
> 零和、会涨会跌、新手负分、场次少被压制（f(n) 即隐式置信度）。仅对训练赛生效（定案 Q3）。

**参数**（集中于 `rating/formula_params.py`，试算页 P6 可调）：Center=800（无历史先验锚点，暂不分档）、Logistic 尺度 400 / 赔率基数 6、时间衰减 0.9^i、首场膨胀 1.5、f 补项满额 1200。

**APerf（进场先验）**：`APerf = Σ Perf_i·0.9^i·(w_i/100) / Σ 0.9^i·(w_i/100)`（i=1 最新；w_i = 场次权重，division 查表融进时间加权）。无历史 → Center。

**历史归属（定案）**：组队赛以**队伍**为参赛实体，APerf = **队伍自身历史队 Perf** 加权平均（非队员个人均值）；换员即新队（member_key 约定），先验重置 Center，个人历史跨队累计。solo/oi 以个人为实体。

**Perf（由名次反解）**：第 r 名（n 实体参赛，各带 APerf_j）的表现分 X 是下式唯一解（二分搜索）：

```
Σ_{j=1..n} 1 / (1 + 6^((X − APerf_j)/400)) = r − 0.5
```

并列名次取平均（并列 3–6 名都按 4.5）；首场（实体无历史）`Perf = (Perf − Center)×1.5 + Center`；不设封顶（AtCoder RATEDBOUND 防顶级选手低级赛刷分，学校规模无此问题）；打星队参与方程、先验记 Center、不入任何历史。

**Rating（个人展示）**：

```
Rating = g⁻¹( Σ g(Perf_i)·0.9^i·(w_i/100) / Σ 0.9^i·(w_i/100) ) − f(n)
g(X) = 2^(X/800)；  f(n) = (F(n)−F(∞))/(F(1)−F(∞))×1200；  F(n) = sqrt(Σ0.81^i)/Σ0.9^i
```

g 空间平均 = 赢大分、输小分；f(1)=1200 收敛到 0——恒定打出 X 从 X−1200 起步、约 10 场收敛。**同队三人同分（定案）**：队 Perf 全额记入每名队员个人历史。**负分照实显示（定案）**。

**周期榜语义**：生涯榜全史重放；赛年/赛季榜从周期起点以全 Center 重放窗口内事件。

### 2.2 formal / OJ：placeholder_v0（过渡）

| 计算器 | 公式 |
|--------|------|
| Formal | `max(0, (total_teams - rank + 1) / total_teams * 1000 + solved * 50)` |
| OJ 比赛 | `max(0, delta)` |
| OJ 做题 | `rating_numeric * 0.5 + solve_count * 2` |

（原 Training 三个计算器随 §2.1 上线后退役。）数值无业务含义；正式赛的激励职能由「生涯积分制」（第二轨，暂缓讨论，见 [08-路线图](08-路线图.md) §4）规划承担，届时 formal/OJ 是否保留 rating 由该定案一并处置。

## 3. 公式方向定案记录（原四期定案清单）

| 方向 | 结论 | 状态 |
|------|------|------|
| 对手实力建模（原「加权 Elo」） | AtCoder 式表现分：名次 + 全场先验反解，非逐场 Elo | ✅ 2026-09-28 |
| 初始分与收敛 | Center 锚点 + f(n) 补项 | ✅ 2026-09-28 |
| 时间衰减 | 0.9^i，场次权重乘入 | ✅ 2026-09-28 |
| 队内分摊 | 同队三人同分，无分摊 | ✅ 2026-09-28 |
| 置信度展示 | f(n) 隐式解决，不做独立标注 | ✅ 2026-09-28 |
| OJ 归一化 | platform_factor | ⬜ 随 OJ 立项 |
| 生涯积分制（第二轨） | 只累加的贡献分；作业待立项 | ⏸ 暂缓讨论 |

## 4. 触发时机：运行时按需算

- 不预生成文件；榜单页每次筛选组合（mode × period）实时计算
- 当前规模（校内选手、数十场比赛）全量重算为毫秒级，无需增量缓存
- **权重试算**走独立路径：草稿权重算出的结果不落库、不进缓存，仅在页面与当前榜单 diff；「应用」才写 YAML 并 bump `data_version`（P6 待建）

## 5. 榜单模式与时间维度

| 模式 | `mode` | 数据源 |
|------|--------|--------|
| 仅正式赛 | `formal_only` | `source_type = formal` |
| 全部数据 | `all` | formal + training + oj_* |

| 维度 | `period_type` | 定义 |
|------|---------------|------|
| 生涯 | `career` | 首次参赛至今全部记录 |
| 赛年 | `competition_year` | 当年 9/1 至次年 8/31（`2025赛年`） |
| 赛季 | `season` | 秋学期（9–1 月）/ 寒假（2 月）/ 春学期（3–6 月）/ 暑假（7–8 月） |

> **实现现状（✅ 2026-09-14 已接线）**：`PeriodFilter` 的 type+id 在模型层自动解析为
> start/end（`utils/calendar.resolve_period_dates`；显式传入日期优先，无法解析则不过滤），
> 引擎过滤、board meta、缓存 key 全部随之生效；周期下拉选项由
> `board_api.available_periods()` 按数据覆盖范围生成（生涯 + 各赛年 + 四季）。
> 手输 URL 的非法周期值回落为不过滤，与「非法值忽略」口径一致。

## 6. 榜单输出（BoardSnapshot）

```python
BoardSnapshot(
    meta=BoardMeta(mode, period_type, period_id, period_label, start, end,
                   algorithm="placeholder_v0", data_version, tie_break, generated_at),
    rows=[BoardRow(rank, player_id, name, grade_label, rating, event_count, delta_recent)],
)
```

- **排名规则**：rating 降序；同分按 player_id 字典序（稳定可复现）；竞赛排名 1, 2, 2, 4（同分同 rank、下一名跳号）
- `delta_recent`：周期内最近一次事件对该选手的得分贡献
- 离队（`left`）选手不出现在榜单；退役（`retired`）保留；年级展示用入学年（`grade=0` 显示「未设置」）
- 生成时间等 meta 展示在榜单页脚（含 data_version，供确认数据新鲜度）

**选手历史（rating_history）**：`rating.api.player_event_history(player_id, mode=, session=)`（✅ 2026-09-11，P5）
返回 `PlayerEventRecord` 列表——按 (date, event_id) 升序的逐场记录（比赛、名次/解题、贡献）+ 逐场累计
`rating_after`（与榜单 placeholder 聚合语义一致）；测试注入用 `configure_session`（DI 镜像 importer/audit）。
选手详情页消费；OJ/训练赛事件就绪后自动纳入。

## 7. 缓存与失效（已实装）

`xcpc_core/board/api.py`：

- 缓存 key：`(mode, period_key, data_version)`，进程内 dict，上限 256 条（满即全清）
- `data_version` 存于 `meta` 单行表；`board()` 每次调用先读 meta——**写路径已统一接入自动 bump**：
  - `xcpc_core/db/meta.py` 提供 `bump_data_version(session)`：只 flush 不 commit，随调用方事务原子提交/回滚
  - player service（create/update/delete）与 contest service（save/delete）在业务写前调用；
    importer 确认、一步式导入、补队、CLI 经 service 自动覆盖
- `board.invalidate()` 保留为手动兜底（外部工具直改库后调用）
- 注入 `session` 的调用（测试）不走缓存
- 另有 `compute_rating(mode, period, session)` 供纯 Rating 结果消费（不出榜单行）

## 8. 开放问题

见 [08-路线图](08-路线图.md) §4「待定决策」：OJ 归一化（随 OJ 立项）、积分制规格（暂缓，
讨论底稿 RATING_FORMULA_PLAN.md）、分项榜（当前仅总分榜，无历史快照存档）。

---

*docs/ v2 重构（2026-09-11）：合并原 06-Rating计算模块、07-榜单模块；数据导出（05，可选）的榜单文件矩阵方案已随 Reflex 运行时计算废弃。*
