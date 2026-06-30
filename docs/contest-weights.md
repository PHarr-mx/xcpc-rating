# 比赛权重配置

> **状态**：✅ 已实现  
> **配置文件**：`data/config/contest_weights.yaml`  
> **代码路径**：`backend/data/import/weights.py`

---

## 1. 总则

- **基准权重为 100**，表示「标准强度」的一场比赛对 Rating 的贡献
- **允许极少数比赛权重 > 100**（如特别重要的决赛）；需在 raw 中显式写 `weight_override`，并注明原因
- 默认权重由配置文件查表；**不在 raw 里逐场手写**（特殊场次除外）
- Rating 算分时：事件得分 × `weight / 100`

---

## 2. 校内训练赛：按 `division` 查权重

与 `format`（`team_xcpc` / `solo_xcpc` / `oi`）**无关**，只看难度档：

| `division` | 名称 | 权重 |
|------------|------|------|
| `div1+2` | 全体队员组 | **100** |
| `div1` | 老队员组 | **95** |
| `div2` | 新队员组 | **70** |
| `div3` | 未入队新生组 | **60** |

---

## 3. 正式比赛：按 `contest_type` 查权重

| `contest_type` | 名称 | 权重 |
|----------------|------|------|
| `icpc_regional` | ICPC 区域赛 | **100** |
| `ccpc_national` | CCPC 国赛 | **100** |
| `icpc_online` | ICPC 网络赛 | **90** |
| `ccpc_online` | CCPC 网络赛 | **90** |
| `astar_national` | 百度之星国赛 | **90** |
| `icpc_invitational` | ICPC 邀请赛 | **80** |
| `ccpc_invitational` | CCPC 邀请赛 | **80** |
| `lanqiao_national` | 蓝桥杯国赛 | **80** |
| `gplt_national` | GPLT 国赛 | **80** |
| `raicom_national` | RAICOM 国赛 | **75** |
| `icpc_provincial` | ICPC 省赛 | **70** |
| `ccpc_provincial` | CCPC 省赛 | **70** |
| `astar_provincial` | 百度之星省赛 | **70** |
| `lanqiao_provincial` | 蓝桥杯省赛 | **70** |
| `raicom_provincial` | RAICOM 省赛 | **65** |
| `icpc_team_school` | ICPC 组队校赛 | **60** |
| `icpc_school` | ICPC 校赛（个人） | **50** |

---

## 4. OJ 权重（参考，算法待定）

| 类型 | 默认权重 |
|------|----------|
| OJ 比赛（Rated） | **40** |
| OJ 做题（Practice） | **20** |

---

## 5. 权重解析流程

```
读取 raw 比赛文件
    │
    ├─ 校内训练赛
    │     → weight = training_divisions[division]
    │
    └─ 正式比赛
          → weight = formal_types[contest_type]
          → 若存在 weight_override → 使用覆盖值（可 > 100）

写入 processed 的 weight 字段，weight_source = "config" | "override"
```

---

## 6. 权重 > 100 的例外

极少数场次可手动覆盖（在 import 参数中指定）：

```python
FormalImportParams(
    ...
    weight_override=110,
    weight_override_reason="本届国赛计入双积分周期",
)
```

---

## 7. 修改权重

1. 编辑 `data/config/contest_weights.yaml`
2. 重新运行 `import` + `rating` + `export`
3. `meta.json` 记录 `weight_config_version`

不影响 raw 历史文件；processed 重算即可。