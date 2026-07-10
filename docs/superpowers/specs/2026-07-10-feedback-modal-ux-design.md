# Feedback 弹窗体验优化（分组 + 等级一次点选 + 去勾选框）— 设计文档

日期：2026-07-10
状态：已批准（用户确认整体设计；等级交互选定「常显分段式」、存量数据选定「一次性迁移重算」）
背景：2026-07-09 标签化改版（`docs/superpowers/specs/2026-07-09-feedback-tag-selection-design.md`）
上线后，生产实用中暴露三个体验问题：负面标签无分类难查找、选「严重」需连点三次、
「腿脚崩坏」勾选框冗余。本设计在其之上增量演化，数据模型 / 导出 schema 不变。

## 需求（用户已确认）

1. **负面标签分类分组**展示，便于查找。分组方式由 Claude 整理决定。
2. **严重程度一次点选**：任意等级（含「严重」）都必须一次点击选中，
   替换现有「未选→轻→中→重→取消」四态循环。
3. **移除「腿脚崩坏」勾选框**：bad 完全由标签推导；库里存量行的
   `leg_foot_bad` 一次性迁移重算为标签推导值。
4. 允许适当**增大弹窗尺寸**，保证页面结构美观。

## 1. 标签分组（配置驱动）

`app/config/feedback_tags.yaml` 每个标签新增 `group` 字段：

```yaml
- { key: sock_wrinkle_heavy, label: 袜子皱褶过于夸张, polarity: negative,
    leg_foot_bad: true, taxonomy: 袜子/皱褶夸张, group: 袜子 }
```

- `group` 是**纯 UI 分组名**，与 `taxonomy`（实验归档映射）相互独立；
  改分组＝改配置文件重启生效，不动代码。
- `GET /api/creation/feedback/tags` 下发的每个 tag 增加 `group` 字段
  （正面/中立无 group，下发 `null`，前端不使用）。
- 前端按 group 分组渲染负面标签：**组间顺序 = 该组首个标签在配置文件中的
  出现顺序；组内顺序 = 配置文件顺序**。负面标签缺 `group` 时归入「其他」组
  （排最后）。
- 导出 `tag_config` 快照为配置 deepcopy，自然带上 `group`（纯增量，
  归档口径不受影响）。

### 首版分组（负面 21 标签 → 5 组）

| group | 标签（按配置顺序） |
|---|---|
| 袜子（6） | sock_painted 上色感、sock_toe_separation 脚趾分离感、sock_plastic 塑料袋感、sock_wrinkle_heavy 皱褶过于夸张、sock_missing 袜子缺失、sock_shoes 错误穿鞋 |
| 脚部（4） | foot_crude 简陋、foot_exaggerated 细节夸张、foot_proportion 比例结构异常、foot_tip_discolor 脚尖变色 |
| 腿部与姿势（4） | leg_multi_missing 多肢/缺肢、leg_twist 异常扭曲、pose_weird 姿势诡异、leg_proportion 比例失调 |
| 画风（3） | style_realistic 写实化、style_flat2d 平面2D、style_doll3d 3D玩偶感 |
| 脸部与身体（4） | face_collapse 脸部细节崩坏、face_anchor_lost 视觉锚点丢失、face_expression 表情诡异、body_proportion 身体比例不协调 |

配置文件中负面标签按上表分组重新排序（袜子组排最前——生产最高频）。
正面（3 个）、中立（1 个）数量少不分组，维持现有单行展示。
`key` / `taxonomy` / `leg_foot_bad` 全部不变（key 永不改含义的约束照旧）。

## 2. 严重程度：常显分段式

负面胶囊结构改为「标签名 │轻│中│重」：

- **点等级段**：一次点击选中该档；再点当前已选档 = 取消选中。
- **点标签名**：未选中时按「中等」快捷选中；已选中时取消
  （保留一个大点击区，兼顾最常用档位）。
- **视觉**：未选中时等级段用极淡灰色弱化（避免 21 个胶囊都带鲜艳分段的
  视觉噪音）；选中后整个胶囊底色沿用现有三档玫瑰红
  （minor 0.25 / moderate 0.45 / severe 0.75 透明度），当前档段高亮。
- 正面/中立标签维持现有开关点选，样式不变。
- `SEVERITY_CYCLE` 四态循环逻辑删除。

## 3. 移除「腿脚崩坏」勾选框，bad 纯标签推导

### 3.1 前端

- 勾选框（含「已由标签推导」旁注）整体删除，`manualBad` 状态及相关
  useEffect 归零逻辑一并移除。
- 选中标签推导出 bad 时，标签区下方显示一行小字提示：
  「已判定：腿脚崩坏（由标签自动推导）」；未推导出 bad 时该行隐藏。
