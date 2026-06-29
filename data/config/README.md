# config

Rating 与比赛相关的**可配置常量**，纳入 Git。

| 文件 | 说明 |
|------|------|
| [contest_weights.yaml](contest_weights.yaml) | 校内赛 division 权重、正式赛 contest_type 权重 |

`backend/data` 在 import 时读取本目录；修改后需重新跑数据流水线。  
设计说明见 [docs/design/07-比赛权重.md](../docs/design/07-比赛权重.md)。

本地覆盖路径（不提交）：`backend/data/config.yaml` 可指向其他权重文件。
