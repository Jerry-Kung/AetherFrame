# slim 模式生产落地实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 exp001 验证通过的 6 条 Prompt 瘦身规则落地到生产创作链路（模板 slim 化 + good_template 替换 + 发图前机器码剥离），并用 exp001b 小批量回归验证。

**Architecture:** 全部改动收敛在 4 个文件：两个 prompt 模板文件的文本修订、`prompt_precreation_service.py` 的构图输出说明微调 + 新增 `strip_machine_code` 纯函数、`quick_create_service.py` 发图前调用剥离。`[COMPOSITION_DECISION]` 内部协议保留不动（aspect_ratio 解析与 review 多样性评估依赖它），只在发给图像模型的最后一刻剥离。

**Tech Stack:** Python / FastAPI 项目；pytest；无新依赖。

**Spec:** `docs/superpowers/specs/2026-07-06-slim-prompt-production-design.md`（已批准）

## Global Constraints

- 13 字段结构骨架逐字保留；`init_template` 中带【固定】标签的字段（任务目标 / 使用参考图锁定身份 / 统一风格）**一个字都不改**
- 专业摄影词汇保留白名单：三点布光 / Key / Fill / Rim / 体积光（丁达尔）/ Cinematic DOF / bloom / Eye Glint / 等效焦段
- 腿脚展示第一原则不受影响：`init_template` 角色姿势/服装/脚部袜子字段的"自然展示腿部与脚部"相关要求全部保留
- `[COMPOSITION_DECISION]` 块协议不变：step1 仍在正文前输出决策块，`_parse_step1_composition` 及其全部现有测试必须保持绿色
- 存档不变：candidate_prompt_NNN.txt 与卡片 fullPrompt 保持含机器码的原样，仅发图时剥离
- 表情白名单（逐字使用）：平静 / 柔和微笑 / 闭眼 / 微微含笑 / 专注
- 锚点规则（逐字要点）：3-5 个；每条只含一个物件；≤8 字纯视觉名词；结尾加"（见参考图）"；禁止五官描述（眼型/瞳色/五官形状）
- Negative 规则：3-5 条上限；正文已正向声明的内容禁止写入；禁止 (word:1.3) 权重语法
- 运行测试命令一律用 `python -m pytest`（Windows 环境）；全量回归为 `python -m pytest tests/ -q`

---

## 文件结构总览

| 文件 | 责任 | 任务 |
|---|---|---|
| `app/services/creation_service/prompt_precreation_service.py` | 新增 `strip_machine_code`；`composition_output` 说明改自然语言回填 | Task 1, 3 |
| `app/prompts/creation/prompt_template.py` | `init_template` 字段说明 slim 化 + 镜头段去枚举行；`good_template1` 替换 | Task 2 |
| `app/prompts/creation/prompt_precreation.py` | step1/step2 注入 6 条规则 + 文学转译规则；review 加简洁性偏好 | Task 3, 4 |
| `app/services/creation_service/quick_create_service.py` | 发图前调用 `strip_machine_code` | Task 5 |
| `tests/services/test_strip_machine_code.py` | 剥离函数单元测试（新建） | Task 1 |
| `tests/services/test_slim_template_structure.py` | 模板常量结构断言（新建） | Task 2, 3, 4 |
| `experiments/configs/exp001b.yaml` | 回归实验配置（新建） | Task 6 |

---

### Task 1: strip_machine_code 纯函数（TDD）

**Files:**
- Modify: `app/services/creation_service/prompt_precreation_service.py`（在 `_parse_step1_composition` 函数之后、`compose_seed_prompt_with_direction` 之前插入）
- Test: `tests/services/test_strip_machine_code.py`（新建）

**Interfaces:**
- Consumes: 同文件已有的 `_COMPOSITION_BLOCK_RE`（模块级正则，line 43）
- Produces: `strip_machine_code(prompt: str) -> str` —— Task 5 的 quick_create_service 将 `from app.services.creation_service.prompt_precreation_service import strip_machine_code` 导入并在发图前调用

**背景（给零上下文工程师）：** 生产链路 step1 LLM 在 Prompt 正文前输出一段 `**[COMPOSITION_DECISION]**` 机器决策块（aspect_ratio 等 5 行 `key: value`），正文镜头段还可能残留 `` `[SHOOTING_ANGLE]` three_quarter (3/4 正面)`` 这类枚举回填行。这些机器码是流水线内部协议（解析构图用），但发给图像生成模型会污染画面理解。本函数在发图前把它们剥掉，其他文本原样保留。

- [ ] **Step 1: 写失败测试**

创建 `tests/services/test_strip_machine_code.py`：

