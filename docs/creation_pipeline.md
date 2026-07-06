# 二次元居家美图创作业务流程

> 版本快照:2026-07-03 之后(构图规划优化落地后的当前版本)
> 覆盖范围:从「创意方向」到最终图片落盘的完整业务流

## 0. 全景视图

```
┌────────────────────────────────────────────────────────────────────┐
│                       角色基础资料准备                              │
│  chara_profile_final.md + 标准参考图 5 张                           │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  节点 1 · 创意方向  (Material 模块)                                 │
│  Prompt: app/prompts/material/creative_direction.py                │
│    creative_direction_prompt                                        │
│  Service: creative_direction_generation_service.run_creative_...    │
│  产物: MaterialCreativeDirection { title, description,              │
│                                    home_settings: List[str] }      │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  节点 2 · 种子提示词  (Material 模块)                               │
│  Prompt: app/prompts/material/creative_direction.py                │
│    creation_direction_seed_prompt                                   │
│  Service: seed_prompt_generation_service.run_seed_prompt_task       │
│  产物: seed_draft.json { character_specific: [8-10 条种子] }        │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  节点 3 · 预生成 Prompt  (Creation 模块)                            │
│  Prompts: app/prompts/creation/prompt_precreation.py               │
│    prompt_step1  ─►  prompt_step2                                  │
│  Service: prompt_precreation_service.run_prompt_precreation_...     │
│  产物: 2N 份候选 Prompt (candidate_prompt_NNN.txt)                  │
│        + step1 结构化构图决策 (每条候选)                            │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  节点 4 · 最终 Prompt 审核筛选  (Creation 模块)                     │
│  Prompts: app/prompts/creation/prompt_precreation.py               │
│    prompt_review  (兜底 prompt_review_backup)                       │
│  Service: prompt_precreation_service._run_review                    │
│  产物: N 张 PromptCard (best_prompt_files),含 composition 决策段    │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  节点 5 · 一键创作出图  (Creation 模块)                             │
│  Service: quick_create_service.run_quick_create_task_sync           │
│  Tool:   app/tools/llm/nano_banana_pro.generate_image_with_...     │
│  产物: PNG 图片(路径 data/beautify/quick_create/...)                │
└────────────────────────────────────────────────────────────────────┘
```

**触发方式:**
- **手工流**:用户在前端逐节点操作(材料 → 创意方向 → 种子 → 预生成 → 一键创作)。
- **批量流**:首页「批量创作」触发 `BatchAutomationService`,自动串联节点 3 → 4 → 5(链式)。

---

## 1. 前置条件:角色基础资料

在整个业务流启动之前,需要完成角色的基础资料准备,详见 `docs/backend/` 中的对应文档。核心产物:

- `chara_profile_final.md` — 角色完整档案(背景、性格、外观、世界观),供节点 1/2/3/4 作为角色底层参考。
- 5 张标准参考图(全身正/侧、半身正/侧、面部特写)— 供节点 5 出图时锁定角色相貌。

存储位置:`data/material/characters/<character_id>/`。

---

## 2. 节点 1 · 创意方向

**目标:** 为该角色生成一份"居家创作视觉创意主题",指导后续所有创作步骤保持风格一致。

**Prompt 文件:** `app/prompts/material/creative_direction.py`
- **`creative_direction_prompt`** — 输入角色档案 + 用户输入要求 + 发散度 + 历史创意方向列表;输出 JSON 含 `title` / `description`(Markdown 富文本) / `home_settings`(1–3 个居家背景锚点数组,如「卧室大床」「客厅沙发」「日式榻榻米」)。

**为什么加 `home_settings`?**
下游节点 2 的种子提示词需要围绕这些具体的居家背景锚点展开,让 8–10 条种子在几个背景之间均衡分布,避免所有种子都堆在同一场景。

**Service:** `app/services/material_service/creative_direction_generation_service.py`
- `run_creative_direction_task(task_id)` — 后台任务入口
- `_parse_direction_json(raw)` — 返回 `(title, description, home_settings)` 3 元组,对 home_settings 做 trim / dedup / cap-at-3。

