"""Case 文本格式（设计文档 §2.1）解析/序列化。一批多 Case 存一个文件，与
experiments/cases 现行手工样例结构兼容，另加 [meta] 结构化头部与 tags。"""
from dataclasses import dataclass, field

_META_INT = ("images", "bad")
_SECTIONS = ("[meta]", "[seed_prompt]", "[final_prompt]", "[feed_back]")


@dataclass
class Case:
    case_id: str
    date: str
    source: str
    character: str
    seed_id: str
    difficulty: str
    variant: str
    images: int
    bad: int
    tags: list = field(default_factory=list)
    taxonomy_version: str = "v1"
    seed_prompt: str = ""
    final_prompt: str = ""
    feedback: str = ""


def _fmt_tags(tags: list) -> str:
    return "[" + ", ".join(tags) + "]"


def _parse_tags(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def serialize_cases(cases: list) -> str:
    blocks = []
    for c in cases:
        blocks.append(
            f"{c.case_id}:\n"
            "[meta]\n"
            f"date: {c.date}\n"
            f"source: {c.source}\n"
            f"character: {c.character}\n"
            f"seed_id: {c.seed_id}\n"
            f"difficulty: {c.difficulty}\n"
            f"variant: {c.variant}\n"
            f"images: {c.images}\n"
            f"bad: {c.bad}\n"
            f"tags: {_fmt_tags(c.tags)}\n"
            f"taxonomy_version: {c.taxonomy_version}\n"
            "[seed_prompt]\n"
            f"{c.seed_prompt}\n"
            "[final_prompt]\n"
            f"{c.final_prompt}\n"
            "[feed_back]\n"
            f"{c.feedback}\n"
        )
    return "\n".join(blocks)


def _split_case_chunks(text: str) -> list:
    """按 `Xxx:` 且下一非空行为 [meta] 的行切块，返回 [(case_id, body_lines)]。"""
    lines = text.splitlines()
    chunks = []
    cur_id = None
    cur = []
    for i, line in enumerate(lines):
        is_header = (
            line.endswith(":")
            and not line.startswith("[")
            and i + 1 < len(lines)
            and lines[i + 1].strip() == "[meta]"
        )
        if is_header:
            if cur_id is not None:
                chunks.append((cur_id, cur))
            cur_id = line[:-1].strip()
            cur = []
        elif cur_id is not None:
            cur.append(line)
    if cur_id is not None:
        chunks.append((cur_id, cur))
    return chunks


def _section_map(body_lines: list) -> dict:
    """把 body 行按 [meta]/[seed_prompt]/[final_prompt]/[feed_back] 分段。"""
    out = {}
    cur = None
    for line in body_lines:
        if line.strip() in _SECTIONS:
            cur = line.strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def parse_cases(text: str) -> list:
    cases = []
    for case_id, body in _split_case_chunks(text):
        sec = _section_map(body)
        meta = {}
        for line in sec.get("[meta]", []):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        # 正文段末尾会多一个 serialize 时补的换行，rstrip 一个尾随空行
        def _text(name):
            seg = sec.get(name, [])
            while seg and seg[-1] == "":
                seg = seg[:-1]
            return "\n".join(seg)
        cases.append(Case(
            case_id=case_id,
            date=meta.get("date", ""),
            source=meta.get("source", ""),
            character=meta.get("character", ""),
            seed_id=meta.get("seed_id", ""),
            difficulty=meta.get("difficulty", ""),
            variant=meta.get("variant", ""),
            images=int(meta.get("images", 0)),
            bad=int(meta.get("bad", 0)),
            tags=_parse_tags(meta.get("tags", "[]")),
            taxonomy_version=meta.get("taxonomy_version", "v1"),
            seed_prompt=_text("[seed_prompt]"),
            final_prompt=_text("[final_prompt]"),
            feedback=_text("[feed_back]"),
        ))
    return cases
