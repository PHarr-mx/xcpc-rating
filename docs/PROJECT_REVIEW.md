# xcpc-rating 项目整体 Review

> **Review 日期**：2026-06-30  
> **Review 范围**：全仓库（代码、数据、文档、架构设计）  
> **当前分支**：main  
> **最新提交**：72e1d51 init repo

---

## 1. 项目概览

**xcpc-rating** 是一个校内 XCPC 编程竞赛队的 Rating 统计与展示系统。核心目标：汇总正式赛、校内训练赛、OJ 平台三类数据，计算选手 Rating，以静态网站形式展示排行榜。

**技术栈**：Python 3.13（数据管道）+ Vue 3 + Vite（前端，未实现）+ Caddy（静态托管，未部署）

**当前阶段**：MVP 早期。数据管道（`backend/data/`）已部分实现，前端和站点构建模块尚未动工。

---

## 2. 架构评估

### 2.1 整体架构：静态站 + 离线管道 ✅

```
外部数据源 → backend/data/（fetch → process → export） → data/public/（JSON）
                                                              ↓
浏览器 ← Caddy ← index.html + assets/ ← frontend/（Vue 3 build）
```

**优点**：
- 架构清晰，职责分离明确。`backend/data`（数据）、`backend/site`（站点构建）、`frontend`（前端）三个模块边界清晰，可独立开发、测试、部署。
- 离线计算 + 静态托管：运行时无需 Python/Node/数据库，Caddy 直接 serve 静态文件，运维成本极低。
- 数据分层（raw → processed → public）设计合理，可复现、可追溯、可回滚。

**关注点**：
- 数据管道目前只有"导入"阶段实现了部分（formal xlsx），process/export/rating 三个阶段均未实现，是整个项目的关键路径。

### 2.2 目录结构

```
xcpc-rating/
├── backend/data/       ← Python 数据管道（已实现约 30%）
├── backend/site/       ← 站点构建脚本（未实现）
├── frontend/           ← Vue 3 前端（未创建）
├── data/               ← 数据文件（raw/processed/public）
├── docs/               ← 设计文档（较完整）
├── skill/              ← AI Agent Skills（formal-import, player-manage）
└── requirements.txt    ← Python 依赖
```

**评价**：整体目录结构符合 DESIGN.md 规划，但实际代码与设计文档的包结构存在偏差（见 3.3 节）。

---

## 3. 实现现状

### 3.1 已完成模块

| 模块 | 完成度 | 说明 |
|------|--------|------|
| **Player CRUD** | ✅ 100% | 完整 API + CLI + 持久化 + 测试 |
| **Formal Import (xlsx)** | ✅ 90% | 解析、匹配、导入、手动追加均可工作 |
| **Award 计算** | ✅ 100% | 奖牌线推算 + 百分位兜底 |
| **权重配置** | ✅ 100% | YAML 配置文件 + 加载逻辑 |
| **结构化日志** | ✅ 100% | Plog：终端彩色 + JSONL 文件双写 |
| **AI Skills** | ✅ 100% | formal-import / player-manage 两份 SKILL.md |

### 3.2 未完成模块

| 模块 | 状态 | 优先级 |
|------|------|--------|
| Training import | 未实现 | 高 |
| OJ import | 未实现 | 中 |
| Process pipeline | 未实现（仅有 processed/ 样例数据） | 高 |
| Rating engine | 未实现（设计文档有 placeholder 方案） | 高 |
| Export pipeline | 未实现 | 高 |
| `xcpc-data` CLI | 未实现 | 中 |
| `backend/site/` | 未创建 | 低 |
| `frontend/` | 未创建 | 中 |
| JSON Schema | 未创建 | 低 |
| `pyproject.toml` | 已删除 | 中 |

### 3.3 代码组织与设计文档的偏差

设计文档（`docs/design/04-数据导入与加工模块.md`、`docs/design/05-数据导出与发布模块.md`）规划的包结构：

```
backend/data/src/xcpc_data/
├── cli.py
├── import/{players, teams, formal, training, oj}.py
├── processors/{normalize, calendar, unmatched}.py
├── rating/{engine, placeholder}.py
├── export/{meta, ratings, players, catalogs}.py
└── models/
```

实际代码结构：

```
backend/data/
├── import/      ← 包名 "importer"（非 "xcpc_data.import"）
├── player/      ← 包名 "player"（非 "xcpc_data.import.players"）
├── tests/       ← 测试分散在 player 和 import 各自目录下
└── utils/       ← Plog 等工具
```

