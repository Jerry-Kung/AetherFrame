# 创作模块构图规划优化 · 改动归档

**归档日期:** 2026-07-03
**分支:** `dev`
**提交范围:** `7450124..43adc20`(13 个 commit,不含用户手工合入的 1 个辅助文件 commit)
**关联文档:**
- 设计规范: [`docs/superpowers/specs/2026-06-30-creation-composition-planning-design.md`](../specs/2026-06-30-creation-composition-planning-design.md)
- 实施计划: [`docs/superpowers/plans/2026-07-02-creation-composition-planning.md`](../plans/2026-07-02-creation-composition-planning.md)

---

## 1. 背景与动机

实测发现二次元居家美图创作在细节层面已经很到位(服饰、布景、光影),但顶层构图存在两个系统性问题:

1. **图片长宽比与内容适配度不佳** — 长宽比在任务启动前用户手动指定,创作流程中不可变。角色处于居中坐姿时用 16:9 就会让两侧被大面积背景挤占,角色占比过低,发布到外部平台后小图预览缺乏吸引力。
2. **姿势/镜头视角千篇一律** — 现有多样性机制效果有限,LLM 依据概率最大化始终倾向于侧卧、抱膝坐等少数姿势,镜头视角雷同。批次预览视觉上几乎每张只换了角色和背景装饰。

根因:工作流缺少专门的「构图规划」模块,把构图决策全部交给 Prompt 生成阶段的 LLM 自由发挥。

## 2. 解决方案概览

**双臂并进**:
- **尺寸臂(S1)**: 引入 `auto` 长宽比选项,让 LLM 在 step1 阶段根据场景内容决策每张图的 `aspect_ratio` 与主体占比下限,per-card 值贯穿到图片生成 API,实现真正的尺寸闭环。
- **多样性臂(S2/S3/S4/S5)**: 从种子提示词阶段起,把 `pose_family` / `shooting_angle` / `camera_height` / `gaze_direction` 转为结构化枚举决策(而非自由生成),Prompt 装配层现场渲染枚举集,review 阶段以维度差异作 tie-breaker。

**支撑基础**:
- **S0**: 给创意方向加 `home_settings` 字段(1–3 个居家背景锚点),供后续 seed prompt 的「背景联动」使用。
- **S1-1**: 新建 `composition_dimensions.py` 作为所有构图维度的唯一枚举源,禁止 Prompt 模板硬编码枚举自然语言。

## 3. 硬约束

以下约束贯穿整个实施,任何切片、任何 commit 都必须遵守:

1. **腿脚可见性第一硬约束**: 任何构图/机位/姿态组合都不得遮挡或裁掉角色腿部/脚部(袜子)。枚举设计已滤除会违反此约束的取值。
2. **反 fetish 边界**: 严禁 fetish 倾向的镜头语言(脚部特写/袜子特写/袜口装饰特写/纯下半身镜头)进入枚举。腿脚描述以自然居家状态为基调。
3. **LLM 能力上限适配**: 不设计复杂腿脚动作枚举;用「机位组合多样性」代替「姿势细节多样性」。
4. **枚举中央化**: 所有构图维度枚举值集中在 `app/services/creation_service/composition_dimensions.py`,通过 `get_dimension_values(dim: str)` 读取。Prompt 模板不得硬编码枚举自然语言。
5. **schema 变动限制**: 本轮唯一允许的 DB 变动是给 `material_creative_directions` 加 `home_settings TEXT` 列。
6. **预留装配点**: 学习机制的写入路径、权重 UI、参考图上传本轮不实现,只留空字符串占位符供未来注入。

## 4. 切片架构

