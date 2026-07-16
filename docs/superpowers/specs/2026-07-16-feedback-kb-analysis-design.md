# 生产 Feedback 知识库与关联分析机制 — 设计文档

日期：2026-07-16
状态：已批准（用户确认 C 底座 + A 核心 + B 顺带的优先级、乙-乙-乙-方式一四项路线决策与三项细节拍板）
> **归因层已被取代**：本文的"Prompt 特征（配置维度）× 崩坏关联分析"方向经首份报告实证后
> 被用户判定错误，归因层重构为词汇层假说闭环，见
> `2026-07-16-feedback-kb-lexical-attribution-redesign.md`。知识库底座、紧迫度排行榜、
> 版本时间线、守门阈值等其余部分继续有效。
背景：生产 feedback 数据规模持续增长（85 归档 case / 255 图，跨三批导出），当前使用方式
是把 feedback 与产线数据整体喂给 LLM 做一次性分析、产出手工 `CASE_NOTES.md` 快照。依据
[feedback-case-data-first] 原则，需要一个逻辑自洽、高效的机制：从 feedback 中提取有效信息，
持续优化 Prompt 与工作流。

## 需求与决策（用户已确认）

1. **目标优先级**：C 持久知识库=底座；A 优化点识别 + 优化/AB 方案=核心目的；B 趋势监控=顺带
   （本轮只算不展示）。本轮锚定"知识库 + 带证据的分析报告"，**LLM 开方（生成优化假设）留在
   人机对话层，不写进代码**。
2. **归因走关联分析**（选项乙）：代码对比崩坏 vs 未崩 case 的 Prompt 特征分布，产出有证据的
   关联结论（如"脚部简陋在侧卧/盘腿姿势出现率 70%、坐姿仅 10%"）；LLM/人基于证据开方。
3. **版本锚定用时间戳近似**（方式一）：手动维护"Prompt 版本时间线"，case 按 `created_at`
   落区间推断版本归属（标记为推断），接受不精确；方式二（出图链路落版本指纹）本轮不做。
4. **特征提取 = 结构化特征 + LLM 姿势族标签**（选项乙）：COMPOSITION 五维与规则包指纹靠正则
   免费提取；姿势族由 LLM 对"角色姿势"段打一个枚举标签，每 case 一次、结果永久缓存。
5. **v1 导出完全排除**：知识库只摄入 schema=`aetherframe_feedback_v2` 的导出（用户拍板）。
6. **小样本诚实优先**：守门阈值不放宽（N_min=8），接受早期产出为"排行榜 + 少数强关联 +
   大量待积累项"。

## 数据现实（探索确认）

- 首批导出 `feedback_export_20260709-1630.json` 是 schema v1（无 tag/severity）→ 不进知识库；
  其 25 个归档 case 仍在 `production_cases.txt` 供人读。
- v2 的 `tag_config` 原始 key 粒度比崩坏 taxonomy 细（`pose_weird`/`face_collapse` 等都映射进
  「其他/未分类」）→ 知识库必须**存原始 tag key**，taxonomy 映射在分析时动态算，v3 扩词典后
  无需重建库。
- COMPOSITION 中 `shooting_angle`（80/87 = three_quarter）与 `camera_height`（79/87 =
  slight_down）几乎无方差，**不作关联特征**；有方差维度 = `aspect_ratio`、`gaze_direction`、
  姿势族。`subject_area_min` 有 `55%` 与 `0.55` 两种格式，归一为 float。
- 图片在 prompt 组内强相关（存在 9/9 全崩）→ **统计单元取 case 级**，防单种子连崩伪造关联。
- R5（极端姿势退避）是 step1 决策行为、不可从最终 Prompt 文本检测 → 恒 `null`；R1-R4/R6
  可用模板措辞指纹检测。
- 跨导出去重键 `(quick_create_task_id, prompt_index)`（case 级）可行。
- 链路测试记录 `qcreate_3808a8be9915` 按 CASE_NOTES 既有约定不归档 → 知识库同样排除。

## 1. 架构总览

```
导出 JSON (feedbacks/*.json, 仅 v2) ──┐
版本时间线 (prompt_versions.yaml) ────┤ [1] kb_build（确定性 + 一次性 LLM 姿势打标）
姿势 taxonomy (pose_taxonomy.yaml) ───┘        ↓
                        知识库 feature_kb.jsonl（增量、幂等、一 case 一行）
                                               ↓
              [2] rank 紧迫度排行榜   [3] correlate 特征×崩坏关联   [4] trend（只入公式）
                                               ↓
                        [5] report → 带证据的分析报告（JSON + Markdown）
                                               ↓
                            人机对话层：开方（优化假设 + A/B 变量）
```