**产物:**
- **DB**: `MaterialCreativeDirection` 行(id / title / description / home_settings(JSON 字符串) / divergence / initial_input)
- **文件**: `data/material/characters/<id>/creative_directions/<direction_id>.json`

**Route:** `POST /api/material/characters/{character_id}/creative-directions/start`

---

## 3. 节点 2 · 种子提示词

**目标:** 基于创意方向,生成 8–10 条覆盖多样姿态与背景的种子提示词短句,作为节点 3 预生成的初始输入。

**Prompt 文件:** `app/prompts/material/creative_direction.py`
- **`creation_direction_seed_prompt`** — 结构化为 6 大块:
  1. `**任务背景**` — 角色总监设定
  2. `**输出要求**` — 8–10 条,不含违禁词
  3. `**创作规范**` — 4 条硬约束:
     - **姿态家族均衡**:8–10 条覆盖 ≥4 类姿态家族(坐/躺/跪/蹲/倚/盘腿),任一 ≤3 条
     - **腿脚摆放描述**:1 句自然描述,反 fetish 基调
     - **背景联动**:必须选用 `home_settings` 中的一个背景,配合软指引表选择契合的姿态家族
     - **背景均衡分布**:8–10 条在 1–3 个背景之间均衡分布
  4. `**注意事项**` — 保留特殊警告(简洁凝练、避免夸张表情)
  5. `**参考模版**` — 7 条示例种子(供 LLM 参考风格,不得照搬)
  6. `**分布偏好**` + `**特别要求**` + 输入包(chara_profile / 创意方向 / 历史种子)

**装配层枚举渲染:** `app/services/material_service/seed_prompt_generation_service.py`
- `_render_pose_family_enum()` — 现场渲染 6 姿态家族选项(取自 `composition_dimensions.get_dimension_values("pose_family")`)
- `_render_home_setting_hints()` — 渲染 5 条 home_setting → pose_family 软指引表
- `_fold_home_settings_into_direction_text(title, description, home_settings)` — 把 home_settings 数组折叠进传给 LLM 的方向文本
- `_build_seed_prompt(*, chara_profile, direction_text, history_seed_prompts, has_home_settings)` — 一键装配。`has_home_settings=False` 时自动注入 fallback 说明,让 LLM 自由选择自然的居家背景。

**产物:**
- **文件**: `data/material/characters/<id>/seed_prompt_tasks/<task_id>/seed_draft.json` — 含 `character_specific: [8-10 条种子字符串]`

**Route:** `POST /api/material/characters/{character_id}/seed-prompts/start`(涉及 `creative_direction_id` 参数以指定基于哪个方向)

---

## 4. 节点 3 · 预生成 Prompt

**目标:** 基于一条种子提示词,让 LLM 分两步(step1 → step2)生成 2N 份完整的图片创作 Prompt 候选,供节点 4 挑选最优 N 份。step1 也承担构图维度的结构化决策。

**Prompt 文件:** `app/prompts/creation/prompt_precreation.py`
- **`prompt_step1`** — 核心创作步骤:
  1. `**任务步骤**` 开头有 3 个占位符段:
     - `{step1_task_step_zero}` — 强制 LLM 决策 `aspect_ratio`(9 档) + `subject_area_min`(4 档)
     - `{step1_task_step_zero_camera}` — 强制 LLM 决策 `shooting_angle`(5 档) × `camera_height`(4 档) × `gaze_direction`(5 档)
     - `**镜头组合分布偏好**` + `{camera_combo_distribution_bias}` — 预留,本轮空
  2. 「模版填写说明」6 条中间夹 `{negative_prompt_risk_tags}`(预留,本轮空)
  3. `{step1_composition_output_requirement}` — 要求 LLM 在输出模板正文之前插入 `**[COMPOSITION_DECISION]**` 决策块(5 行,含所有维度 code 值),并在模板正文里回填 `{aspect_ratio}` / `{subject_area_min_pct}` 占位符。
  4. 附上填写目标模板 `init_template` 与参考模板 `good_template1`
- **`prompt_step2`** — 复审并补齐镜头/构图/光影/材质/Negative Prompt 等高级配置项,基于 step1 已填充的字段继续加工。