| 切片 | 目标 | 关键改动 | Commit |
|---|---|---|---|
| **S0-1** | DB 迁移 + 模型加列 | `material_creative_directions.home_settings TEXT` | `e038833` |
| **S0-2** | 创意方向 Prompt 输出 home_settings | `creative_direction_prompt` 增字段, `_parse_direction_json` 3 元组 | `ba401be` |
| **S1-1** | 新建构图维度枚举模块 | `composition_dimensions.py` 承载 6 维度枚举 + 软指引表 | `951f5df` |
| **S1-2** | step1 决策 + 尺寸闭环 | `_build_step1_prompt` / `_parse_step1_composition`, cards `composition`, quick_create per-card 出图 | `143a0c9` |
| **S1-3** | 前端 auto 长宽比 | 3 个 UI 入口下拉框加 Auto | `598c721` |
| **S2-1** | seed prompt 多样性硬约束 | 姿态家族均衡 / 腿脚描述 / 背景联动 / 分布偏好占位 | `a26c89e` |
| **S3-1** | step1 机位方位 + 机位高度 | shooting_angle × camera_height 决策 + 模板硬回填位 | `09d9322` |
| **S3 fix** | 引号 + 反 fetish 移除 | Prompt 引号 U+201C/U+201D 规范化 | `7248298` |
| **S4-1** | step1 视线维度 | gaze_direction 决策 + 模板硬回填位 | `a0e89d5` |
| **S5-1** | review 反同质化评分 | 维度差异分 + 权重表预留 | `199ecda` |
| **Z-1 fix** | 批量自动化 auto 支持 | `batch_automation_service._VALID_ASPECT` 补 auto | `c78b60c` |
| **Final fix** | 双花括号 + 并发丢 composition | `composition_output` 单花括号规范 + chain 传 composition | `43adc20` |

## 5. 文件变更清单

### 新增文件(4)

- `app/services/creation_service/composition_dimensions.py` — 构图维度枚举中央源
- `tests/services/test_composition_dimensions.py` — 枚举模块单测(11 条)
- `tests/services/test_creative_direction_home_settings.py` — home_settings 集成 + parser 单测(4 条)
- `tests/services/test_prompt_precreation_composition_persistence.py` — step1 决策与解析单测(12 条,含 S1-2/S3-1/S4-1)
- `tests/services/test_seed_prompt_composition_prompt.py` — seed prompt 姿态家族与背景联动单测(7 条)
- `tests/services/test_prompt_review_composition.py` — review 差异分单测(4 条)

### 修改的模型 / 迁移(2)

- `app/models/material.py` — `MaterialCreativeDirection` 加 `home_settings = Column(Text, nullable=True)`
- `app/models/database.py` — `migrate_material_creative_directions_add_home_settings()` + 挂入 `init_db()`

### 修改的 Prompt 模板(3)

- `app/prompts/material/creative_direction.py` — `creative_direction_prompt` 加 home_settings 字段说明;`creation_direction_seed_prompt` 结构重组(新增「创作规范」块,精简「注意事项」,加分布偏好预留)
- `app/prompts/creation/prompt_precreation.py` — `prompt_step1` 加任务步骤 0 占位符 + 镜头组合分布偏好预留 + Negative Prompt 风险标签预留;`prompt_step2` / `prompt_review` / `prompt_review_backup` 顶部 4 处硬编码 16:9 改为"由 step1 决策";`prompt_review` 加维度差异分 + 权重表预留
- `app/prompts/creation/prompt_template.py` — `init_template` 里 `**16:9**` → `**{aspect_ratio}**`;构图硬约束加主体占比条;镜头与构图段顶部加 3 行硬回填位;`good_template1` 同步补 3 行示例值

### 修改的服务层(4)