```python
from app.services.creation_service.prompt_precreation_service import strip_machine_code


COMPOSITION_BLOCK = (
    "**[COMPOSITION_DECISION]**\n"
    "aspect_ratio: 3:4\n"
    "subject_area_min: pct_65\n"
    "shooting_angle: three_quarter\n"
    "camera_height: slight_up\n"
    "gaze_direction: to_camera\n"
)

BODY = (
    "**【固定】任务目标**：生成一张 **3:4** 的插画。\n"
    "\n"
    "**镜头与构图（让人一眼“WoW”）**：3/4 正面视角，机位略高做轻微俯拍。\n"
)


def test_strips_composition_decision_block():
    result = strip_machine_code(COMPOSITION_BLOCK + "\n" + BODY)
    assert "[COMPOSITION_DECISION]" not in result
    assert "aspect_ratio:" not in result
    assert "**【固定】任务目标**" in result
    assert "3/4 正面视角" in result


def test_strips_legacy_enum_backfill_lines():
    legacy = (
        "**镜头与构图**：\n"
        "`[SHOOTING_ANGLE]` three_quarter (3/4 正面)\n"
        "`[CAMERA_HEIGHT]` slight_up (略仰)\n"
        "`[GAZE_DIRECTION]` to_camera (看镜头)\n"
        "使用等效 35mm 焦段。\n"
    )
    result = strip_machine_code(legacy)
    assert "[SHOOTING_ANGLE]" not in result
    assert "[CAMERA_HEIGHT]" not in result
    assert "[GAZE_DIRECTION]" not in result
    assert "使用等效 35mm 焦段。" in result


def test_no_machine_code_returns_unchanged():
    assert strip_machine_code(BODY) == BODY


def test_idempotent():
    once = strip_machine_code(COMPOSITION_BLOCK + "\n" + BODY)
    assert strip_machine_code(once) == once


def test_empty_string():
    assert strip_machine_code("") == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/services/test_strip_machine_code.py -v`
Expected: FAIL — `ImportError: cannot import name 'strip_machine_code'`

- [ ] **Step 3: 最小实现**

在 `app/services/creation_service/prompt_precreation_service.py` 中，`_parse_step1_composition` 函数结束后（约 line 162 之后）插入：

```python
_ENUM_BACKFILL_LINE_RE = _re.compile(
    r"^\s*`\[(?:SHOOTING_ANGLE|CAMERA_HEIGHT|GAZE_DIRECTION)\]`[^\n]*\n?",
    _re.MULTILINE,
)


def strip_machine_code(prompt: str) -> str:
    """发图前剥离流水线机器码：[COMPOSITION_DECISION] 决策块与镜头段枚举回填行。

    卡片 fullPrompt 与存档保持原样，仅在发送给图像模型的最后一刻调用。
    对不含机器码的文本幂等（原样返回）。
    """
    text = _COMPOSITION_BLOCK_RE.sub("", prompt)
    text = _ENUM_BACKFILL_LINE_RE.sub("", text)
    return text.lstrip("\n") if text != prompt else prompt
```

注意：`_COMPOSITION_BLOCK_RE.sub("", ...)` 会把决策块（含标记行到下一个 `**` 字段前）整体删除；剥离后开头可能残留空行，用 `lstrip("\n")` 清理；完全没有命中时按幂等要求原样返回。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/services/test_strip_machine_code.py -v`
Expected: 5 passed

- [ ] **Step 5: 回归确认协议未破坏**

Run: `python -m pytest tests/services/test_prompt_precreation_composition_persistence.py -q`
Expected: 全部 PASS（`_parse_step1_composition` 未被改动）

- [ ] **Step 6: 提交**

```bash
git add tests/services/test_strip_machine_code.py app/services/creation_service/prompt_precreation_service.py
git commit -m "feat(creation): 新增 strip_machine_code 发图前机器码剥离（规则6基础）"
```

---

### Task 2: init_template slim 化 + good_template1 替换

**Files:**
- Modify: `app/prompts/creation/prompt_template.py`（全文重写，67 行）
- Test: `tests/services/test_slim_template_structure.py`（新建）

**Interfaces:**
- Consumes: 无（纯模板常量文件）
- Produces: `init_template`、`good_template1` 两个字符串常量，名称与导出方式不变（`prompt_precreation_service.py:23` 的 `from app.prompts.creation.prompt_template import good_template1, init_template` 与 `experiments/baseline_gen.py:9` 依赖此名称）

**背景：** `init_template` 是 step1 LLM 填充的 13 字段骨架，其中括号内的填写说明是行为指令；`good_template1` 是随模板下发的"高质量范例"。exp001 结论认定旧范例（华丽窗台款）是复杂度膨胀源，需替换为 slim 版 cas_med_squat（用户指定的最佳出图款，冻结于 `experiments/variants/exp001/slim/cas_med_squat.txt`）。镜头段的三行枚举码回填要求改为自然语言开头。

- [ ] **Step 1: 写失败的结构断言测试**

创建 `tests/services/test_slim_template_structure.py`（本任务只写 init_template/good_template1 部分，Task 3/4 会往同文件追加）：

```python
"""slim 化模板的轻量结构断言：防止后续误删关键指令或倒退回华丽风格。"""
from app.prompts.creation.prompt_template import good_template1, init_template


class TestInitTemplateSlim:
    def test_no_enum_backfill_lines(self):
        assert "[SHOOTING_ANGLE]" not in init_template
        assert "[CAMERA_HEIGHT]" not in init_template
        assert "[GAZE_DIRECTION]" not in init_template

    def test_camera_field_requires_natural_language_opening(self):
        assert "自然语言" in init_template

    def test_fixed_fields_untouched(self):
        assert "**【固定】任务目标**" in init_template
        assert "{aspect_ratio}" in init_template
        assert "{subject_area_min_pct}" in init_template
        assert "**【重要，必须遵守】角色的面部五官细节、面部神韵、发型发色、发饰、整体气质、核心装饰物需要与参考图完全一致，不要改脸。**" in init_template
        assert "3D toon shader + 细腻 cel shading" in init_template

    def test_thirteen_field_skeleton_preserved(self):
        for field in (
            "**角色视觉锚点**", "**背景场景**", "**角色姿势", "**角色服装**",
            "**角色脚部/袜子细节**", "**角色神态**", "**镜头与构图",
            "**构图硬约束**", "**光影", "**材质与质感", "**Negative Prompt**",
        ):
            assert field in init_template, f"缺少字段: {field}"

    def test_expression_whitelist_in_expression_field(self):
        for word in ("平静", "柔和微笑", "闭眼", "微微含笑", "专注"):
            assert word in init_template
        assert "单一主表情" in init_template
        assert "视线方向" in init_template

    def test_leg_foot_exposure_preserved(self):
        assert "自然展示腿部与脚部，但不低俗" in init_template
        assert "穿着袜子，不得穿鞋、赤足" in init_template

    def test_negative_field_caps_at_3_to_5(self):
        assert "3-5" in init_template.split("**Negative Prompt**")[1]


