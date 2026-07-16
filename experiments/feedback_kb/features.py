"""full_prompt → 结构化特征提取（设计文档 §3/§8）。纯函数、无 IO、确定性。

三个入口：
- extract_composition: [COMPOSITION_DECISION] 键值块五维（subject_area_min 归一 float）
- split_sections: 按 `**标题**：` 固定标题切段
- detect_rules: 腿脚规则包 R1-R4/R6 措辞指纹（R5 为 step1 决策行为，恒 None 不可文本检测）
"""
import re

# `**[COMPOSITION_DECISION]**` 块后的 `key: value` 行，直到空行/下一段
_COMPOSITION_LINE = re.compile(r"^([a-z_]+):\s*(.+?)\s*$", re.M)

# 段落标题：行首 `**标题**：`（正文接在同行冒号后或下一行列表）
_SECTION_HEADER = re.compile(r"^\*\*(.+?)\*\*[：:]", re.M)

# ---- 规则包措辞指纹（来源：exp002 设计文档 §3 与 5c14c0c 落地模板措辞）----
# 已知假阴性风险：生产模板措辞微调时需同步本表（设计文档 §8）。
# R1 材质词黑名单：袜子/脚部相关段落不得出现光学-材料学词汇 → 指纹 = 黑名单词全部缺席
_R1_BLACKLIST = ("折射", "珠光", "透光率", "微孔", "丝线密度", "次表面散射", "莹润", "高透光")
# R2 袜口结构锚定：袜口 + 结构词（蕾丝/罗纹/缎带/荷叶边）至少其一
_R2_SOCK_CUFF = "袜口"
_R2_STRUCTURES = ("蕾丝", "罗纹", "缎带", "荷叶边")
# R3 脚趾防护：足尖圆润/弱化脚趾类防护措辞至少其一
_R3_PATTERNS = (
    re.compile(r"足尖[^。]{0,30}圆润"),
    re.compile(r"圆润[^。]{0,20}(足尖|脚趾)"),
    re.compile(r"弱化[^。]{0,20}脚趾"),
    re.compile(r"脚趾[^。]{0,10}的?(分离感|解剖线条)"),
)
# R6 Negative 腿脚保底：Negative 段含腿脚相关条目
_R6_NEGATIVE_TERMS = ("多肢", "脚趾", "袜", "多余的腿", "多余的双腿")

# 关注段落标题的匹配子串（标题带括号后缀，如「角色姿势（自然展示…）」，用包含匹配）
_POSE_KEY = "角色姿势"
_SOCK_FOOT_KEY = "脚部/袜子"
_OUTFIT_KEY = "角色服装"
_NEGATIVE_KEY = "Negative"


def extract_composition(full_prompt: str) -> dict:
    """抽取 [COMPOSITION_DECISION] 五维。缺块返回全 None；subject_area_min 归一为 float
    （兼容 `55%` 与 `0.55` 两种格式）。"""
    keys = ("aspect_ratio", "subject_area_min", "shooting_angle",
            "camera_height", "gaze_direction")
    out = {k: None for k in keys}
    head = full_prompt.split("**【固定】", 1)[0]  # 决策块在首个固定段之前
    if "[COMPOSITION_DECISION]" not in head:
        return out
    for key, value in _COMPOSITION_LINE.findall(head):
        if key not in out:
            continue
        if key == "subject_area_min":
            m = re.search(r"(\d+(?:\.\d+)?)\s*%?", value)
            if m:
                num = float(m.group(1))
                out[key] = round(num / 100, 4) if "%" in value or num > 1 else num
        else:
            out[key] = value
    return out


def split_sections(full_prompt: str) -> dict:
    """按 `**标题**：` 切段，返回 {标题: 正文}。标题保留原文（含括号后缀）。"""
    matches = list(_SECTION_HEADER.finditer(full_prompt))
    sections = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_prompt)
        sections[m.group(1).strip()] = full_prompt[m.end():end].strip()
    return sections


def _find_section(sections: dict, key: str) -> str:
    for title, body in sections.items():
        if key in title:
            return body
    return ""


def get_pose_text(full_prompt: str) -> str:
    """姿势段原文（LLM 打标输入；存 KB 供复核）。缺段返回空串。"""
    return _find_section(split_sections(full_prompt), _POSE_KEY)


def detect_rules(full_prompt: str) -> dict:
    """R1-R4/R6 指纹检测，返回 {R1..R6: bool|None}。R5 恒 None。
    段落缺失时相应规则记 False（模板未按预期出段本身就是不遵从信号）。"""
    sections = split_sections(full_prompt)
    sock = _find_section(sections, _SOCK_FOOT_KEY)
    outfit = _find_section(sections, _OUTFIT_KEY)
    negative = _find_section(sections, _NEGATIVE_KEY)
    sock_scope = sock + "\n" + outfit  # R1/R2 检查袜子相关描述所在的两段

    r1 = bool(sock) and not any(w in sock_scope for w in _R1_BLACKLIST)
    r2 = _R2_SOCK_CUFF in sock_scope and any(s in sock_scope for s in _R2_STRUCTURES)
    r3 = bool(sock) and any(p.search(sock) for p in _R3_PATTERNS)
    # R4 褶皱单处克制：袜子细节段"褶"出现 ≤2 次（一处描述常含"衣褶/褶皱"两词形）
    r4 = bool(sock) and sock.count("褶") <= 2
    r6 = any(t in negative for t in _R6_NEGATIVE_TERMS)
    return {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": None, "R6": r6}