**填写目标模板:** `app/prompts/creation/prompt_template.py`
- **`init_template`** — 空白模板,含 `{aspect_ratio}` 与 `{subject_area_min_pct}` 待 LLM 回填;`**镜头与构图**` 段顶部有 3 行硬回填位:`[SHOOTING_ANGLE]` / `[CAMERA_HEIGHT]` / `[GAZE_DIRECTION]`
- **`good_template1`** — 高质量示例模板(飘窗坐姿 + 白丝袜的完整范例),供 LLM 参考风格与丰满度

**装配层:** `app/services/creation_service/prompt_precreation_service.py`
- `_build_step1_prompt(*, chara_profile, seed_prompt)` — 装配 step1 完整 Prompt(现场渲染 4 组枚举 + 拼接构图决策块指令)
- `_parse_step1_composition(step1_output)` — 用正则解析 `[COMPOSITION_DECISION]` 决策块,按 `_ENUM_CODES` 校验值域,静默丢弃越界项。返回 `{"aspect_ratio", "subject_area_min", "shooting_angle", "camera_height", "gaze_direction"}` 字典
- `_collect_candidates(...)` — 循环 max(2N, 4N) 次调 step1 + step2,返回 `(candidates, compositions)` 两个字典。目标 2N 条成功候选
- `_render_dimension_list(dim)` — 通用维度枚举渲染工具(读 `composition_dimensions` 模块)

**枚举源模块:** `app/services/creation_service/composition_dimensions.py`
- 集中管理 8 个 dim_code 的枚举取值(见「构图规划优化改动归档」文档 §6)
- 通过 `get_dimension_values(dim_code)` 唯一入口读取,Prompt 模板严禁硬编码

**产物:**
- **DB**: `CreationPromptPrecreation` 行的 `result_json` 字段(cards 数组,每张 card 含 id / title / preview / fullPrompt / composition)
- **文件**: `data/beautify/prompt_precreation/<task_id>/candidate_prompt_NNN.txt`(2N 份 step2 输出的完整 Prompt)

**Route:** `POST /api/creation/characters/{character_id}/prompt-precreation/start`

---

## 5. 节点 4 · 最终 Prompt 审核筛选

**目标:** 从 2N 份候选中挑选出最优 N 份进入节点 5 出图。

**Prompt 文件:** `app/prompts/creation/prompt_precreation.py`
- **`prompt_review`** — 主路径:
  - `**维度差异分（始终生效）**` + `{composition_diversity_criteria}` — 质量相近时以 `shooting_angle` / `camera_height` / `gaze_direction` / `pose_family` 4 维度组合差异作为 tie-breaker,保证批次内多样性
  - `**维度权重表**` + `{composition_weight_table}` — 预留,本轮空占位("由后续学习机制注入")
  - 输入:2N 份候选 JSON 数组 + 用户原始输入 + 角色档案 + `num_best_prompts=N`
  - 输出:JSON `{ review_result: <评价>, best_prompt_files: [...] }`
- **`prompt_review_backup`** — 兜底路径:
  - 与主路径同 IO 契约,但**不含**差异分与权重表段(简化以最大化 JSON 格式稳定性)
  - 主路径 2 次失败后自动降级到兜底路径

**装配层:** `app/services/creation_service/prompt_precreation_service.py`
- `_REVIEW_DIVERSITY_CRITERIA` — 常量文本(4 维度差异分策略),内嵌 `{num_best_prompts}` 供预格式化
- `_build_review_prompt(*, input_content, seed_prompt, chara_profile, num_best_prompts)` — 主路径 Prompt 装配(先预格式化 `_REVIEW_DIVERSITY_CRITERIA`,再入外层 `prompt_review.format`)
- `_run_review(...)` — 双路径调度(主 → 备)

**产物:**
- **DB**: `CreationPromptPrecreation.result_json` 更新为 N 张最终 card
- **前端**: `PromptCard` 数组,含 `id / title / preview / fullPrompt / composition / tags / createdAt`

**Route:** 继续走 `/api/creation/characters/{character_id}/prompt-precreation/{task_id}/status` 轮询,直到状态从 `reviewing` → `completed`。