class TestGoodTemplateSlim:
    def test_based_on_slim_cas_med_squat(self):
        assert "淡紫色薄纱短袜" in good_template1
        assert "白猫" in good_template1
        assert "3:4" in good_template1

    def test_no_machine_code(self):
        assert "[SHOOTING_ANGLE]" not in good_template1
        assert "[COMPOSITION_DECISION]" not in good_template1

    def test_camera_opens_with_natural_language(self):
        assert "3/4 正面视角，机位略高做轻微俯拍" in good_template1

    def test_anchors_bound_to_reference(self):
        assert "（见参考图）" in good_template1

    def test_negative_is_short_noun_list(self):
        neg = good_template1.split("**Negative Prompt**")[1]
        assert len([p for p in neg.replace("：", "").split("、") if p.strip()]) <= 5

    def test_pro_photography_vocab_retained(self):
        for term in ("Key Light", "Fill Light", "Rim Light", "Eye Glint", "50mm"):
            assert term in good_template1

    def test_old_ornate_exemplar_removed(self):
        assert "纯白色丝袜" not in good_template1  # 旧窗台款特征
        assert "飘窗" not in good_template1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/services/test_slim_template_structure.py -v`
Expected: FAIL —— 枚举行断言、表情白名单断言、good_template 内容断言等多项失败（旧模板仍是窗台款）

- [ ] **Step 3: 重写 prompt_template.py**

用以下内容**整体替换** `app/prompts/creation/prompt_template.py`：

```python
init_template = """
**【固定】任务目标**：请你根据用户上传或描述的主体形象，生成一张 **{aspect_ratio}** 的高端游戏宣传插画级“室内角色场景图”，用于展示主角的居家瞬间。画面超清、细节丰富但不杂乱。

**【固定】使用参考图锁定身份**：**【重要，必须遵守】角色的面部五官细节、面部神韵、发型发色、发饰、整体气质、核心装饰物需要与参考图完全一致，不要改脸。**

**角色视觉锚点**：（3-5 条高价值易丢失锚点。每条只含一个物件、≤8 字纯视觉名词、结尾加“（见参考图）”，如“黑荆棘粉白花冠（见参考图）”。只允许非五官视觉物件——头饰/发色/服饰/配饰；禁止描述眼型、瞳色、五官形状，脸完全交给参考图；禁止文学标签）

**【固定】统一风格**：整张图（人物与背景）采用**统一的精致 3D 动漫插画风格**（3D toon shader + 细腻 cel shading），线条描边克制一致，材质高级干净，绝不出现“人物二次元但背景写实”的割裂。

**背景场景**：（室内空间的世界观主题、装修风格、道具布景等。只写可直接绘制的视觉事实：具体物体、位置、颜色、材质；不写抒情比喻与设计意图旁白）

**角色姿势（自然展示腿部与脚部，但不低俗）**：（角色的姿势描述，保持自然放松，并且需要自然展示腿部与脚部，但不低俗。只写身体部位的位置与朝向，禁止解剖学词汇——足弓/骨骼/关节结构）

**角色服装**：（角色的服装描述，需要脑补角色在该场景中最适合的服装和袜子样式。这里需要明确指定角色脚上需要穿着袜子，不得穿鞋、赤足）

**角色脚部/袜子细节**：（根据角色的袜子样式设计，增加2-3句角色腿/脚部及袜子的相关细节设计描述。）

**角色神态**：（单一主表情 + 视线方向，一句话。表情从白名单中选：平静 / 柔和微笑 / 闭眼 / 微微含笑 / 专注；禁止多微表情叠加；不描述眼睛长相，只描述视线方向）

**镜头与构图（让人一眼“WoW”）**：（以一句自然语言开头描述机位方位/高度/视线方向，与 step1 决策一致，例：“3/4 正面视角，机位略高做轻微俯拍，视线看向镜头”。随后指定 **等效焦段范围**、前中后景分层、焦点引导路径）

**构图硬约束**：角色主体在画面中占比不低于 {subject_area_min_pct}%；（对于构图固定约束的补充说明与强调）

**光影（电影级三点布光）**：（Key / Fill / Rim 的职责各一句写清楚，可选体积光、粒子、Eye Glint；不堆叠形容词）

**材质与质感（高级感来源）**：（2-4 个关键材质，每个一句，不用过细）

**Negative Prompt**：（3-5 条高风险失败项的名词短语，用“、”分隔。正文已正向声明的内容禁止写入；禁止 (word:1.3) 权重语法；不要包含模型几乎不可能犯的低级错误）
"""


