# 生产 Feedback 标签化（点选标签 + 等级）— 设计文档

日期：2026-07-09
状态：已批准（用户确认七节设计 + 标签体系三处修订）
背景：生产验证阶段用户逐图打字填 feedback 费时费力。将首页灵感产线的图片
feedback 从「纯文本 + 腿脚崩坏勾选」升级为「标签点选为主、自由文本为辅」。
前作：`docs/superpowers/specs/2026-07-08-production-feedback-entry-design.md`
（本设计在其数据模型 / API / 导出之上增量演化，原有能力全部保留）。

## 需求（用户已确认）

1. 页面提供**可点选的反馈标签**，分三类：正面（如「袜子样式好看」）、
   负面（如「袜子皱褶过于夸张」）、中立（如「正常」），**可多选**。
2. **负面标签统一带问题等级**：轻微 / 中等 / 严重，逐标签选择。
3. 标签词表为**独立配置**（不直接复用 taxonomy.yaml），负面标签各自记录到
   实验 taxonomy 的映射；UI 标签可自由增删措辞，不受 taxonomy 治理约束。
4. **保留自由文本框**作为可选补充（发现新问题模式的唯一通道）。
5. Case 的 `bad` 计数**由标签自动推导 + 兜底勾选**：选中任一「计入腿脚崩坏」
   的标签即计 bad；仅填文本时可单独勾「腿脚崩坏」兜底。
6. 导出 schema 升 **aetherframe_feedback_v2**，兼容 v1 历史归档。
7. 标签管理方式：**配置文件 + API 下发**（改配置文件重启生效，不做管理 UI）。
8. 选中标签存储：**现有表加 JSON 列**（方案 A）。

## 1. 标签配置文件

新增 `app/config/feedback_tags.yaml`（随代码提交，非 gitignore）。结构：

```yaml
version: 1
tags:
  - key: sock_wrinkle_heavy          # 稳定英文标识，存库/导出用，永不改含义
    label: 袜子皱褶过于夸张           # UI 中文名，可自由改措辞
    polarity: negative               # positive | negative | neutral
    leg_foot_bad: true               # 仅 negative 有意义：选中即计 bad
    taxonomy: 袜子/皱褶夸张           # 仅 negative：映射实验 taxonomy（父类/子类）
```

- `key` 一旦启用不得复用为其他含义（历史数据靠 key 追溯）；改 `label` 措辞、
  改 `taxonomy` 映射、增删标签都只改配置文件，重启生效。
- 正面/中立标签无 `leg_foot_bad`、无 `taxonomy` 字段。

### 首版词表（已批准）

**负面·腿脚类（`leg_foot_bad: true`，均带等级）：**

| key | label | taxonomy |
|---|---|---|
| `foot_crude` | 脚部简陋 | 脚部/简陋 |
| `foot_exaggerated` | 脚部细节夸张 | 脚部/夸张 |
| `foot_proportion` | 脚部比例结构异常 | 脚部/比例结构 |
| `foot_tip_discolor` | 脚尖变色 | 脚部/脚尖变色 |
| `leg_multi_missing` | 多肢/缺肢 | 腿部/结构错误 |
| `leg_twist` | 腿部异常扭曲（含脚尖反向） | 腿部/结构错误 |
| `pose_weird` | 姿势诡异（不符合人类正常姿势） | 其他/未分类 |
| `leg_proportion` | 腿部比例失调（过粗/过细） | 身体比例/整体不协调 |
| `sock_painted` | 袜子上色感 | 袜子/上色感 |
| `sock_toe_separation` | 脚趾分离感 | 袜子/上色感 |
| `sock_plastic` | 袜子塑料袋感 | 袜子/塑料袋感 |
| `sock_wrinkle_heavy` | 袜子皱褶过于夸张 | 袜子/皱褶夸张 |
| `sock_missing` | 袜子缺失 | 袜子/缺失 |
| `sock_shoes` | 错误穿鞋 | 袜子/穿鞋 |

**负面·非腿脚类（`leg_foot_bad: false`，带等级）：**

