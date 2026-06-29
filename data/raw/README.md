# raw 原始数据

人工投放的原始输入。格式见 [03-比赛与记录模块](../../docs/design/03-比赛与记录模块.md)；权重见 [07-比赛权重](../../docs/design/07-比赛权重.md)。

## 校内训练 `training/`

根字段：`format`（`team_xcpc` / `solo_xcpc` / `oi`）、`division`（`div1` / `div2` / `div1+2` / `div3`）。  
**不必写 `weight`**，import 时按 division 查 `data/config/contest_weights.yaml`。

| 文件 | division | 权重 |
|------|----------|------|
| `2026_w12_team_xcpc_div1+2.json` | div1+2 | 100 |
| `2026_w10_team_xcpc_div1.json` | div1 | 95 |
| `2026_w05_solo_xcpc_div2.json` | div2 | 70 |
| `2026_w08_oi_div3.json` | div3 | 60 |

## 正式比赛 `formal/`

根字段：`contest_type`（见权重文档枚举）、`format`、`total_teams`。

| 文件 | contest_type | 权重 |
|------|--------------|------|
| `2025_icpc_hefei_regional.json` | icpc_regional | 100 |
| `2026_ccpc_national_final.json` | ccpc_national | 110（override 示例） |
| `2025_autumn_invitational.json` | icpc_invitational | 80 |
| `2026_ccpc_hunan_provincial.json` | ccpc_provincial | 70 |
| `2026_spring_invitational.json` | icpc_team_school | 60 |

## 选手名册 `players/`

见 `roster.json`。字段：`handle`（校内简称）、`status`（`active` / `retired` / `left`）。  
样例：`陈七` 为 `retired`，`周八` 为 `left`（站点导出时过滤）。
