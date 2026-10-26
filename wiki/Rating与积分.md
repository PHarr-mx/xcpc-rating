# Rating 与积分

本系统有**两条独立轨**：

| 轨 | 度量什么 | 算法 | 数据来源 |
|----|----------|------|----------|
| **Rating** | 「谁现在更强」 | AtCoder 式表现分重放 | `counts_for_ranking=True` 的比赛 |
| **生涯积分** | 「投入与积累」 | UCup 式单场分累加 | `counts_for_points=True` 的比赛 + 认证 |

两轨由每场比赛的两个开关独立控制，互不影响。

---

# 第一轨：Rating

- **`rating` 模块**（`xcpc_core/rating/`）：事件生成 + 重放引擎 + 权重试算
- **`board` 模块**（`xcpc_core/board/`）：榜单聚合（只读，缓存）

## 1. 引擎架构

```
AtcoderReplayEngine（榜单唯一算法，meta.rating_algorithm = atcoder_v1）
  按 (场次, date) 重放统一比赛事件流 → 每选手逐场 ReplayEventScore{perf, rating_after}

BaseRatingCalculator (ABC)         compute() = base × weight / 100（旧逐事件路径）
├── ContestDispatcher   "contest"      已写，不再被榜单消费
├── FormalCalculator    "formal"       同上
├── TrainingDispatcher  "training"     同上
├── OjContestCalculator "oj_contest"   已写，永不触发（无数据源）
└── OjPracticeCalculator"oj_practice"  已写，永不触发（无数据源）
```

- 旧逐事件路径（`rating/engine.py`）**保留未消费**：为将来 OJ 数据源复用
- 事件权重 = **tier.coefficient × 100**（事件生成阶段写入，整数；重放内融进 0.9^i 时间加权）
- 算法版本记录在 `meta.rating_algorithm`（迁移 `0004_atcoder_v1`）

## 2. AtCoder 式表现分

> 来源：AtCoder Rating System ver. 1.00（2016 官方文档）。语义：回答「谁现在更强」——
> 零和、会涨会跌、新手负分、场次少被压制（f(n) 即隐式置信度）。

### 2.1 参数

集中于 `rating/formula_params.py`（不可变 dataclass `FormulaParams`），可在 `/admin/rating` 试算页调整：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `center` | 800.0 | 无历史先验锚点（对应 AtCoder ABC 档，暂不分档） |
| `logistic_scale` | 400.0 | Logistic 尺度：实力差 400 分 → 期望对局赔率 1:6 |
| `logistic_odds` | 6.0 | 赔率基数 |
| `g_scale` | 800.0 | g 变换尺度 `g(X)=2^(X/g_scale)` |
| `time_decay` | 0.9 | 时间权重 `0.9^i`（i=1 最新，约 22 场半衰） |
| `first_perf_inflation` | 1.5 | 实体首场表现分膨胀 |
| `f_full` | 1200.0 | f(n) 满额（n=1 时的扣减值） |

### 2.2 APerf（进场先验）

```
APerf = Σ Perf_i·0.9^i·(w_i/100) / Σ 0.9^i·(w_i/100)     i=1 为最新
```

无历史 → Center。

**历史归属**：组队赛以**队伍**为参赛实体，APerf = **队伍自身历史队 Perf** 加权平均（非队员个人均值）；换员即新队（member_key 约定），先验重置 Center，个人历史跨队累计。solo/oi 以个人为实体。

### 2.3 Perf（由名次反解）

第 r 名（n 实体参赛，各带 APerf_j）的表现分 X 是下式唯一解（二分搜索）：

```
Σ_{j=1..n} 1 / (1 + 6^((X − APerf_j)/400)) = r − 0.5
```

- 并列名次取平均（并列 3–6 名都按 4.5）
- 首场（实体无历史）`Perf = (Perf − Center)×1.5 + Center`
- 不设封顶（AtCoder RATEDBOUND 防顶级选手低级赛刷分，学校规模无此问题）
- 打星队参与方程、先验记 Center、**不入任何历史**

### 2.4 Rating（个人展示）

```
Rating = g⁻¹( Σ g(Perf_i)·0.9^i·(w_i/100) / Σ 0.9^i·(w_i/100) ) − f(n)

g(X) = 2^(X/800)
f(n) = (F(n)−F(∞))/(F(1)−F(∞))×1200
F(n) = sqrt(Σ0.81^i)/Σ0.9^i
```

- g 空间平均 = **赢大分、输小分**
- f(1)=1200 收敛到 0——恒定打出 X 从 X−1200 起步，约 10 场收敛
- **同队三人同分**：队 Perf 全额记入每名队员个人历史
- **负分照实显示**

### 2.5 周期榜语义

- **生涯榜**：全史重放
- **赛年/赛季榜**：从周期起点以**全 Center 重放**窗口内事件（「这个赛年若从零开始」）

## 3. 触发时机：运行时按需算

- 不预生成文件；榜单页每次筛选组合（mode × period）实时计算
- 当前规模（校内选手、数十场比赛）全量重算为毫秒级，无需增量缓存

## 4. 榜单模式与时间维度

| 模式 | `mode` | 数据源 |
|------|--------|--------|
| 全部数据 | `all` | `counts_for_ranking=True` 的统一比赛（+ 将来 oj_*） |

| 维度 | `period_type` | 定义 |
|------|---------------|------|
| 生涯 | `career` | 首次参赛至今全部记录 |
| 赛年 | `competition_year` | 当年 9/1 至次年 8/31（`2025赛年`） |
| 赛季 | `season` | 秋学期（9–1 月）/ 寒假（2 月）/ 春学期（3–6 月）/ 暑假（7–8 月） |