| key | label | taxonomy |
|---|---|---|
| `style_realistic` | 画风写实化 | 画风/写实化 |
| `style_flat2d` | 画风平面2D | 画风/平面2D |
| `style_doll3d` | 3D玩偶感 | 画风/3D玩偶感 |
| `body_proportion` | 身体比例不协调 | 身体比例/整体不协调 |
| `face_collapse` | 脸部细节崩坏 | 其他/未分类 |
| `face_anchor_lost` | 视觉锚点丢失 | 其他/未分类 |
| `face_expression` | 表情诡异 | 其他/未分类 |

**正面（无等级、无映射）：** `pos_sock_style` 袜子样式好看、
`pos_leg_natural` 腿脚自然、`pos_overall_good` 整体效果好。
**中立：** `neutral_normal` 正常。

设计说明（已批准的两个决策）：

- **腿部标签重整**：原 taxonomy 单条「腿部/结构错误」在 UI 层拆为
  多肢/缺肢 与 异常扭曲 两个标签（生产数据证实是两类不同崩坏），
  归档聚合暂共用同一 taxonomy tag；`pose_weird` 与三个脸部标签暂映射
  其他/未分类，taxonomy v3 落地后只改配置映射，不动代码。
- **脚趾分离感独立成标签**：与「袜子上色感」并存、映射同一 taxonomy tag
  （袜子/上色感）。上色感 = 整只袜子像皮肤上色；脚趾分离感 = 脚趾根根分明
  如五指袜，是前者最典型症状但不等同。feedback 层双 key 保留精确语义，
  将来频次高再在 taxonomy v3 单列子 tag。

## 2. 数据模型与迁移

`creation_image_feedbacks` 表新增列：

```
selected_tags_json TEXT NOT NULL DEFAULT '[]'
```

- 内容为 JSON 数组：负面标签 `{"key": "...", "severity": "minor|moderate|severe"}`；
  正面/中立标签 `{"key": "..."}`（无 severity 字段）。
- 新增 `migrate_creation_image_feedbacks_add_selected_tags()`，沿用现有
  「检查列存在 → ALTER TABLE」模式（`app/models/database.py`）。
- **清空即删语义扩展**：文本空 且 未勾兜底 且 无选中标签 → 删行。
- 一行 = 一张图的 feedback 语义不变；upsert / 删除联动全部照旧。

## 3. API（`/api/creation` 前缀，ApiResponse 包装）

### 3.1 标签配置下发（新增）

`GET /feedback/tags`

- 返回 `{ "version": 1, "tags": [ {key, label, polarity, leg_foot_bad} ] }`
  （taxonomy 映射不下发，前端用不到）。
- 配置文件缺失/解析失败 → 返回 `tags: []` + 日志告警；前端拿到空列表时
  退化为纯文本模式（等于现状，不阻断反馈）。
- 前端启动后拉一次，模块级缓存。

### 3.2 保存（扩展现有接口）

`PUT /quick-create/tasks/{task_id}/feedback/{prompt_id}/{image_index}`

- body 增加 `selected_tags: [{key, severity?}]`（默认 `[]`，向后兼容）。
- 后端校验：未知 key **剔除并告警**（不报错，防配置改名后旧前端缓存卡死）；
  负面标签缺 severity 按 `moderate` 兜底；正面/中立标签忽略传入的 severity。
- **`leg_foot_bad` 落库值由后端统一推导**：
  `(任一选中负面标签的 leg_foot_bad=true) OR body.leg_foot_bad`。
  前端勾选框只传兜底位。
- 清空即删按 §2 扩展后的三条件判断。

### 3.3 回显（扩展现有接口）

`GET /batch-automation/items-hydrated` 的 feedbacks 每项增加
`selected_tags`（与存储同构的对象数组）。

## 4. 前端 UI（ImageFeedbackModal 改版）

弹窗从上到下：