[1] 构建、[2-5] 分析汇总全部确定性；唯一 LLM 调用是 [1] 的姿势打标（每 case 一次、缓存命中
跳过）。

## 2. 模块清单

新目录 `experiments/feedback_kb/`（与 casebank/ 平级；崩坏 tag 归一复用 `casebank/taxonomy.py`）：

| 模块 | 职责 | 关键接口 |
|---|---|---|
| `versions.py` + `experiments/cases/prompt_versions.yaml` | 版本时间线加载与推断 | `load_versions`；`infer_version(created_at) -> str` |
| `pose_taxonomy.py` + `experiments/cases/pose_taxonomy.yaml` | 姿势族字典，只增不改 + aliases | `load_pose_taxonomy`；`normalize`；`is_valid` |
| `features.py` | full_prompt → 结构化特征（纯函数无 IO） | `extract_composition`；`detect_rules`；`split_sections` |
| `pose_tagger.py` | 姿势段 → LLM 单标签；枚举校验、`other` 兜底；LLM 不可用时降级 `null` 待补 | `tag_pose(pose_text) -> str`（复用 `app/tools/llm/yibu_llm_infer`） |
| `kb_build.py` | CLI：遍历导出、组装 case 行、`case_key` upsert 幂等 | `python -m experiments.feedback_kb.kb_build` |
| `kb_query.py` | 加载 + 检索原语（按 tag/版本/姿势/角色过滤） | `load_kb`；`filter_cases` |
| `rank.py` | 紧迫度 = 频次×严重度×趋势 | `rank_modes(kb, versions)` |
| `correlate.py` | RR + 四道守门 + 置信标注 | `correlate(kb, mode, dim)` |
| `report.py` | CLI：汇总为 JSON+Markdown 报告 | `python -m experiments.feedback_kb.report` |

## 3. 知识库 schema（`experiments/cases/feature_kb.jsonl`）

一行一 case（= quick_create_task × prompt_group，与归档 case 同粒度）：

```jsonc
{
  "case_key": "qc_10856785a168__p0",          // 主键 = qc hex 段 + prompt_index
  "case_id": "Case_prod_20260713_10856785_0", // 按 07-08 spec §4 规则派生，对齐 case txt
  "exported_from": "feedback_export_20260716-0001.json",
  "created_at": "2026-07-13T15:48:42",
  "version_inferred": "rulepack",
  "character_id": "mchar_1a89122be6", "character_name": "Sandrone",
  "seed_id": "seed-...", "seed_text": "...",
  "composition": {"aspect_ratio": "3:4", "subject_area_min": 0.65,
                   "shooting_angle": "three_quarter", "camera_height": "slight_down",
                   "gaze_direction": "to_camera"},
  "rules": {"R1": true, "R2": true, "R3": true, "R4": true, "R5": null, "R6": true},
  "pose_family": "sit_kneel",                  // LLM 打标 + 缓存；失败/未打为 null
  "pose_text": "角色在茶几旁...半蹲...",        // 打标输入原文，供复核/重打
  "total_images": 3, "bad": 3,
  "images": [{"image_index": 0, "leg_foot_bad": true,
               "tag_keys": ["foot_exaggerated"], "severities": ["严重"],
               "feedback_text": ""}]
}
```

- 存原始 `tag_keys`（severity 与之对齐，per-image 保留）；taxonomy 映射分析时动态算。
- `version_inferred`/`case_id` 为派生字段，重建即重算（幂等）。
- 增量：`kb_build` 以 `case_key` upsert；已有行且 `pose_text` 未变 → 跳过 LLM。

## 4. 关联分析统计方法（防噪声核心）

统计单元 = case 级。指标 = 相对风险 `RR(M, D=v) = P(M|D=v) / P(M|D≠v)`，恒随附两侧原始
分子/分母（如 "sit_kneel: 7/10 vs 其他 3/50"）。四道守门：

1. **最小样本**：任一格 case 数 < **N_min=8** → 不出 RR，标 `insufficient`。
2. **单种子驱动检测**：某分组崩坏信号 ≥60% 来自同一 seed_id → 标 `疑单种子驱动`。
3. **多重比较收敛**：只对紧迫度 Top-K（**K=5**）模式 × 有方差维度（aspect_ratio /
   gaze_direction / pose_family）做检验；报告显式列出本次检验组数。
4. **置信三档**：`strong` / `weak` / `insufficient`；措辞统一为"值得作为归因假设验证"，
   不下因果结论。

零对照分母（P(M|D≠v)=0）不做 Haldane 修正，直接标 `无对照样本`（更诚实）。
报告每张表标注有效分母。

## 5. 紧迫度排序公式

对每个崩坏模式 M（taxonomy 父类或子类聚合）：

