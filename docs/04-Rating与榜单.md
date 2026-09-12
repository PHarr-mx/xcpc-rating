# Rating 与榜单

> 定位：**参考 + 待建**。关联：[03-比赛与导入](03-比赛与导入.md) · [05-Web与认证](05-Web与认证.md) · [08-路线图](08-路线图.md)

- **rating 模块**（`xcpc_core/rating/`）：把统一事件流按 `source_type` 分发到计算器，算出选手得分
- **board 模块**（`xcpc_core/board/`）：把得分聚合成榜单快照（只读，缓存）

> 实现状态：**架构骨架已落地，公式仍是 placeholder_v0（占位）**——榜单数值当前无业务含义，
> 正式公式是四期的核心工作（先业务定案，见 [08-路线图](08-路线图.md)）。

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

## 2. 现行公式：placeholder_v0（占位，非最终规则）

| 计算器 | 公式 |
|--------|------|
| Formal | `max(0, (total_teams - rank + 1) / total_teams * 1000 + solved * 50)` |
| Training 组队 | `max(0, (team_count - rank + 1) / team_count * 800 + solved * 30) / size` |
| Training 个人 | `max(0, (player_count - rank + 1) / player_count * 800 + solved * 30)` |
| Training OI | `max(0, (player_count - rank + 1) / player_count * 800 + score * 2)` |
| OJ 比赛 | `max(0, delta)` |
| OJ 做题 | `rating_numeric * 0.5 + solve_count * 2` |

**聚合语义**：`rating = round(sum(各事件得分))`——名次百分位 × 权重的线性累加。

**当前公式的已知局限**（公式定案时要解决的）：

- 无对手实力建模、无期望胜率、无 K 因子（非 Elo 类）
- 无初始分与收敛机制，事件可无限累加不封顶
- 无时间衰减（生涯榜对远古比赛同等计权）
- 队内分摊为均分（`/size`）

## 3. 未来算法方向（四期业务定案清单）

| 方向 | 说明 | 决策状态 |
|------|------|----------|
| 加权 Elo | 正式赛权重高、训练赛/OJ 低；按时间序迭代更新 | ⬜ 待定 |
| 队内分摊 | 按队员贡献比例分配（目前均分） | ⬜ 待定（训练赛前置） |
| OJ 归一化 | 不同平台 Rating 映射统一尺度（platform_factor） | ⬜ 待定 |
| 时间衰减 | 生涯榜对远古比赛降权 | ⬜ 待定 |
| 置信度展示 | 参赛场次过少时标注 | ⬜ 待定 |

定案产出：写进本文档 §2 的公式规格 + `meta.rating_algorithm` 版本号升级。

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

> **实现现状**：引擎过滤只按 `PeriodFilter.start/end` 生效；Web 端 `BoardState` 目前传
> `type/id` 未换算成 start/end，赛年/赛季筛选**实际不改变结果集**（标签生效、过滤未接线）。
> 这是四期接线项（`utils/calendar.py` 已具备换算所需的基础）。

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

见 [08-路线图](08-路线图.md) §4「待定决策」：正式公式、队内分摊、OJ 归一化、置信度、
赛年/赛季过滤接线、分项榜（当前仅总分榜，无历史快照存档）。

---

*docs/ v2 重构（2026-09-11）：合并原 06-Rating计算模块、07-榜单模块；数据导出（05，可选）的榜单文件矩阵方案已随 Reflex 运行时计算废弃。*