---

## 6. 节点 5 · 一键创作出图(Nano Banana Pro)

**目标:** 把 N 张 PromptCard 每张跑 M 次(用户配置),提交给图片生成 API,得到最终图片。

**图片生成工具:** `app/tools/llm/nano_banana_pro.py`
- `generate_image_with_nano_banana_pro(Content, output_path, file_name, aspect_ratio)` — 底层图片 API 封装,调用 yibuapi.com 的 Gemini 2.5 Nano Banana Pro
- 输入 `Content` 是多模态内容数组:`[{text: prompt全文}, {text: 参考图指引}, {picture: 5张标准图路径}]`

**Service:** `app/services/creation_service/quick_create_service.py`
- `run_quick_create_task_sync(task_id)` — 后台任务入口
- `_resolve_selected_prompts(*, selected_prompts, latest_cards)` — 合并用户选择的 prompt 与最新 precreation cards,透传 `composition` 字段
- **auto 尺寸闭环核心逻辑**(核心创新):
  ```
  effective_ar = task.aspect_ratio  # 用户前端选的
  if effective_ar == "auto":
      # 从 per-card 的 composition.aspect_ratio 取
      effective_ar = item["composition"]["aspect_ratio"] or "16:9"
  generate_image_with_nano_banana_pro(..., aspect_ratio=effective_ar)
  ```

**产物:**
- **文件**: `data/beautify/quick_create/<task_id>/prompt_<N>_<id>/image_<M>_<timestamp>.png`
- **元数据**: `data/beautify/quick_create/<task_id>/task_meta.json`
- **DB**: `CreationQuickCreate.result_json` 记录每张图路径 + review payload(usable / repair_needed)

**Route:** `POST /api/creation/characters/{character_id}/quick-create/start`

---

## 7. 批量流(可选串联)

**入口:** 首页「批量创作」→ `POST /api/creation/batch-automation/start`
**Service:** `app/services/creation_service/batch_automation_service.py`
- 一次配置多轮迭代,每轮:创意方向已备好 → 抽种子 → 链式串联节点 3 → 4 → 5
- 长宽比校验:`_VALID_ASPECT` frozenset 允许 auto + 5 档手动比例
- 链式一键创作在节点 4 完成后自动触发,`_try_chain_quick_create` 保留每张 card 的 `composition` 字段(避免批量并发时被覆盖)

---

## 8. Prompt 文件全清单

| 节点 | Prompt 文件 | 关键常量 | 说明 |
|---|---|---|---|
| 1 | `app/prompts/material/creative_direction.py` | `creative_direction_prompt` | 创意方向生成(输出含 home_settings) |
| 2 | `app/prompts/material/creative_direction.py` | `creation_direction_seed_prompt` | 种子提示词生成(创作规范 4 硬约束) |
| 3 | `app/prompts/creation/prompt_precreation.py` | `prompt_step1` | step1 主创作(含构图三层决策) |
| 3 | `app/prompts/creation/prompt_precreation.py` | `prompt_step2` | step2 加工(镜头/构图/光影/材质补充) |
| 3 | `app/prompts/creation/prompt_template.py` | `init_template` | 空白填写模板(3 行硬回填位) |
| 3 | `app/prompts/creation/prompt_template.py` | `good_template1` | 高质量示例模板 |
| 4 | `app/prompts/creation/prompt_precreation.py` | `prompt_review` | 主审核路径(维度差异分) |
| 4 | `app/prompts/creation/prompt_precreation.py` | `prompt_review_backup` | 兜底审核路径 |

**其它相关 Prompt(不在本文流程主线,但存在)**
- `app/prompts/material/chara_profile.py` — 角色档案生成(节点 0 的前置)
- `app/prompts/material/standard_photo.py` — 标准参考图生成
- `app/prompts/material/creation_advice.py` — 创作建议(非主流程)
- `app/prompts/creation/prompt_review.py` — 一键创作后的单图审核(是否需要 repair)

## 9. Service 层文件全清单