```
urgency(M) = freq(M) × severity_weight(M) × trend_factor(M)
```

- `freq` = 出现 M 的 case 数（case 级去重）。
- `severity_weight` = severity 均值（轻微=1 / 中等=2 / 严重=3）。
- `trend_factor` = 最新版本崩坏率 / 上一版本崩坏率，clamp [0.5, 2.0]；版本样本不足取 1.0。
  **本轮 trend 只参与排序与排行榜行内展示，不单列趋势章节**（B 只算不展示）。

## 6. 姿势 taxonomy 首版（v1）

单层枚举 + aliases，只增不改（新族经用户确认后 bump version）：
`sit_normal / sit_crosslegged / sit_kneel（跪坐+半蹲）/ lie_side / lie_prone /
lie_supine / recline_lean / stand / other（兜底，触发人工复核提议新族）`。
粒度取舍：~8 族 + 兜底——更细稀释小样本，更粗丢因果分辨力。

## 7. 版本时间线首版

`experiments/cases/prompt_versions.yaml`，时间取 git 提交（近似，可手动修正）：
`pre_slim（起始）→ slim（2026-07-06 15:33，commit 624b214 终审）→ rulepack
（2026-07-07 19:06，commit 5c14c0c + cf51075 终审）`。此后每次生产 Prompt 更新手动追加一行。

## 8. 规则指纹定义（R1-R4/R6，措辞来源 exp002 设计 §3）

集中定义在 `features.py` 一处常量：R1=袜子/脚部段无光学物理词（折射/珠光/透光率/微孔/
丝线密度/次表面散射/莹润）；R2=袜口 + 结构词（蕾丝/罗纹/缎带）；R3=足尖圆润/弱化脚趾类
防护措辞；R4=袜子细节段褶皱描述 ≤1 处；R6=Negative 段含腿脚保底条目（多肢/脚趾/袜）。
R5 恒 `null`（决策行为不可文本检测）。已知假阴性风险：模板措辞微调需同步指纹。

## 9. 端到端流程

```bash
# 维护：Prompt 更新时手动追加 prompt_versions.yaml
python -m experiments.feedback_kb.kb_build --feedbacks-dir experiments/feedbacks --kb experiments/cases/feature_kb.jsonl
python -m experiments.feedback_kb.report --kb experiments/cases/feature_kb.jsonl --versions experiments/cases/prompt_versions.yaml --out experiments/results/feedback_report_YYYYMMDD.md
# 人工：读报告 → 人机对话开方 → 产出下一轮 exp0NN configs/runbook（走现有实验生命周期）
```

## 10. 集成点

- 复用 `casebank/taxonomy.py`（tag 归一）、`app/tools/llm/yibu_llm_infer.py`（姿势打标）；
  rank/correlate 与 `case_analyze.py` 的 case 级口径同构。
- 数据源=导出 JSON（保留 severity/per-image），不从 case txt 反解析；`case_id` 互指交叉引用。
- 不改归档管线：`production_cases.txt` 仍是人读正本，`feature_kb.jsonl` 是机读分析底座。

## 11. 明确不做（YAGNI）

- 不做 B 趋势独立章节/仪表盘 UI（trend 只入公式与行内）；
- 不做 LLM 开方固化（留人机对话层）；
- 不做方式二版本指纹（改链路+schema v3）；
- 不摄入 v1 导出；不在本轮 bump 崩坏 taxonomy v3（存原始 key 已为其留路）；
- 不做姿势打标多轮投票；不做 watch/自动调度。

## 12. 测试

- `features.py`：对 v2 两份导出全部 61 group 断言五维齐全、`subject_area_min` 双格式归一、
  切段无异常（fixture 取真实导出样本片段）。
- `kb_build`：幂等（连跑两次第二次零 LLM 调用、内容不变）；v1 文件跳过并提示；
  `case_key` 无重复；链路测试记录被排除。
- `correlate`：构造小样本断言 `<N_min` 标 insufficient、单种子连崩标疑单种子驱动、
  零对照标无对照样本。
- 端到端：真实数据跑 kb_build + report，排行榜 Top 项与 CASE_NOTES 已知结论（脚部/简陋、
  腿部/结构错误、其他/未分类高频）方向一致作旁证。

## 13. 风险

1. 小样本天花板（v2 约 60 case）：多数细分落"证据不足"，已确认接受，价值随数据积累增长。
2. 版本时间线人工维护：漏记/记错污染 trend；yaml 带 commit 参照，评审对照 `git log app/prompts/`。
3. 姿势打标一致性：边界姿势不稳；`other` 兜底 + `pose_text` 留存抽查重打，首批人工抽查校准。
4. 规则指纹假阴性：指纹集中一处常量 + 来源注释，模板改动时同步。