- `app/services/creation_service/prompt_precreation_service.py` — 新增 `_render_dimension_list` / `_build_step1_prompt` / `_parse_step1_composition` / `_STEP0_CAMERA_TEMPLATE` / `_REVIEW_DIVERSITY_CRITERIA` / `_build_review_prompt`;`_ENUM_CODES` 承载 5 维度校验;`_collect_candidates` 返回 (candidates, compositions) 2-tuple;`_build_cards` 写入 card `composition`;`_try_chain_quick_create` 在 selected 里保留 composition;`_run_review.call_main` 走 `_build_review_prompt`。
- `app/services/creation_service/quick_create_service.py` — `VALID_ASPECT_RATIOS` 加 `"auto"`;`_resolve_selected_prompts` 拓宽返回类型至 `List[Dict[str, Any]]` 并透传 composition;出图循环按 per-card `composition.aspect_ratio` 决定 `effective_ar`,兜底 `"16:9"`。
- `app/services/creation_service/batch_automation_service.py` — `_VALID_ASPECT` 加 `"auto"`(Z-1 手工 E2E 发现的缺口)。
- `app/services/material_service/seed_prompt_generation_service.py` — 新增 `_render_pose_family_enum` / `_render_home_setting_hints` / `_fold_home_settings_into_direction_text` / `_build_seed_prompt` + `_SEED_HOME_SETTINGS_FALLBACK` 常量;`_resolve_direction_text` 返回 3-tuple(含 home_list);`run_seed_prompt_task` 用 `_build_seed_prompt` 装配。
- `app/services/material_service/creative_direction_generation_service.py` — `_parse_direction_json` 返回 3-tuple;`run_creative_direction_task` 持久化 `home_settings`;`_write_direction_json_file` 落盘含 `home_settings` 键。

### 修改的 Schema(2)

- `app/schemas/creation.py` — 3 处 `aspect_ratio: Literal[...]` 加 `"auto"`;`PromptCardItem` 加 `composition: Optional[Dict[str, str]] = None`。
- `app/schemas/material.py` — `CreativeDirectionResponse` 加 `home_settings: Optional[List[str]]` + `field_validator` 把 DB JSON 字符串转回 list。

### 修改的前端(5)

- `page/src/services/creationApi.ts` — 3 处 aspect_ratio Literal 拓宽至含 `"auto"`。
- `page/src/pages/creation/components/QuickCreatePage.tsx` — `ASPECT_RATIO_OPTIONS` 首位加 Auto。
- `page/src/pages/creation/components/PromptGenPage.tsx` — `CHAIN_ASPECT_OPTIONS` 首位加 auto;`clampPromptAspect` 兜底保留 `"1:1"` 不变。
- `page/src/pages/home/components/BatchCreationPage.tsx` — 允许集与类型 union 加 auto。
- `page/src/pages/home/components/BatchConfigModal.tsx` — 批量创作可见下拉首位加 Auto。

## 6. 核心机制:构图维度枚举中央化

**动机**: spec §7 明确要求 Prompt 模板不得硬编码枚举自然语言。所有装配层通过统一接口读取,新增/删除/改名枚举值只需改一个文件,不需改 Prompt 与节点拓扑。

**位置**: `app/services/creation_service/composition_dimensions.py`

**导出接口**:
- `DimensionValue`(dataclass,frozen):`code / display_name / description`
- `get_dimension_values(dim: str) -> List[DimensionValue]` — 8 个 dim_code:`aspect_ratio_manual` / `aspect_ratio_auto_full` / `aspect_ratio_auto_mainstream` / `subject_area_min` / `pose_family` / `shooting_angle` / `camera_height` / `gaze_direction`
- `get_home_setting_pose_hints() -> List[Tuple[str, List[str]]]` — 5 条 home_setting → pose_family 软指引
- `VALID_MANUAL_ASPECT_CODES` / `VALID_AUTO_ASPECT_CODES` — frozenset 常量

**枚举清单**:

| 维度 | code 数 | 承载切片 |
|---|---|---|
| aspect_ratio_manual | 5(16:9, 4:3, 1:1, 3:4, 9:16) | S1 手动比例 |
| aspect_ratio_auto_full | 9(主流 5 + 特殊 4) | S1 auto 决策 |
| aspect_ratio_auto_mainstream | 5(= manual) | S1 auto 优先主流 |
| subject_area_min | 4(0.45 / 0.55 / 0.65 / 0.75) | S1 主体占比下限 |
| pose_family | 6(坐 / 躺 / 跪 / 蹲 / 倚 / 盘腿) | S2 seed prompt 均衡 |
| shooting_angle | 5(正 / 3/4 正 / 侧 / 3/4 背 / 背回眸) | S3 机位方位 |
| camera_height | 4(略仰 / 平视 / 略俯 / 大俯) | S3 机位高度 |
| gaze_direction | 5(看镜头 / 3/4 出画 / 侧看 / 下方 / 远处) | S4 视线 |