`PeriodFilter` 的 type+id 在模型层自动解析为 start/end（`utils/calendar.resolve_period_dates`；显式传入日期优先，无法解析则不过滤），引擎过滤、board meta、缓存 key 全部随之生效；周期下拉选项由 `board_api.available_periods()` 按数据覆盖范围生成。手输 URL 的非法周期值回落为不过滤。

## 5. 榜单输出（BoardSnapshot）

```python
BoardSnapshot(
    meta=BoardMeta(mode, period_type, period_id, period_label, start, end,
                   algorithm="atcoder_v1", data_version, tie_break, generated_at),
    rows=[BoardRow(rank, player_id, name, grade_label, rating, event_count, delta_recent)],
)
```

- **排名规则**：rating 降序；同分按 player_id 字典序（稳定可复现）；竞赛排名 1, 2, 2, 4（同分同 rank、下一名跳号）
- ⚠️ AtCoder 语义下同队同分常态化——**前端必须保留核心 rank，不得按行序重新编号**
- `rating`：该选手重放序列最后一场的 rating_after
- `delta_recent`：最近一场的 Rating 变化（首场相对 0 起点计）
- 离队（`left`）选手不出现在榜单；退役（`retired`）保留；`grade=0` 显示「未设置」
- 生成时间等 meta 展示在榜单页脚（含 data_version，供确认数据新鲜度）

**选手历史**：`rating.api.player_event_history(player_id, mode=, session=)` 返回 `PlayerEventRecord` 列表——按 (date, event_id) 升序的逐场记录（比赛、名次/解题、奖项）+ 逐场 `rating_delta`（首场相对 0）与 `rating_after`，与榜单同一套重放语义。

## 6. 缓存与失效

`xcpc_core/board/api.py`：

- 缓存 key：`(mode, period_key, data_version)`，进程内 dict，上限 256 条（满即全清）
- `data_version` 存于 `meta` 单行表；`board()` 每次调用先读 meta——**写路径已统一接入自动 bump**：
  - `xcpc_core/db/meta.py` 提供 `bump_data_version(session)`：只 flush 不 commit，随调用方事务原子提交/回滚
  - player service（create/update/delete）与 contest service（save/delete）在业务写前调用；importer 确认、一步式导入、补队、CLI 经 service 自动覆盖
- `board.invalidate()` 保留为手动兜底（外部工具直改库后调用）
- **注入 `session` 的调用（测试）不走缓存**

## 7. 权重试算（`/admin/rating`）

三条硬约束：

1. **不落库** —— 试算只读事件流，不改任何表
2. **不进缓存** —— 直接调 `BoardService.build()`，绕开 `board.api.board()` 的进程内缓存
3. **应用才生效** —— 「应用」才写 `data/config/rating_params.yaml` + bump `data_version` + 审计 `weights.apply`

服务在 `rating/lab.py`：`preview(params)` 用「已应用参数」和「草稿参数」各构一次榜，
逐人返回 `rank_base/rank_draft/rating_base/rating_draft/delta`，外加
`summary{players, rank_changed, max_abs_delta, mean_abs_delta, params_changed}`。

**只覆盖 Rating 轨**。积分系数是逐场与 tier 维度，走 `/admin/tiers` 的 CRUD。

## 8. OJ 归一化（未实现）

`platform_factor` 方案随 OJ 数据源立项决定。

---

# 第二轨：生涯积分

**`points` 模块**（`xcpc_core/points/`）：认证工作流 + 双账本 + 积分榜。
语义是**只累加的贡献分**——衡量投入与积累，不衡量「谁更强」。

## 9. 积分公式

```
formula:     R = 100 × (value / max_value) × ((n_teams − rank + 1) / n_teams) × 系数
award_only:  R = awardlevel.base_points × 系数
```

- 无 GP30 项、无参赛保底分；资格线 = `value ≥ 1`
- **系数 = tier.coefficient**（赛事等级），审核通过时随流水快照——**改配置不溯及**

## 10. 工作流

```
管理员配置场次（entity、scoring、max_value、n_teams、双开关）
  → 选手在 /points 提交认证（formula 填 value/rank；award_only 选奖项）
  → 管理员在 /admin/points 审核
  → 通过：同事务写双 owner 流水 + auditlog（points.approve / points.reject）
```

- **驳回后可重提**：部分唯一索引带 `status != 'rejected'` 谓词，同一场次同一 owner 只允许一条非 rejected 记录
- **改配置不溯及**：流水带参数快照（`payload_json`），后续改比赛配置不影响已记分
- **免认证直录**：系统内已有权威成绩时，管理员可批量直录（见 [比赛与导入](比赛与导入) §5）

## 11. 双账本与队伍复合分

审核通过时：

| 场次 entity | 写入的流水 |
|-------------|-----------|
| `player` | 1 条 `player` 流水（`team_context` 空） |
| `team` | 1 条 `team` 流水 + **每名现役成员 1 条 `player` 流水**（`team_context` = 该队） |

**队伍积分榜复合分**：

```
composite = 0.6 × 团队积分 + 0.4 × Σ(成员个人积分 − team_context=本队的流水)
```

排除规则防双计：成员「队外积分」= 成员全部个人流水 − 由本队比赛产生的流水。
成员取当前 roster（`teammember`），队名取最新别名。

**个人榜**：个人流水直加，离队（`left`）选手不出榜。

## 12. 不设场次上限

积分制**不设「赛年最好 N 场」之类的上限**（决定记录见下）。

理由：积分制度量的是**投入度**，多参赛本身就是水平与意愿的体现，用场次上限压制它会与设计意图冲突。榜单保持「全部流水直加」。

> 历史备注：曾实现过「赛年最好 N 场」择优上限，随后整体移除（保留两套聚合路径与「这参数能不能用」的长期疑问不划算）。Git 历史可查回该实现。