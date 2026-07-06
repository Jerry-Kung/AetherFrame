# slim 模式生产落地设计（创作模块 Prompt 瘦身规则落地）

> 日期：2026-07-06
> 前置结论：`docs/superpowers/specs/2026-07-06-exp001-conclusion.md`（exp001 判定采纳 slim 为新基准）
> 方案：方案 A —— 模板全面 slim 化 + 代码层机器码剥离（用户已批准）

## 1. 目标与范围

把 exp001 验证通过的 6 条 Prompt 瘦身规则落地到生产创作链路，使 step1/step2 自动产出的最终文生图 Prompt 达到人工改写 slim 版的风格与质量水准（字符数落在 slim 冻结件区间约 1400–2100、无机器码、锚点合规、无文学修辞）。

**改动范围（4 个文件，不新增链路节点、不动 DB、不动前端）：**

| 文件 | 改动 |
|---|---|
| `app/prompts/creation/prompt_template.py` | `init_template` 字段说明 slim 化；`good_template1` 整体替换为 slim 版 cas_med_squat |
| `app/prompts/creation/prompt_precreation.py` | `prompt_step1`/`prompt_step2` 填写说明注入 6 条规则 + 文学转译规则；`prompt_review` 加简洁性偏好一行 |
| `app/services/creation_service/prompt_precreation_service.py` | 镜头段构图输出要求改为自然语言（不再回填枚举码行）；新增 `strip_machine_code` 纯函数 |
| `app/services/creation_service/quick_create_service.py` | 发图前调用 `strip_machine_code` 剥离机器码（规则 6 兜底） |

**不做（留给第二阶段）：** 腿脚崩坏专项、脸崩复现与专项、review 节点筛选目标重构、checker 校准、上游节点（创意方向/种子）改动。

**红线（继承 exp001）：**
- 13 字段结构骨架逐字保留（【固定】标签字段不动）
- 专业摄影词汇保留：三点布光 / Key / Fill / Rim / 体积光（丁达尔）/ Cinematic DOF / bloom / Eye Glint / 等效焦段（50mm 等）
- 记忆约束 [[creation-leg-foot-exposure-principle]]：自然展示腿/脚（袜）的第一原则不受影响——瘦身只砍表述方式，不砍腿脚展示要求

## 2. 文学输入 → 视觉事实的转译边界（用户提出的设计约束）

**问题：** `compose_seed_prompt_with_direction`（`prompt_precreation_service.py:164-194`）把节点 1 创意方向（title + description）与节点 2 种子文本拼接为 `"### 创作创意方向\n{title}\n\n{description}\n\n### 初始创作种子\n{text}"` 整体填入 step1/step2 的 `{seed_prompt}` 槽。这两部分不可避免带文学性描述，与"最终 Prompt 去文学化"的瘦身目标存在张力。

**设计原则：文学性留在种子层，视觉事实进模板层。** 种子的文学描述服务于"帮 step1 脑补出好场景"，价值保留；瘦身砍的是"文学语言泄漏进最终 Prompt"。上游节点不改，step1 承担"文学 → 视觉"的翻译职责。

**落地方式：** 在 `prompt_step1` 任务步骤中新增一条显式转译规则（`prompt_step2` 注意事项中同步一条简版）：

> 用户的原始输入可能包含文学化、抒情化的描述（如"发丝如丝绸般流淌"、"展现极致的信任感"）。这些内容是你理解场景与情绪的**创意来源**，但**禁止原样抄入模板字段**。填写模板时必须把它们转译为可直接绘制的视觉事实：具体的物体、位置、姿势、颜色、材质（"发丝如丝绸般流淌在榻榻米上" → "长发散开铺在榻榻米上"）；情绪意图转译为白名单内的单一表情与视线方向（"展现极致的信任感" → "柔和微笑，看向镜头"）。

## 3. 六条瘦身规则的注入点

### 规则 1：表情降级白名单
- `init_template` 「角色神态」字段说明改为：单一主表情 + 视线方向；白名单：平静 / 柔和微笑 / 闭眼 / 微微含笑 / 专注；禁止多微表情叠加。
- `prompt_step1` 填写说明同步。

### 规则 2：消除锁脸 vs 改脸矛盾
- `prompt_step1` 锚点说明追加：锚点只允许非五官视觉物件（头饰 / 发色 / 服饰 / 配饰），禁止描述眼型、瞳色、五官形状——脸完全交给参考图。
- 神态说明追加：不描述眼睛长相，只描述视线方向。

### 规则 3：锚点收敛绑定参考图
- 现有"3-5 个"上限保留，追加：每条锚点只含一个物件、≤8 字纯视觉名词、结尾加"（见参考图）"、禁止文学标签。

### 规则 4：删文学修辞与解剖学描述
- `prompt_step1` / `prompt_step2` 注意事项各加一条：禁止文学抒情比喻、设计意图旁白（"传达出xx感"）、解剖学词汇（足弓 / 骨骼 / 关节结构）。
- 脚部/袜子设计说明中现有的正向引导（"不要写实化或包含过度的解剖细节"等）保留不动。