good_template1 = """
**【固定】任务目标**：请你根据用户上传或描述的主体形象，生成一张 **3:4** 的高端游戏宣传插画级“室内角色场景图”，用于展示主角的居家瞬间。画面超清、细节丰富但不杂乱。

**【固定】使用参考图锁定身份**：**【重要，必须遵守】角色的面部五官细节、面部神韵、发型发色、发饰、整体气质、核心装饰物需要与参考图完全一致，不要改脸。**

**角色视觉锚点**：
*   黑荆棘粉白花冠（见参考图）
*   额前水滴形紫宝石（见参考图）
*   尖长精灵耳（见参考图）
*   银紫色长发（见参考图）
*   左手黑色长手套（见参考图，此场景中半褪至手背）

**【固定】统一风格**：整张图（人物与背景）采用**统一的精致 3D 动漫插画风格**（3D toon shader + 细腻 cel shading），线条描边克制一致，材质高级干净，绝不出现“人物二次元但背景写实”的割裂。

**背景场景**：温馨洁净的日式现代风玄关。浅色原木地板，一侧墙壁为磨砂玻璃窗，阳光透过玻璃在玄关洒下大片暖金色光斑。右侧是原木色实木鞋柜，柜面上摆着一盆多肉盆栽与几本小书，一只毛茸茸的纯白小猫趴在鞋柜边缘。

**角色姿势（自然展示腿部与脚部，但不低俗）**：角色蹲在玄关的木地板上，双膝并拢，裙摆在双脚周围自然散开。身体略微向右前倾，呈 3/4 侧面面对镜头。右手轻撑在大腿上保持平衡，左臂微微抬起，用半脱手套的手指指尖轻轻伸向鞋柜上的白猫。双腿曲折蹲下，脚部自然折叠并清晰可见。

**角色服装**：轻盈简约的纯白棉麻短袖连衣裙，裙面干净无复杂花纹，有自然褶皱。右臂完全裸露，左手黑色长手套半褪至手背处。脚上穿着一双**轻薄透气的淡紫色薄纱短袜**，不穿鞋。

**角色脚部/袜子细节**：淡紫色薄纱短袜，轻薄半透明，贴合足部，微透出皮肤的淡粉色。袜口有极窄的蕾丝花边，松松贴合脚踝，带少许自然褶皱。脚跟因蹲姿略微抬起。

**角色神态**：温柔浅笑，微微低头，视线向下看着鞋柜上的白猫。

**镜头与构图（让人一眼“WoW”）**：3/4 正面视角，机位略高做轻微俯拍，角色视线看向下方。采用等效 **50mm** 自然人像焦段，聚焦下蹲的角色。构图以黄金对角线引导：从左上方洒入的日光 → 面部 → 半褪手套的左臂 → 指尖与白猫接触点。前景以鞋柜边缘作微弱虚化遮挡，中景人物与白猫清晰锐利，背景在大光圈景深（Cinematic Bokeh）中柔和虚化。

**构图硬约束**：角色主体在画面中占比不低于 65%；必须完整展现角色下蹲的全身比例；双膝、裙摆及穿薄纱短袜的双脚必须完全在画幅内，脚部严禁出画或被前景完全遮挡。

**光影（电影级三点布光）**：主光（Key Light）为穿透磨砂玻璃的侧逆向暖阳，在发丝及身体右侧形成金色轮廓光（Rim Light），空气中呈现温暖体积光（丁达尔效应）与漂浮的金色尘埃粒子。辅光（Fill Light）为低强度漫射暖白光，弱化暗部投影，保留白裙褶皱与背光侧的渐变细节，不死黑。眼中点出窗格反射高光（Eye Glint）。

**材质与质感（高级感来源）**：发丝在逆光下有半透明的边缘漫射；纯白棉麻裙的褶皱受光边缘呈柔和漫反射；黑色手套与白皙手背形成材质对比；淡紫色薄纱短袜轻盈高透光，蕾丝花边结构清晰；白猫绒毛在边缘光下蓬松柔软。

**Negative Prompt**：穿鞋、多余的手指、断肢、面部五官变形、画风割裂。
"""
```

要点说明：
- good_template1 正文 = `experiments/variants/exp001/slim/cas_med_squat.txt` 全文原样（含"角色视觉锚点"5 条实例），仅光影字段标题的括号从半角 `)` 修正为全角 `）` 以与骨架一致
- init_template 的镜头段用自然语言开头要求替换了原三行枚举回填（原 line 21-24）
- 神态/锚点/Negative 字段说明按 Global Constraints 的逐字规则改写
- 已知的既有措辞不一致无需处理：`prompt_step2` 提到"角色的基本信息"字段而 init_template 从未有过该字段，属改造前就存在的历史遗留，不在本任务范围

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/services/test_slim_template_structure.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 回归相关消费方测试**

Run: `python -m pytest tests/services/test_prompt_precreation_composition_persistence.py tests/experiments/test_baseline_gen.py -q`
Expected: 全部 PASS（导入名称未变）

- [ ] **Step 6: 提交**

```bash
git add app/prompts/creation/prompt_template.py tests/services/test_slim_template_structure.py
git commit -m "feat(creation): init_template slim 化 + good_template1 替换为 slim cas_med_squat（规则1/2/3/5 模板端）"
```

---

### Task 3: prompt_step1 注入转译规则与瘦身规则 + composition_output 自然语言化

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py`（`prompt_step1` 常量，line 1-62）
- Modify: `app/services/creation_service/prompt_precreation_service.py`（`_build_step1_prompt` 内 `composition_output` 局部变量，约 line 93-106）
- Test: `tests/services/test_slim_template_structure.py`（追加断言类）