## 7. 关键数据流

### 尺寸闭环(S1)

```
用户前端选 aspect_ratio="auto"
   ↓
POST /api/creation/prompt-precreation/start (aspect_ratio="auto")
   ↓
_collect_candidates 循环 N 次:
   step1 Prompt 含 9 长宽比档 + 4 主体占比档枚举 + [COMPOSITION_DECISION] 块要求
   ↓
   LLM 输出:模板顶部 [COMPOSITION_DECISION] 决策块 + 已回填 {aspect_ratio} 与 {subject_area_min_pct} 的模板正文
   ↓
   _parse_step1_composition 解析决策块,校验枚举范围,写入 compositions[key]
   ↓
   _build_cards 把每张 card 的 composition 段挂上(含 aspect_ratio / subject_area_min / shooting_angle / camera_height / gaze_direction)
   ↓
POST /api/creation/quick-create/start (aspect_ratio="auto")
   ↓
run_quick_create_task_sync 出图循环:
   effective_ar = "auto" → 从 item.composition.aspect_ratio 取(缺则回落 "16:9")
   ↓
generate_image_with_nano_banana_pro(aspect_ratio=effective_ar)
```

### 多样性架构(S2/S3/S4/S5)

```
S2: seed prompt 阶段
   creation_direction_seed_prompt 含「创作规范」块:
   - 姿态家族均衡:≥4 类家族,任一 ≤3 条
   - 腿脚摆放描述简洁性 + 反 fetish 基调
   - 背景联动:每条种子选一个 home_setting,参考软指引表
   - {pose_family_distribution_bias} 空占位(未来学习机制注入)
   ↓
S3: step1 阶段
   任务步骤 0-cam 强制 LLM 决策 shooting_angle × camera_height
   写入 [COMPOSITION_DECISION] 块,持久化到 card.composition
   {camera_combo_distribution_bias} 空占位
   ↓
S4: step1 阶段
   任务步骤 0-cam 扩至 3 维度,追加 gaze_direction
   模板顶部 3 行硬回填位 [SHOOTING_ANGLE] / [CAMERA_HEIGHT] / [GAZE_DIRECTION]
   ↓
S5: review 阶段
   维度差异分作为质量相近候选的 tie-breaker
   {composition_weight_table} 空占位(未来加权重)
```

## 8. 反 fetish 处理

**Spec 原始设计**: S3-1 落地 back_glance 与「上半身回头」的强绑定互斥规则,防止背面视角演变为纯臀腿构图。

**实际决策**: 用户在 S3-1 落地时决定移除该规则 — 认为单条互斥不够系统,后续将新增独立的反 fetish 模块统一承载。

**当前状态**:
- back_glance 枚举保留(在 `_SHOOTING_ANGLE` 中),description 已含「角色上半身回头朝向镜头、视线接触观者」的天然描述。
- S3-1 的 `_STEP0_CAMERA_TEMPLATE` 里没有互斥规则文案。
- S2 的 seed prompt「创作规范」块保留「腿脚摆放描述基调」,以自然居家状态为基调,不带暗示性或刻意聚焦 — 这是 fetish 层面的第一道语义闸门。

**后续**: 若观察到 back_glance 输出偏向问题,可考虑独立反 fetish 模块(Negative Prompt 增强、gaze/pose 二级校验或 review 阶段增强)。

## 9. 预留装配点

以下段落本轮以空字符串占位符渲染,后续学习机制可直接注入:

| 占位符 | 位置 | 用途 |
|---|---|---|
| `{pose_family_distribution_bias}` | seed prompt「特别要求」之前 | 姿态家族分布偏好(基于历史数据) |
| `{camera_combo_distribution_bias}` | step1 任务步骤 0-cam 之后 | 镜头组合分布偏好 |
| `{negative_prompt_risk_tags}` | step1 「模版填写说明」第 3 条之后 | Negative Prompt 高风险标签(基于历史失败案例) |
| `{composition_weight_table}` | prompt_review 差异分块之后 | 维度权重表(基于人工投票或质量反馈) |
| `{home_settings_fallback_note}` | seed prompt「创作规范」段 | 无 home_settings 时的兜底说明(non-empty 时空字符串) |

## 10. 测试覆盖

**新增测试**: 44 条(11 + 4 + 12 + 7 + 4 + 6 = 44)
- `test_composition_dimensions.py`: 11 条
- `test_creative_direction_home_settings.py`: 4 条
- `test_prompt_precreation_composition_persistence.py`: 12 条
- `test_seed_prompt_composition_prompt.py`: 7 条
- `test_prompt_review_composition.py`: 4 条
- 装配层与解析器纯函数覆盖

**回归**: 全量 pytest `377 passed / 12 skipped / 243 warnings in ~58s`(warnings 均为 SQLAlchemy 2.0 deprecation 与 pre-existing 项目告警,非本轮引入)。

**前端**: `npm run type-check` PASS;`npm run build` PASS(1.34s,`app/static/` 产物已刷新);`npm run lint` 11 pre-existing warnings,零新增。

## 11. Known Issues / Follow-ups

以下 Minor 项在本轮实施中被记录,未阻塞合并,可作为后续独立任务处理:

1. **`_COMPOSITION_LINE_RE` key 字符类为 `[a-z_]+`** — LLM 幻觉输出 `Aspect_ratio` 会被静默丢弃,不 warn。可考虑 `re.IGNORECASE`。
2. **quick_create auto 兜底路径无 warn** — 若 card 缺 composition 时静默回落 `"16:9"`,生产环境定位困难。可加 `logger.warning`。
3. **home_settings 端到端写入路径无 pytest** — 目前只有 parser 单测,无 DB roundtrip + 落盘 JSON 的完整测试。
4. **反 fetish 独立模块** — 用户决策的后续独立工作,目前只有 spec §5「反 fetish 基调」在 seed prompt 层生效。
5. **`_REVIEW_DIVERSITY_CRITERIA` 未来 escape 风险** — 若未来在此常量增加 `{...}` 会与 `.format()` 冲突,可改 Template 或显式转义。
6. **良好模板 `good_template1` 里 `**16:9**` 是完整示例值** — 若 LLM 从示例中偷懒复制 16:9,理论上有回归可能。E2E 时值得抽样。

## 12. 提交清单

```
7450124  docs(creation): 构图规划实施计划 + pre-flight 三处决策 inline
e038833  feat(S0): 为 material_creative_directions 增加 home_settings 列
ba401be  feat(S0): 创意方向 Prompt 增 home_settings 输出并持久化
951f5df  feat(S1): 新建构图维度枚举集中管理模块
143a0c9  feat(S1): step1 决策 auto 长宽比+主体占比并打通尺寸闭环
598c721  feat(S1): 前端长宽比选项加 auto 档
a26c89e  feat(S2): seed prompt 加姿态家族均衡+背景联动+分布偏好占位
09d9322  feat(S3): step1 引入机位方位+高度维度决策
7248298  fix(S3): 修复 Prompt 引号偏差 + 移除反 fetish 互斥规则
a0e89d5  feat(S4): step1 补齐视线维度决策与结构化持久化
199ecda  feat(S5): prompt_review 增维度差异分与权重表预留段
929418f  手动合入内容项 (用户手工:辅助文件,非切片改动)
c78b60c  fix(S1): 批量自动化 aspect_ratio 校验加 auto 档
43adc20  fix(review): 修复 final review 两处 Important findings
```