**偏差**：
- 实际使用的是平铺式 import（`from importer.xxx`、`from player.xxx`），而非设计文档中的 `xcpc_data.xxx` 命名空间包。这是通过 `PYTHONPATH` 兼容的临时方案。
- 缺少顶层 `src/xcpc_data/` 包裹，缺少 `pyproject.toml` 做正式的包管理。
- 这个偏差在 MVP 阶段可以接受，但应在正式化前统一。

---

## 4. 代码质量评估

### 4.1 整体评价：良好

代码风格一致，类型标注完整，docstring 简洁有效，错误处理到位。

### 4.2 亮点

**Pydantic 模型设计**（`backend/data/import/models.py`）：
- 输入/输出模型定义清晰，`FormalImportParams`、`FormalImportResult`、`AddFormalTeamParams` 等职责分明。
- 使用 `Literal` 类型约束枚举值，`Field()` 约束校验规则。
- `model_dump(mode="json")` 序列化规范。

**Player Service 层**（`backend/data/player/service.py`）：
- 清晰的 Service → Store 分层，业务逻辑与持久化解耦。
- 唯一性校验（handle、OJ 账号）在 service 层完成而非 store 层，职责正确。
- `find_by_name` 支持别名匹配，`find_by_oj` 支持跨平台查找，功能完备。

**Formal Import 流程**（`backend/data/import/formal.py`）：
- `import_formal_xcpcio_xlsx()` 一站式导入，参数通过 Pydantic 模型传入。
- `add_formal_team()` 手动追加打星队伍，支持同队替换（upsert）。
- Team ID 基于成员集合的 SHA-256 哈希，保证了"同队同 ID"的正确语义。
- 日志记录完整（plog），便于调试和审计。

**Award 计算**（`backend/data/import/awards.py`）：
- 优先使用正式奖牌数据（取 weakest medal winner），无奖牌数据时回退到百分位。逻辑严谨。

**测试**：
- 14 个测试函数，覆盖 xlsx 解析、award 计算、import 流程、add_team、player CRUD、Plog。
- 使用 `tmp_path` fixture 隔离文件系统，不污染仓库。
- 测试了 `auto_create_players=True/False` 两条路径。

### 4.3 可改进之处

**1. `PlayerStore` 每次操作都全量读写 JSON**

`service.py` 中 `list_players`、`get_player`、`find_by_name` 等每次调用都执行 `self.store.load_all()`，对于 20+ 人的规模没问题，但若扩展到数百人，建议加一层内存缓存或换 SQLite。

**2. `service.py` 中 `list_players` 的过滤在内存中线性扫描**

```python
def list_players(self, *, include_left=True, status=None, grade=None):
    players = self.store.load_all()
    if not include_left:
        players = [p for p in players if p.status != PlayerStatus.left]
    # ...
```

每次过滤都创建新列表，数据量小时无妨，但可以一次性遍历过滤。

**3. 缺少 `PlayerService` 的批量导入接口**

`import/players.py` 中的 `resolve_member_names` 直接操作 `PlayerStore`，绕过了 `PlayerService` 的唯一性校验逻辑。建议统一通过 Service 层操作。

**4. `formal_store.py` 的路径处理**

`raw_contest_path` 和 `raw_contest_rel_path` 对 `formal_` 前缀做了 strip 处理，这个隐含约定在代码中没有注释说明。

**5. 测试中的硬编码数据**

`test_xcpcio_xlsx.py` 依赖仓库根目录下的特定 xlsx 文件（`第十八届四川省大学生程序设计竞赛 - 正式赛.xlsx`），如果文件被移动或删除，测试会 skip。建议将测试数据放入 `tests/fixtures/` 目录。

**6. 缺少集成测试**

当前测试都是单元测试 + 文件 I/O 测试。缺少端到端的"xlsx → raw → 验证"的完整流程测试。

---

## 5. 数据评估

### 5.1 当前数据

| 数据文件 | 内容 | 状态 |
|----------|------|------|
| `data/raw/players/roster.json` | 24 名选手 | 所有 grade=0（未设置），oj_accounts 均为空 |
| `data/raw/formal/2026_sichuan_provincial.json` | 1 场正式赛（312 队，8 支本校队） | 完整 |
| `data/processed/contests_formal.json` | 1 条记录 | 与 raw 数据一致 |
| `data/processed/players.json` | 21 名 active 选手 | 由 raw 衍生 |
| `data/processed/standings_formal.json` | 7 条记录 | 与 raw 一致 |