**Interfaces:**
- Consumes: Task 2 的新 `init_template`（step1 模板通过 `{init_template}` 槽引用它）
- Produces: 修订后的 `prompt_step1` 字符串常量（名称不变）；`_build_step1_prompt` 签名不变

**背景：** `prompt_step1` 是指挥 step1 LLM 填模板的任务说明书。需要：① 新增"文学输入 → 视觉事实"转译规则（spec §2，用户明确要求）；② 模版填写说明与 Task 2 的新字段说明对齐（表情白名单、锚点规则、删修辞/解剖学）；③ `composition_output` 说明补充"正文镜头段用自然语言表述所选决策，不出现枚举码"。

- [ ] **Step 1: 追加失败测试**

在 `tests/services/test_slim_template_structure.py` 末尾追加：

```python
class TestPromptStep1Slim:
    def _p(self):
        from app.services.creation_service.prompt_precreation_service import _build_step1_prompt
        return _build_step1_prompt(chara_profile="档案", seed_prompt="种子")

    def test_contains_literary_translation_rule(self):
        p = self._p()
        assert "创意来源" in p
        assert "禁止原样抄入" in p
        assert "视觉事实" in p

    def test_contains_expression_whitelist_rule(self):
        p = self._p()
        assert "单一主表情" in p

    def test_contains_anchor_binding_rule(self):
        p = self._p()
        assert "（见参考图）" in p
        assert "8 字" in p or "8字" in p

    def test_forbids_rhetoric_and_anatomy(self):
        p = self._p()
        assert "抒情比喻" in p
        assert "解剖学词汇" in p

    def test_composition_block_protocol_kept(self):
        p = self._p()
        assert "[COMPOSITION_DECISION]" in p

    def test_composition_output_requires_natural_language_not_backfill(self):
        p = self._p()
        assert "自然语言" in p
        assert "`[SHOOTING_ANGLE]` <从" not in p

    def test_leg_foot_design_guidance_preserved(self):
        p = self._p()
        assert "不要写实化或包含过度的解剖细节" in p
        assert "自然展示腿部与脚部，但不低俗" in p
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/services/test_slim_template_structure.py::TestPromptStep1Slim -v`
Expected: `test_contains_literary_translation_rule` 等多项 FAIL（现有 step1 无这些指令）

- [ ] **Step 3: 修订 prompt_step1**

对 `app/prompts/creation/prompt_precreation.py` 的 `prompt_step1` 做四处 Edit（其余行原样保留）：

**Edit 3a — 任务步骤第 1 步之前插入转译规则**（在 `1、根据用户的需求，想象一幅最美妙的、以角色为核心主体的画面；` 一行之前插入）：

```
**文学输入转译规则（必须遵守）**：用户的原始输入（含创意方向与创作种子）可能包含文学化、抒情化的描述（如"发丝如丝绸般流淌"、"展现极致的信任感"）。这些内容是你理解场景与情绪的**创意来源**，但**禁止原样抄入**模板字段。填写模板时必须把它们转译为可直接绘制的**视觉事实**：具体的物体、位置、姿势、颜色、材质（"发丝如丝绸般流淌在榻榻米上" → "长发散开铺在榻榻米上"）；情绪意图转译为白名单内的单一表情与视线方向（"展现极致的信任感" → "柔和浅笑，看向镜头"）。
```

**Edit 3b — 模版填写说明第 1 条**，原文：

```
1、首先填写模板中的"背景场景"、"角色姿势"、"角色服装"、"角色神态"这四个字段，并严格遵守字段后面括号内的填写说明。
```

改为：

```
1、首先填写模板中的"背景场景"、"角色姿势"、"角色服装"、"角色神态"这四个字段，并严格遵守字段后面括号内的填写说明。"角色神态"必须是单一主表情 + 视线方向（表情白名单：平静 / 柔和微笑 / 闭眼 / 微微含笑 / 专注）。
```

**Edit 3c — 模版填写说明第 2 条**，原文：

```
2、确定角色需要固定的一些视觉锚点（仅保留高价值易丢失锚点，3-5个即可，不要过度展开），填写到模板中的"角色视觉锚点"字段中。
```

改为：

```
2、确定角色需要固定的一些视觉锚点（仅保留高价值易丢失锚点，3-5个即可，不要过度展开），填写到模板中的"角色视觉锚点"字段中。每条锚点只含一个物件、≤8 字纯视觉名词、结尾加"（见参考图）"；只允许非五官视觉物件（头饰/发色/服饰/配饰），禁止描述眼型、瞳色、五官形状。
```

（注意：源文件中引号为中文全角引号“”，Edit 时以文件实际内容为准。）

**Edit 3d — 注意事项区**，在 `- **注意**，用词简洁凝练、突出重点、不要包含与绘图无关的冗余废话。` 一行之后插入：

```
- **注意**，禁止文学抒情比喻、设计意图旁白（"传达出xx感"）、解剖学词汇（足弓/骨骼/关节结构）。
```

- [ ] **Step 4: 修订 composition_output（service 层）**

在 `app/services/creation_service/prompt_precreation_service.py` 的 `_build_step1_prompt` 中，`composition_output` 的最后一句（原 line 104-105）：

```python
        "后续「任务目标」与「构图硬约束」段中，请用你选定的长宽比替换 `{aspect_ratio}` 占位符、"
        "用主体占比下限的百分比值（如 65%）替换 `{subject_area_min_pct}` 占位符。"
```

改为：