### 规则 5：清除正负矛盾
- `prompt_step2` Negative 填写说明改为：填写前逐条比对正文，正文已正向声明的内容禁止写入 Negative；只保留 3-5 条正文未提及的高危名词短语；禁止 (word:1.3) 权重语法。
- `init_template` Negative 字段说明同步收紧（3-5 条上限）。

### 规则 6：机器码剥离（代码层，见 §4）

### 配套：good_template1 替换
- 以 `experiments/variants/exp001/slim/cas_med_squat.txt`（用户指定的最佳出图款）为蓝本替换 `good_template1` 全文。
- 适配调整：作为通用范例保留其 3:4 画幅与蹲姿场景；镜头段已是自然语言开头（"3/4 正面视角，机位略高做轻微俯拍"），与 §4 模板端改动一致。
- 理由：范例即规范——防止"模板说瘦身、范例却华丽"的自相矛盾（exp001 结论 §2.4 已认定旧范例是复杂度膨胀源）。

## 4. 机器码剥离（规则 6）

**协议保留：** step1 输出的 `[COMPOSITION_DECISION]` 块继续保留——`_parse_step1_composition` 靠它解析构图存入卡片 `composition` 字段（auto 档出图时决定 aspect_ratio，review 多样性评估也用它）。这是流水线内部协议，不能删。

**变化在两端：**

1. **模板端**（`prompt_template.py` + `prompt_precreation_service.py`）：
   - `init_template` 镜头段删除三行 `` `[SHOOTING_ANGLE]` `` / `` `[CAMERA_HEIGHT]` `` / `` `[GAZE_DIRECTION]` `` 枚举码回填要求，改为"以一句自然语言开头描述机位方位 / 高度 / 视线方向"（如"3/4 正面视角，机位略高做轻微俯拍，视线看向镜头"）。
   - `_build_step1_prompt` 中 `composition_output` 说明同步：决策块照写，但正文镜头段不再回填枚举码，改用自然语言表述所选决策。
   - `prompt_step2` 中"长宽比已在 step1 决策并回填至模板顶部"等相关表述核对一致性。

2. **发图端**（`quick_create_service.py`）：
   - 新增纯函数 `strip_machine_code(prompt: str) -> str`（放在 `prompt_precreation_service.py`，复用同文件现成的 `_COMPOSITION_BLOCK_RE`，由 quick_create_service 导入）：剥离 `**[COMPOSITION_DECISION]**` 块与残留的 `` `[SHOOTING_ANGLE]` `` 类枚举行。
   - `quick_create_service` 装配 content（约 341-346 行 `content = [{"text": full_prompt}, ...]`）前调用它，作为模板遵从失败时的确定性兜底。
   - **存档不变：** candidate_prompt_NNN.txt 与卡片 fullPrompt 保持原样（含机器码），只在发给图像模型的最后一刻剥离。aspect_ratio 解析链路（composition dict → "auto" 档解析 → "16:9" 兜底）不受影响。

## 5. review 节点轻改（一行）

`prompt_review` 评审说明加一句：

> 候选质量相近时，优先选择表述简洁凝练、无冗余修辞的候选；华丽文风本身不是加分项。

目的：防止评审 LLM 因"华丽 = 用心"的偏好系统性淘汰 slim 风格候选。完整筛选目标重构留给第二阶段。

## 6. 验证方案（小批量回归，复用 experiments 基建）

1. 模板 + 代码改完、单元测试通过后，新增 `experiments/configs/exp001b.yaml`：用**改造后的生产链路**（baseline_gen 本来就镜像 `_collect_candidates`）为 6 个基准种子各生成 1 份 Prompt，人工抽查确认 6 条规则遵从（字符数落在 slim 冻结件区间约 1400–2100、无机器码泄漏、锚点合规、无文学修辞）。
2. 生产环境跑 18 张图（6 种子 × 3 张），取回后与 exp001 的 slim 组（人工改写版）生成 reveal 式并排对照页。
3. 用户人工确认无回退 → 落地完成；发现系统性回退 → 区分"模板遵从性问题"（LLM 没照做，迭代模板措辞）与"规则本身问题"（规则在自动链路下有副作用，回退该条规则）。
4. checker 自动指标照跑，仍只作参考值（未校准）。

## 7. 测试与风险

**单元测试：**
- `strip_machine_code`：块剥离 / 枚举行剥离 / 无机器码时原样返回 / 幂等（strip 两次结果相同）。
- 模板常量结构断言：`init_template` 不再含 `[SHOOTING_ANGLE]` 枚举回填行；`prompt_step1` 含转译规则关键句；`prompt_review` 含简洁性偏好句（轻量字符串断言，防止后续误删）。
- 现有 composition 解析相关测试保持绿色（COMPOSITION_DECISION 协议未变）。

**风险与对策：**

| 风险 | 对策 |
|---|---|
| LLM 模板遵从性不及人工改写 | exp001b 小批量回归兜底；遵从失败的机器码由代码层剥离保证下限 |
| review 节点淘汰 slim 候选 | 简洁性偏好一行；回归中观察 review 选择结果 |
| 上游文学性泄漏进最终 Prompt | §2 转译规则 + 回归抽查 |
| 改动引入回退 | 全部改动收敛在一个 commit 序列内，revert 即回到现状 |