1. **标签区**（三组胶囊按钮，标签来自 §3.1 API）：
   - 问题标签（负面，玫瑰红系）、亮点标签（正面，绿系）、中立（灰系）；
   - 负面标签**点击循环四态**：未选 → 轻微 → 中等 → 严重 → 取消选中；
     选中时胶囊尾部显示「·轻 / ·中 / ·重」，底色随等级加深；
   - 正面/中立标签为普通开关（点选/取消），可多选；
   - 标签列表为空（API 退化）时整个标签区隐藏。
2. **自由文本框**：缩到 2 行，placeholder 改为
   「标签覆盖不了的新问题写这里…」。
3. **兜底勾选「腿脚崩坏」**：当选中标签已隐含 bad 时自动勾上并置灰，
   旁注「已由标签推导」；否则可手动勾选（覆盖仅填文本的场景）。

保存按钮逻辑不变（保存中禁用、失败弹窗内报错不丢输入）。
标签配置挂全局一次性加载（模块级缓存，`creationApi` 新增 `getFeedbackTags`）。
类型 `QuickCreateImage.userFeedback` 增加 `selectedTags` 字段。

## 5. 导出 v2 与归档口径

### 5.1 导出

- schema 值升为 `aetherframe_feedback_v2`，结构在 v1 基础上：
  - 每张图增加 `selected_tags`（`[{key, severity?}]`）与
    `selected_tag_labels`（如 `["袜子皱褶过于夸张（严重）"]`，方便人读）；
  - 顶层新增 `tag_config` 快照：导出时刻的完整标签配置
    （含 taxonomy 映射与 leg_foot_bad），**导出文件自包含**，
    归档不依赖仓库配置文件的当前状态。
- 存量行（改版前保存的 feedback）`selected_tags` 为空数组，其余字段照旧。

### 5.2 归档口径（对 2026-07-08 spec §4 的增补）

- Case `tags`：优先由 `selected_tags` 按导出内 `tag_config` 快照的
  taxonomy 映射直接生成（负面标签→tag，去重）；自由文本仍由 Claude
  人工判读，补充映射外的 tag。
- `feed_back` 行格式：`图{N}: [标签中文名（等级）、顿号连接]｜{自由文本}`；
  无标签只有文本、或只有标签无文本时省略对应段——**等级随原文进 Case
  永久保留**。
- `bad` 计数继续用 `leg_foot_bad`（布尔口径不变；severity 是归档后
  分析的附加信号，不参与 bad 判定）。
- v1 历史归档（`production_cases.txt` 现有 25 Case）不受影响、不回改。

## 6. 错误处理

- 保存：task 不存在 404；`image_index < 0` 422；未知 tag key 剔除不报错；
  其余 500 走 ApiResponse 统一错误。
- 标签配置：文件缺失/解析失败降级空列表（前端退化纯文本模式），
  启动与请求时日志告警。
- 导出：沿用 v1 的坏数据跳过策略；`tag_config` 装配失败时输出空快照
  并告警，不阻断导出。

## 7. 测试

- 后端 pytest（沿用 `tests/` 现有模式）：
  - 迁移：新列存在、幂等重跑；
  - 保存：未知 key 剔除、负面缺 severity 补 moderate、正面/中立忽略
    severity、`leg_foot_bad` 推导（纯标签 / 纯勾选 / 混合 / 非腿脚负面
    标签不计 bad）、清空即删三条件（含「只剩标签也算已填」）；
  - 回显：items-hydrated 带 `selected_tags`；
  - 导出：schema=v2、`selected_tags`/`selected_tag_labels` 透传、
    `tag_config` 快照、存量行空数组；
  - 标签 API：正常下发、配置缺失退化空列表。
- 前端：`npm run type-check` + `npm run lint` 通过（项目无前端测试设施，
  不新增）。

## 8. 明确不做（YAGNI）

- 不做标签管理 UI（改配置文件重启生效）；
- 不做标签排序/分组自定义、使用频次统计；
- 不做旧 feedback 数据的文本→标签回填迁移（历史已归档，生产库旧行保持原样）;
- 不做逐标签的图内区域标注；
- 不改盲评页（三组三档评分是盲评专用，两套入口不合并）；
- 不做 taxonomy v3（脸部父类等映射调整届时只改配置文件）。