**注意**：`data/processed/` 在 `.gitignore` 中，但当前仓库中仍有该目录。根据设计，`processed/` 应由 pipeline 生成，不应手动维护。

### 5.2 数据质量问题

- **选手 grade 全部为 0**（未设置）：这是 `data/config/school.yaml` 中 `player_defaults.grade: 0` 导致的，需要在 roster 中手动补全或通过 import 流程设置。
- **OJ 账号全部为空**：OJ 数据导入尚未实现，选手的 OJ 账号需要手动录入。
- **已删除的 raw 文件**：git status 显示 `data/raw/formal/` 下删除了 5 个 JSON 文件，`data/raw/training/` 下删除了 4 个 JSON 文件。这些可能是早期测试数据，但删除后导致历史数据丢失。

---

## 6. 文档评估

### 6.1 文档完整度：优秀

| 文档 | 质量 | 说明 |
|------|------|------|
| `docs/DESIGN.md` | ⭐⭐⭐⭐⭐ | 工程架构设计完整，数据流、部署、开发工作流均有覆盖 |
| `docs/design/01-07` | ⭐⭐⭐⭐⭐ | 7 份模块设计文档，业务逻辑详尽 |
| `docs/backend-player-module.md` | ⭐⭐⭐⭐⭐ | API 文档与实现完全一致 |
| `docs/backend-formal-import-xcpcio.md` | ⭐⭐⭐⭐⭐ | 导入流程文档清晰 |
| `skill/formal-import/SKILL.md` | ⭐⭐⭐⭐⭐ | AI Agent 操作手册，步骤清晰 |
| `skill/player-manage/SKILL.md` | ⭐⭐⭐⭐⭐ | AI Agent 操作手册，含常见场景 |
| `README.md` | ⭐⭐⭐ | 基础信息齐全，但缺少快速开始示例 |
| `data/README.md` | ⭐⭐⭐ | 描述了 raw 目录结构，但部分内容已过时 |

### 6.2 文档与实现的一致性

- `docs/backend-player-module.md` 与 `backend/data/player/` 实现一致 ✅
- `docs/backend-formal-import-xcpcio.md` 与 `backend/data/import/` 实现一致 ✅
- `docs/DESIGN.md` 中的包结构 `xcpc_data` 与实际 `importer`/`player` 不一致 ⚠️
- `data/raw/README.md` 中描述的训练赛文件格式与实际已删除的文件结构吻合，但当前无实际文件可验证 ⚠️

---

## 7. 关键风险与建议

### 7.1 风险

| 风险 | 严重程度 | 说明 |
|------|----------|------|
| **Rating 算法未定** | 🔴 高 | 这是系统的核心价值。placeholder_v0 是简单加权求和，不能反映真实水平。但设计已将算法解耦为插件接口，阻碍不大。 |
| **数据管道未完成** | 🔴 高 | import 之外的 process/export/rating 均未实现，当前无法产出 `data/public/`。 |
| **前端未启动** | 🟡 中 | 没有前端就无法展示。但数据管道是前端的前提，优先级可排后。 |
| **包结构未统一** | 🟡 中 | 当前 `importer`/`player` 平铺在 `backend/data/` 下，与设计文档不一致。需要在正式化前迁移到 `xcpc_data` 命名空间。 |
| **选手数据不完整** | 🟡 中 | 所有选手 grade=0，OJ 账号为空，影响 Rating 计算和展示。 |
| **历史数据丢失** | 🟡 中 | git status 显示多场 formal/training raw 文件被删除，如果是刻意清理则无妨，但需确认。 |

### 7.2 建议优先级

**P0（阻塞 MVP）**：
1. 实现 `data/processed/` 的 process 阶段（将 raw 转换为规范化表）
2. 实现 placeholder rating engine（只要能跑通流程即可）
3. 实现 `data/public/` 的 export 阶段
4. 实现 `xcpc-data update` CLI 入口

**P1（完善数据管道）**：
5. 统一包结构为 `xcpc_data`，添加 `pyproject.toml`
6. 实现 training import（解析训练赛 JSON）
7. 补全选手数据（grade、OJ 账号）
8. 搭建 `frontend/` 基础框架（Vue 3 + Vite + 路由）

**P2（体验优化）**：
9. 添加 `data/schemas/` JSON Schema 校验
10. 实现 OJ 数据导入
11. 实现 `backend/site/` 构建部署脚本
12. Caddy 部署配置
13. CI/CD（GitHub Actions 自动测试 + 定时构建）

---

## 8. 模块详解