```python
        "后续「任务目标」与「构图硬约束」段中，请用你选定的长宽比替换 `{aspect_ratio}` 占位符、"
        "用主体占比下限的百分比值（如 65%）替换 `{subject_area_min_pct}` 占位符。"
        "正文「镜头与构图」段**不要**出现任何枚举 code 或方括号标记，"
        "以一句自然语言开头表述你选定的机位方位/高度/视线方向"
        "（例：\"3/4 正面视角，机位略高做轻微俯拍，视线看向镜头\"）。"
```

- [ ] **Step 5: 跑测试确认通过 + 协议回归**

Run: `python -m pytest tests/services/test_slim_template_structure.py tests/services/test_prompt_precreation_composition_persistence.py tests/services/test_seed_prompt_composition_prompt.py -v`
Expected: 全部 PASS（决策块协议测试 `test_build_step1_prompt_contains_composition_output_requirement` 仍绿——决策块要求保留）

- [ ] **Step 6: 提交**

```bash
git add app/prompts/creation/prompt_precreation.py app/services/creation_service/prompt_precreation_service.py tests/services/test_slim_template_structure.py
git commit -m "feat(creation): step1 注入文学转译规则与瘦身规则，镜头段改自然语言（规则1/2/3/4）"
```

---

### Task 4: prompt_step2 Negative 收紧 + prompt_review 简洁性偏好

**Files:**
- Modify: `app/prompts/creation/prompt_precreation.py`（`prompt_step2` line 65-98；`prompt_review` line 101-145）
- Test: `tests/services/test_slim_template_structure.py`（追加断言类）

**Interfaces:**
- Consumes: 无新依赖
- Produces: 修订后的 `prompt_step2`、`prompt_review` 常量（名称不变；`prompt_review_backup` 不改——它只输出文件名，无评价行为可引导）

**背景：** step2 填镜头/光影/材质/Negative 四个高级字段。规则 5 要求 Negative 与正文不矛盾且 3-5 条封顶；规则 4 的禁修辞条款也要在 step2 出现（它独立生成文本）；转译规则加简版（step2 也接收 `{seed_prompt}`）。review 节点加一行简洁性偏好，防止评审 LLM 系统性淘汰 slim 候选。

- [ ] **Step 1: 追加失败测试**

在 `tests/services/test_slim_template_structure.py` 末尾追加：

```python
class TestPromptStep2AndReviewSlim:
    def test_step2_negative_contradiction_rule(self):
        from app.prompts.creation.prompt_precreation import prompt_step2
        assert "正向声明" in prompt_step2
        assert "3-5" in prompt_step2
        assert "权重语法" in prompt_step2

    def test_step2_forbids_rhetoric_and_anatomy(self):
        from app.prompts.creation.prompt_precreation import prompt_step2
        assert "抒情比喻" in prompt_step2
        assert "解剖学词汇" in prompt_step2

    def test_step2_literary_translation_brief(self):
        from app.prompts.creation.prompt_precreation import prompt_step2
        assert "视觉事实" in prompt_step2

    def test_review_prefers_concise_candidates(self):
        from app.prompts.creation.prompt_precreation import prompt_review
        assert "简洁凝练" in prompt_review
        assert "华丽文风本身不是加分项" in prompt_review

    def test_review_backup_untouched(self):
        from app.prompts.creation.prompt_precreation import prompt_review_backup
        assert "简洁凝练" not in prompt_review_backup
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/services/test_slim_template_structure.py::TestPromptStep2AndReviewSlim -v`
Expected: 前 4 项 FAIL

- [ ] **Step 3: 修订 prompt_step2 与 prompt_review**

对 `app/prompts/creation/prompt_precreation.py` 做三处 Edit：

**Edit 3a — prompt_step2 填写说明第 3 条**，原文：

```
3、如果需要强调某些内容不得出现，请填写模板中的"Negative Prompt"字段中，注意，不要删除字段原有内容，在原有内容的基础上添加。
```

改为：

```
3、如果需要强调某些内容不得出现，请填写模板中的"Negative Prompt"字段中，注意，不要删除字段原有内容，在原有内容的基础上添加。添加前逐条比对正文：正文已正向声明的内容禁止写入 Negative；全字段合计保持 3-5 条高危名词短语，禁止 (word:1.3) 之类的权重语法。
```

**Edit 3b — prompt_step2 注意事项区**，在 `- **注意**，带有"固定"标签的字段，请严格遵守，不得修改。` 一行之后插入两行：

```
- **注意**，禁止文学抒情比喻、设计意图旁白（"传达出xx感"）、解剖学词汇（足弓/骨骼/关节结构）。
- **注意**，用户原始输入中的文学化描述是创意来源，禁止原样抄入，须转译为可直接绘制的视觉事实。
```

（注意：源文件中引号为中文全角引号“”，Edit 时以文件实际内容为准。）

**Edit 3c — prompt_review**，在 `**注意**，避免任何色情、软色情、暴力、低俗、不雅的用语，以免触发AI生成模型的审核机制。` 一行之前插入：

```
**简洁性偏好**：候选质量相近时，优先选择表述简洁凝练、无冗余修辞的候选；华丽文风本身不是加分项。
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/services/test_slim_template_structure.py tests/services/test_prompt_review_composition.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add app/prompts/creation/prompt_precreation.py tests/services/test_slim_template_structure.py
git commit -m "feat(creation): step2 Negative 收紧与去修辞，review 加简洁性偏好（规则4/5 + review 轻改）"
```