- `onSave` 回调签名去掉 `legFootBad` 参数；保存请求体不再携带
  `leg_foot_bad`（schema 默认 False，后端忽略该值）。
- `QuickCreateImage.userFeedback.legFootBad` 类型字段保留
  （回显后端合并值，卡片角标等展示可能用到），仅弹窗不再写它。

### 3.2 后端

- `save_feedback` 的落库 bad 改为**纯推导**：
  `leg_foot_bad = any(选中负面标签的 leg_foot_bad=true)`。
  请求体 `leg_foot_bad` 字段在 schema 中保留但**忽略其值**
  （防旧页面缓存 422，注释标注 deprecated）。
- `derive_leg_foot_bad(normalized, checkbox, config)` 的 checkbox 参数
  删除，签名改为 `derive_leg_foot_bad(normalized, config)`。
- **清空即删**从三条件简化为两条件：文本空 且 无选中标签 → 删行
  （bad 是推导值，无标签必为 False，不再单独判断）。

### 3.3 存量数据一次性迁移

新增数据迁移 `migrate_creation_image_feedbacks_recompute_leg_foot_bad()`
（`app/models/database.py`，在 init_db 现有迁移列表末尾调用）：

- **一次性标记**：复用现有 `app_migrations` 元表守卫
  （`_is_migration_applied` / `_mark_migration_applied`，
  bio walk 一次性数据迁移的同款模式）。与「查列存在」的结构迁移不同，
  这是数据迁移，必须只跑一次——否则将来改配置里的 `leg_foot_bad`
  标志会在每次重启时重写历史数据。
- **重算**：逐行按当前标签配置重算
  `leg_foot_bad = any(selected_tags_json 里负面标签的 leg_foot_bad=true)`；
  `selected_tags_json` 解析失败按空数组处理。
- **清理**：重算后满足「文本空 且 无标签」的行直接删除
  （对齐新的清空即删语义；07-08 时代「仅手动勾选无文本」的行属此类）。
- 标签配置加载失败（空配置）时**跳过迁移且不置标记**，日志告警,
  下次启动重试——防止在配置缺失的窗口把所有 bad 清零。
- 影响说明（用户已确认接受）：07-08 批次纯文本行的手动 bad 在库里清零；
  其 25 个 Case 已永久归档进 `production_cases.txt`（永不回改），
  且归档流程按 Case ID 去重会跳过旧记录，实际无损。

### 3.4 导出

结构不变（仍 `aetherframe_feedback_v2`）：`leg_foot_bad` 照旧输出，
迁移后库值即推导值，全库口径单一。

## 4. 弹窗尺寸与布局

- 宽度 `w-[30rem]` → `w-[52rem]`，保留 `max-w-[calc(100vw-2rem)]`
  与 `max-h-[calc(100vh-4rem)] overflow-y-auto` 小屏兜底。
- 单列结构不变，从上到下：头部（缩略图＋标题）→ 问题标签区
  （5 个分组，各带小标题）→ 亮点/中立一行 → bad 推导提示行 →
  自由文本（2 行）→ 取消/保存按钮。
- 风格延续现有玫瑰粉圆角体系（ZCOOL KuaiLe 字体、rose 色系、圆角胶囊）。

## 5. 错误处理

- 标签配置缺失/解析失败：API 照旧降级空列表，前端标签区整体隐藏，
  退化为纯文本模式；此时保存的 bad 推导值为 False（无标签可推导），
  提示行不显示。迁移在此状态下跳过（见 §3.3）。
- 保存错误路径不变（404 / 422 / 500，弹窗内报错不丢输入）。

## 6. 测试

- 后端 pytest：
  - 推导：请求体 `leg_foot_bad=true` 被忽略（无 bad 标签时落库 False）；
    选中 bad 标签落库 True；非腿脚负面标签不计 bad。
  - 清空即删两条件：有文本无标签→保留；无文本有标签→保留；
    双空→删行（不再受请求体 bad 位影响）。
  - 迁移：有标签行重算为推导值；纯文本手动 bad 行→False 且保留；
    「无文本无标签」行被删除；app_migrations 置标记后重跑不再动数据；
    空配置时跳过且不置标记。
  - 标签 API：下发字段含 `group`。
- 前端：`npm run type-check` + `npm run lint` 无新增告警。

## 7. 明确不做（YAGNI）

- 不做标签搜索/筛选、分组折叠、使用频次统计；
- 不做等级的键盘快捷键；
- 不改盲评页；
- 不升导出 schema v3（本次全部为增量字段与库内口径统一）；
- 不做迁移的回滚工具（迁移前用户可自行备份 `data/db/aetherframe.db`，
  且已归档 Case 不依赖库值）。