**Material 模块 · 素材加工:**
- `chara_profile_generation_service.py` — 角色档案生成
- `standard_photo_generation_service.py` — 标准参考图生成
- `creative_direction_generation_service.py` — 节点 1:创意方向
- `seed_prompt_generation_service.py` — 节点 2:种子提示词
- `history_creative_directions.py` / `history_seed_prompts.py` — 历史查询辅助
- `material_file_service.py` — 通用文件读写
- `task_concurrency.py` — LLM 信号量控制(全局并发上限)

**Creation 模块 · 美图创作:**
- `composition_dimensions.py` — 构图维度枚举中央源(见归档 §6)
- `prompt_precreation_service.py` — 节点 3+4:预生成 + 审核
- `quick_create_service.py` — 节点 5:一键出图
- `batch_automation_service.py` — 批量串联流

**LLM 底层工具:**
- `app/tools/llm/yibu_llm_infer.py` — `yibu_gemini_infer(prompt, thinking_level, temperature)` 文本推理
- `app/tools/llm/nano_banana_pro.py` — `generate_image_with_nano_banana_pro(...)` 图片生成

## 10. 关键数据传递字段

### PromptCard 结构(节点 3/4/5 之间的传递介质)

```json
{
  "id": "uuid",
  "title": "第 1 行文本(前 40 字符)",
  "preview": "全文前 160 字符",
  "fullPrompt": "完整 Prompt 文本",
  "tags": [],
  "createdAt": "2026-07-03",
  "composition": {
    "aspect_ratio": "1:1",
    "subject_area_min": "0.65",
    "shooting_angle": "three_quarter",
    "camera_height": "slight_up",
    "gaze_direction": "to_camera"
  }
}
```

### [COMPOSITION_DECISION] 决策块(LLM 输出格式)

step1 LLM 必须在模板正文之前输出:

```
**[COMPOSITION_DECISION]**
aspect_ratio: 1:1
subject_area_min: 0.65
shooting_angle: three_quarter
camera_height: slight_up
gaze_direction: to_camera
```

这是 auto 长宽比闭环与镜头多样性追踪的数据源头。装配层用正则解析并挂到每张 card 的 `composition` 段。

### home_settings 传递路径

```
节点 1 生成 → DB material_creative_directions.home_settings (JSON 字符串)
      ↓
节点 2 装配层 _fold_home_settings_into_direction_text 折叠进 chara_creative_direction 文本
      ↓
节点 2 Prompt 里的「背景联动」硬约束引用它
      ↓
LLM 输出的 8–10 条种子每条明确关联一个 home_setting
```

## 11. 前端入口对照

| 前端页面 | 后端 Route | 触发节点 |
|---|---|---|
| Home 「批量创作」BatchConfigModal | `POST /api/creation/batch-automation/start` | 3+4+5 串联 |
| Prompt Gen Page | `POST /api/creation/.../prompt-precreation/start` | 3+4 |
| Quick Create Page | `POST /api/creation/.../quick-create/start` | 5 |
| Material Page 创意方向 | `POST /api/material/.../creative-directions/start` | 1 |
| Material Page 种子提示词 | `POST /api/material/.../seed-prompts/start` | 2 |

前端所有 aspect_ratio 下拉框都支持 `Auto` 档,选中后由 step1 决策实际画布尺寸,per-card 独立生效。

## 12. 关联文档

- 构图规划优化的设计动机与决策过程:[`docs/superpowers/specs/2026-06-30-creation-composition-planning-design.md`](superpowers/specs/2026-06-30-creation-composition-planning-design.md)
- 落地实施计划:[`docs/superpowers/plans/2026-07-02-creation-composition-planning.md`](superpowers/plans/2026-07-02-creation-composition-planning.md)
- 改动归档(commits 明细 + known issues):[`docs/superpowers/changelog/2026-07-03-creation-composition-planning.md`](superpowers/changelog/2026-07-03-creation-composition-planning.md)
- 项目总体架构 CLAUDE.md 说明:仓库根 `CLAUDE.md`
- 出图质量 A/B 实验体系（experiments/ 层）：[`docs/superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md`](superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md)，操作手册见仓库根 `experiments/README.md`