---

### Task 5: quick_create 发图前剥离机器码

**Files:**
- Modify: `app/services/creation_service/quick_create_service.py`（导入区 line 1-25；content 装配处约 line 341-346）
- Test: `tests/test_creation_quick_create.py`（追加 1 个测试）

**Interfaces:**
- Consumes: Task 1 的 `strip_machine_code(prompt: str) -> str`
- Produces: 无新接口；行为变化 = 发给 `generate_image_with_nano_banana_pro` 的 text 不再含机器码

**背景：** quick_create 把卡片的 fullPrompt 原文装进多模态 content 发给图像模型。现在 step1 产出的 fullPrompt 头部带 `[COMPOSITION_DECISION]` 块。剥离仅发生在装配 content 的这一处；`full_prompt` 变量的其他用途（存档 task_meta.json、图片评审 `_review_generated_image(creation_prompt=full_prompt)`）保持原样。

- [ ] **Step 1: 写失败测试**

在 `tests/test_creation_quick_create.py` 的 `TestQuickCreateService` 类中追加（放在 `test_quick_create_success` 之后；复用文件顶部已有的 `MOCK_REVIEW_USABLE_JSON` 与模块级辅助函数 `_create_five_standard_refs`）：

```python
    @patch("app.services.creation_service.quick_create_service.yibu_gemini_infer")
    @patch("app.services.creation_service.quick_create_service.generate_image_with_nano_banana_pro")
    def test_quick_create_strips_machine_code_before_send(
        self, mock_generate, mock_review_infer, db_session, temp_data_dir
    ):
        from app.repositories.creation_repository import CreationPromptPrecreationRepository
        from app.repositories.material_repository import MaterialCharacterRepository
        from app.services.creation_service.quick_create_service import QuickCreateService

        character_id = "mchar_qc_strip"
        MaterialCharacterRepository(db_session).create(
            {"id": character_id, "name": "测试角色"}
        )
        prepo = CreationPromptPrecreationRepository(db_session)
        task = prepo.create(
            character_id=character_id, seed_prompt="seed", n=1, status="completed"
        )
        full_prompt_with_code = (
            "**[COMPOSITION_DECISION]**\n"
            "aspect_ratio: 3:4\n"
            "shooting_angle: three_quarter\n"
            "\n"
            "**【固定】任务目标**：生成插画。\n"
        )
        prepo.update(task.id, {"status": "completed", "result_json": [{
            "id": "p1", "title": "t1", "preview": "pv1",
            "fullPrompt": full_prompt_with_code,
            "tags": [], "createdAt": "2026-01-01",
        }]})
        _create_five_standard_refs(character_id)
        mock_review_infer.return_value = MOCK_REVIEW_USABLE_JSON

        sent_texts = []

        def _ok(**kwargs):
            sent_texts.append(kwargs["Content"][0]["text"])
            os.makedirs(kwargs["output_path"], exist_ok=True)
            with open(os.path.join(kwargs["output_path"], kwargs["file_name"]), "wb") as f:
                f.write(b"img")
            return True

        mock_generate.side_effect = _ok

        service = QuickCreateService(db_session)
        start = service.start_quick_create(
            character_id=character_id,
            selected_prompts=[{"id": "p1", "fullPrompt": full_prompt_with_code}],
            n=1,
            aspect_ratio="1:1",
            background_tasks=None,
        )
        status = service.get_task_status(start["task_id"])
        assert status["status"] == "completed"
        assert sent_texts, "图像模型未收到任何文本"
        for text in sent_texts:
            assert "[COMPOSITION_DECISION]" not in text
            assert "aspect_ratio:" not in text
            assert "**【固定】任务目标**" in text
        # 存档保持原样（含机器码）
        qtask = service.quick_repo.get_by_id(start["task_id"])
        with open(os.path.join(qtask.work_dir, "task_meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        assert "[COMPOSITION_DECISION]" in meta["selected_prompts"][0]["fullPrompt"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_creation_quick_create.py::TestQuickCreateService::test_quick_create_strips_machine_code_before_send -v`
Expected: FAIL —— `assert "[COMPOSITION_DECISION]" not in text` 断言失败（当前原样发送）

- [ ] **Step 3: 最小实现**

在 `app/services/creation_service/quick_create_service.py`：

**导入**（与其他 `app.services` 导入放一起）：

```python
from app.services.creation_service.prompt_precreation_service import strip_machine_code
```

注意：`prompt_precreation_service` 不导入 `quick_create_service`，无循环导入风险（实现时用 `python -c "import app.services.creation_service.quick_create_service"` 验证一次）。

**content 装配处**（约 line 341），原文：

```python
            content = [
                {"text": full_prompt},
                {"text": "以下是角色参考图，作为你修补任务的重要参考"},
            ]
```

改为：

```python
            content = [
                {"text": strip_machine_code(full_prompt)},
                {"text": "以下是角色参考图，作为你修补任务的重要参考"},
            ]
```

- [ ] **Step 4: 跑测试确认通过 + 模块回归**

Run: `python -m pytest tests/test_creation_quick_create.py -v`
Expected: 全部 PASS（旧用例的 fullPrompt 不含机器码，`strip_machine_code` 幂等原样返回，不受影响）

- [ ] **Step 5: 提交**

```bash
git add app/services/creation_service/quick_create_service.py tests/test_creation_quick_create.py
git commit -m "feat(creation): quick_create 发图前剥离机器码，存档保持原样（规则6落地）"
```

---