### 8.1 Player 模块（`backend/data/player/`）

**架构**：API → Service → Store → JSON 文件

```
player/api.py          ← 公开编程接口（所有外部调用入口）
player/cli.py          ← xcpc-player 命令行
player/service.py      ← 业务逻辑（CRUD、查询、校验）
player/store.py        ← JSON 文件读写
player/models.py       ← Pydantic 数据模型
player/exceptions.py   ← 异常层次结构
```

**评价**：层次清晰，职责分明。Service 层的唯一性校验（handle、OJ 账号跨选手不重复）实现正确。Store 层使用 `find_repo_root()` 定位仓库根目录，避免硬编码路径。

**CLI 设计**：
```bash
xcpc-player list [--status active|retired|left] [--grade 2023] [--json]
xcpc-player get <id> [--json]
xcpc-player find --name <name> [--json]
xcpc-player find --oj <platform> <handle> [--json]
xcpc-player create --name <name> [--grade <year>] [--oj <platform:handle>]
xcpc-player update <id> [--name <name>] [--grade <year>]
xcpc-player delete <id>
xcpc-player mark-left <id>
```

### 8.2 Formal Import 模块（`backend/data/import/`）

**数据流**：

```
xlsx 文件
  → xcpcio_xlsx.py（openpyxl 解析，过滤本校组织）
  → awards.py（计算奖牌线）
  → formal.py（匹配选手、生成 team_id、写 raw JSON）
  → players.py（resolve 选手名 → 查 roster 或自动创建）
  → weights.py（查 contest_weights.yaml）
  → formal_store.py（读写 raw/formal/ 目录）
```

**关键设计决策**：
- Team ID = `t_` + SHA-256(sorted(player_ids))[:8]：基于成员集合的哈希，同一组人无论队名如何变化，ID 不变。
- 选手名册 auto-create：导入时遇到新名字自动创建选手（`pXXX` 格式 ID），减少手动维护。
- `add_formal_team`：手动追加打星队（非本校挂靠但需要追踪的队），支持同 team_id 替换。
- 奖牌线计算优先使用 xlsx 中的正式奖牌数据（取各等级最弱获奖者的成绩），无数据时回退到 10%/20%/30% 百分位。

### 8.3 权重配置（`data/config/contest_weights.yaml`）

设计合理，覆盖了所有比赛类型：
- 训练赛：按 Division 分级（Div1+2=100, Div1=95, Div2=70, Div3=60）
- 正式赛：按比赛类型分级（ICPC/CCPC 区域赛=100，省赛=70，校赛=50-60）
- 个人赛：百度之星、蓝桥杯、GPLT、RAICOM 均有对应权重
- OJ：预留了 contest/practice 默认权重
- 支持 `weight_override` 突破 100 上限（特殊比赛）

---

## 9. 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|----------|--------|----------|
| `import/tests/test_xcpcio_xlsx.py` | 4 | xlsx 解析、过滤、auto-create、无 auto-create |
| `import/tests/test_awards.py` | 5 | 奖牌线、百分位、分配逻辑 |
| `import/tests/test_add_formal_team.py` | 4 | 手动追加、替换、校验 |
| `tests/test_player_crud.py` | 6 | CRUD、过滤、唯一性校验、持久化 |
| `tests/test_player_api.py` | 3 | API 层代理、隔离 |
| `utils/tests/test_plog.py` | 2 | 日志写入、路径 |

**总计**：约 24 个测试函数。覆盖了核心路径，但缺少：
- 训练赛导入测试（模块未实现）
- Process / Export 测试（模块未实现）
- 端到端集成测试

---

## 10. 总结

**项目健康度**：⭐⭐⭐⭐（4/5）

**优势**：
- 架构设计清晰、文档完善，为后续开发提供了良好的蓝图
- 已实现部分代码质量高，类型标注完整，错误处理到位
- 测试覆盖核心路径，Pydantic 模型提供类型安全
- AI Skills 设计规范，便于 AI 辅助开发

**待改进**：
- 关键路径（process/export/rating）尚未实现，是当前最大瓶颈
- 包结构需统一为设计文档中的 `xcpc_data` 命名空间
- 选手数据需要补全（grade、OJ 账号）
- 缺少 `pyproject.toml` 做正式的包管理

**下一步建议**：集中精力实现 process → rating → export 数据管道，打通从 raw 到 public 的完整链路，这是 MVP 的核心前提。

---

*Review 由 Claude Code 完成，基于仓库 `main` 分支 `72e1d51` 的完整代码审查。*