### Task 6: exp001b 回归配置 + 全量测试 + 回归操作手册

**Files:**
- Create: `experiments/configs/exp001b.yaml`
- Create: `docs/superpowers/specs/2026-07-06-exp001b-regression-runbook.md`
- Test: 全量 `python -m pytest tests/ -q`

**Interfaces:**
- Consumes: 既有 `experiments/baseline_gen.py`（`run_baseline_gen` 走生产 `_build_step1_prompt` + `prompt_step2`，改造后模板自动生效）、`experiments/runner.py`、`experiments/fixtures/benchmark_v1.yaml`
- Produces: exp001b 配置与操作手册；无代码接口

**背景：** exp001b 是改造后生产链路的小批量回归（spec §6）：6 基准种子 × 1 份 Prompt 生成 → 人工抽查规则遵从 → 18 张出图 → 与 exp001 slim 组（人工改写版）并排对照 → 用户人工确认。生成与出图需调用真实 LLM/生图 API（生产环境执行），本任务只交付配置与手册，实际执行由用户按手册操作。

- [ ] **Step 1: 写 exp001b 配置**

创建 `experiments/configs/exp001b.yaml`：

```yaml
exp_id: exp001b
benchmark: experiments/fixtures/benchmark_v1.yaml
# regression 变体 = 改造后生产链路自动生成；slim 变体 = 复用 exp001 人工改写冻结件（对照）
variants: [slim, regression]
images_per_cell: 3
concurrency: 10
review_shuffle_seed: 20260706
```

- [ ] **Step 2: 验证配置可加载**

Run: `python -c "from experiments.config import load_experiment_config; print(load_experiment_config('experiments/configs/exp001b.yaml'))"`
Expected: 打印 `ExperimentConfig(exp_id='exp001b', ...)` 无异常

- [ ] **Step 3: 写回归操作手册**

创建 `docs/superpowers/specs/2026-07-06-exp001b-regression-runbook.md`，内容如下（```` 内为文件全文）：

````markdown
# exp001b 回归操作手册：slim 模板落地后的小批量验证

> 前置：本仓库 slim 落地 commit 序列已合入；生产环境已同步该代码。
> 目的：验证改造后 step1/step2 自动产出达到 exp001 人工改写 slim 版的水准（spec §6）。

## 1. 准备对照组（本地，一次性）

把 exp001 的 slim 冻结件复制为 exp001b 的 slim 变体（冻结语义，已存在则跳过）：

    mkdir -p experiments/variants/exp001b/slim
    cp experiments/variants/exp001/slim/*.txt experiments/variants/exp001b/slim/

## 2. 生成 regression 变体（生产环境）

用改造后的生产链路为 6 个基准种子各生成 1 份 Prompt：

    python -m experiments.baseline_gen --config experiments/configs/exp001b.yaml

注意：baseline_gen 固定写入 `experiments/variants/exp001b/baseline/`，生成完成后重命名目录：

    mv experiments/variants/exp001b/baseline experiments/variants/exp001b/regression

## 3. 人工抽查规则遵从（出图前的门槛）

逐份检查 6 个 regression Prompt：

- [ ] 字符数落在约 1400–2100 区间（slim 冻结件实测区间；明显超出说明瘦身指令未生效）
- [ ] 正文无 `[SHOOTING_ANGLE]` 等枚举回填行（头部 [COMPOSITION_DECISION] 决策块属正常，发图时代码层剥离）
- [ ] 锚点 3-5 条、每条单物件带“（见参考图）”、无五官描述
- [ ] 神态为白名单单一表情 + 视线方向
- [ ] 无文学抒情比喻 / 设计意图旁白 / 解剖学词汇
- [ ] Negative 3-5 条、与正文无矛盾、无权重语法

任何一条系统性不达标 → 回到模板措辞迭代，不进入出图。

## 4. 出图与对照（生产环境 + 本地）

    python -m experiments.runner --config experiments/configs/exp001b.yaml

注意：runner 直接发送变体文件全文，regression 变体头部的 [COMPOSITION_DECISION] 块
不会经过 quick_create 的剥离路径。出图前先手工删除各 regression .txt 头部的决策块段落，
保证与 slim 对照组同条件（slim 冻结件本来就无机器码）。

取回 `experiments/results/exp001b/` 后，参照 `experiments/results/exp001/_reveal.py`
生成并排对照页（slim 列 = exp001 人工改写版出图，regression 列 = 新链路出图）。

## 5. 判定

- 用户人工确认无回退 → slim 落地完成
- 系统性回退 → 区分“模板遵从性问题”（LLM 没照做 → 迭代模板措辞）
  与“规则本身问题”（自动链路下有副作用 → 回退该条规则）
- checker 自动指标可照跑，仍只作参考值（未校准）
````

- [ ] **Step 4: 全量测试回归**

Run: `python -m pytest tests/ -q`
Expected: 全部 PASS，无新增失败（重点关注 tests/services/ 与 tests/experiments/）

- [ ] **Step 5: 提交**

```bash
git add experiments/configs/exp001b.yaml docs/superpowers/specs/2026-07-06-exp001b-regression-runbook.md
git commit -m "feat(experiments): exp001b 回归配置与操作手册（slim 落地验证）"
```

---

## 完成定义

- Task 1-6 全部提交，`python -m pytest tests/ -q` 全绿
- exp001b 的实际执行（LLM 生成 + 出图 + 用户人工确认）按手册在生产环境进行，属落地验收而非本计划代码范围
