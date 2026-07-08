# experiments/ — 出图质量 A/B 实验层

创作模块（美图创作）Prompt 优化的实验基础设施。核心思想：**生产真实出图数据 + 用户人工
feedback 是优化的唯一核心依据**——每轮优化都以 A/B 实验验证，评判以人工盲评为决定性
标准，结果归档为结构化 Case 供跨轮分析。

本文档是下一次实验的操作参考：按「实验生命周期」一节从头走一遍即可复现当前流程。

## 已完成实验索引

| 实验 | 变量 | 结论 | 结论文档 |
|---|---|---|---|
| exp001 | Prompt 瘦身 6 规则（baseline vs slim） | 采纳 slim 为新基准 | `docs/superpowers/specs/2026-07-06-exp001-conclusion.md` |
| exp001b | slim 生产落地回归 | 回归通过 | `docs/superpowers/specs/2026-07-06-exp001b-conclusion.md` |
| exp002 | 腿脚规则包 R1-R6（control vs rulepack） | 采纳规则包，合入 main | `docs/superpowers/specs/2026-07-08-exp002-conclusion.md` |

历次实验的运行手册（含当轮特有细节）也在 `docs/superpowers/specs/` 下，命名
`YYYY-MM-DD-expNNN-runbook.md`。新实验建议照此惯例写一份 runbook 再开跑。

## 目录结构

```
experiments/
├── config.py           # 实验配置/benchmark 的加载与校验
├── layout.py           # results 目录布局唯一事实源（所有工具从这里取路径）
├── baseline_gen.py     # 走生产链路生成变体 Prompt（对已存在文件跳过 = 冻结语义）
├── runner.py           # 批量出图（断点续跑，产出 manifest.json）
├── checker/            # 自动指标（结构检查 + 锚点保留），需校准后才可采信
├── report.py           # metrics / review（盲评页）/ reveal（揭盲页）/ final（合流报告）
├── casebank/           # Case 结构化格式、归档、聚合分析、taxonomy
├── configs/            # 实验定义 expNNN.yaml（exp_id、benchmark、变体、张数、乱序种子）
├── fixtures/           # benchmark_vN.yaml（种子集，冻结）+ anchors/（角色锚点清单）
├── variants/           # 各实验冻结的变体 Prompt（git 提交后永不再编辑）
├── cases/              # ★ Case 库统一归档路径（见下）+ taxonomy.yaml
└── results/            # 运行产物（gitignore，本地留存）
```

### Case 库（`experiments/cases/`）

所有实验与手工收集的 Case 统一放在这一个目录下，一个来源一个 `*_cases.txt` 文件，
格式见 `casebank/case_format.py`（`[meta]` + seed_prompt + final_prompt + feed_back
三段式）。当前内容：

- `manual_0706_cases.txt` — 2026-07-06 手工收集的生产正负样例（优化起点，7 Case）
- `exp002_cases.txt` — exp002 盲评归档（24 Case）
- `taxonomy.yaml` — 崩坏模式两层 tag 词典（当前 v2）
- `CASE_NOTES.md` — Case 库关键信息：遗留问题、原因猜测、下阶段建议

聚合分析一条命令扫全库：

```bash
python -m experiments.casebank.case_analyze --cases-dir experiments/cases
```

**不可回改原则**：Case 的三段原文与已定稿的 tags/taxonomy_version 永不回改；新一轮
只允许新增文件/新增 Case。taxonomy 只增不删，新子 tag 须经用户确认后 bump version。

## 实验生命周期（以 exp002 为范本）

约定：所有命令从仓库根运行（依赖 `app.*` 导入与 gitignore 的 `app/tools/llm/config.py`）。
生成 Prompt 与出图在**生产环境**执行（默认配置即生产模式，角色目录 `data/material/characters`，
无需环境变量；仅本地用生产拷贝调试时才设置 `MATERIAL_CHARACTERS_DIR`）。盲评与归档在本地执行。

### 0. 定义实验（本地）

1. 明确变量：一次只验证一包变化（如一组模板规则），提前写清判定标准（预注册，先于看数据承诺）。
2. 基准集：复用 `fixtures/benchmark_vN.yaml` 或新建。种子草案须经用户审定后冻结；
   种子文本一旦冻结不再修改（连续性豁免的缺陷也保留，如 hys_hard_bubble 无袜子描述）。
   难度分层 hard/medium/easy——**注意天花板效应**：广覆盖基准会稀释高危场景
   （exp002 control 崩坏率仅 8.3%，远低于 exp001 的 ~22%），要检出增益需富集 hard 种子。
3. 写 `configs/expNNN.yaml`（exp_id、benchmark 路径、变体名列表、images_per_seed、
   review_shuffle_seed）与 runbook 文档。
4. 规模参考：120 张在低崩坏率下 Fisher 检验力不足，判定以人工揭盲对比为决定性依据；
   想要统计显著需加大规模或富集 hard。

### 1. 生成并冻结变体 Prompt（生产环境）

`baseline_gen` 走生产链路读 `app/prompts/creation/*` 生成，一个变体跑一次；对照组
用 git 把模板切回旧状态再生成（详细命令见 exp002 runbook §1）：

```bash
python -m experiments.baseline_gen --config experiments/configs/expNNN.yaml
mv experiments/variants/expNNN/baseline experiments/variants/expNNN/<变体名>
```

冻结语义：baseline_gen 对已存在文件跳过。两变体全部生成后 **git 提交冻结，之后永不编辑**。

### 2. 出图前遵从性抽查（门槛）

逐份检查新变体 Prompt 是否真的体现了本轮变量（exp002 的六条检查单见 runbook §2）。
系统性不达标 → 回去迭代模板措辞，不进入出图——出图很贵，别为不合格的 Prompt 花钱。

### 3. 出图（生产环境）

```bash
python -m experiments.runner --config experiments/configs/expNNN.yaml
```

并发 ≤ 10；中断后重跑自动续。runner 发送前自动剥离 COMPOSITION_DECISION 决策块、
画幅跟随各变体决策块。产出 `results/expNNN/images/` 与 `manifest.json`。

### 4. 自动指标（可选，仅参考）

checker 依赖角色 anchors 清单（`fixtures/anchors/`，目前仅 castorice/hysilens 有）
且**未经校准的结果不可采信**（exp001 教训：锚点自动指标与盲评矛盾）。新角色没建
anchors 时不要跑 `run_checks`（会因缺键报错）。跑了 checker 才有意义执行
`report metrics`。人工盲评始终是决定性标准。

### 5. 盲评（本地）

把 `results/expNNN/` 整目录打包拷回本地（**注意**：解包后确认没有多套一层同名目录，
`manifest.json` 应位于 `experiments/results/expNNN/manifest.json`）。

```bash
python -m experiments.report review --config experiments/configs/expNNN.yaml
```

浏览器打开 `results/expNNN/review.html`：图片已乱序匿名（变体不可见），逐图对
脸部/锚点/腿脚袜三组打分并在备注栏写具体问题（自由文本，之后会成为 Case 的 feedback）。

- 进度实时自动保存在浏览器 localStorage（按实验 ID 隔离），可关页分多次评完；
  换浏览器/机器时先「导出评分 JSON」再在新环境「导入评分 JSON」续评。
- **每张图都要评满三组**——未评的图会稀释统计分母。
- 盲评期间不要打开 `review_key.json`（揭盲钥匙）。
- 评完点「导出评分 JSON」，把下载的文件手动移动到 `experiments/results/expNNN/ratings.json`。

### 6. 揭盲对比（本地，决定性判据）

```bash
python -m experiments.report reveal --config experiments/configs/expNNN.yaml
```

打开 `results/expNNN/reveal.html`：按种子分组、变体并排、回显盲评评分与备注，
难度 hard→easy 排序。用户逐种子对比给出最终观感结论——三档盲评粒度捕捉不到的
美观性差异（exp001 的 slim 优势就是在这一步确认的）在这里定论。

（如需数字合流报告：`python -m experiments.report final --config ... --ratings <ratings.json>`）

### 7. 归档为结构化 Case（本地，揭盲后）

先校验 ratings.json 确实在目标路径——`case_archive` 对缺失文件**静默**按无评分处理，
会产出全 `bad=0` 的假数据：

```powershell
if (-not (Test-Path experiments/results/expNNN/ratings.json)) { "缺 ratings.json" }
```

归档（单行命令，路径按实验替换）：

```bash
python -c "from experiments.config import load_benchmark; from experiments.layout import ExpLayout; from experiments.casebank.case_archive import archive_experiment; lay=ExpLayout('experiments/results','expNNN'); bench=load_benchmark('experiments/fixtures/benchmark_vN.yaml'); archive_experiment(lay, bench, source='expNNN', out_path='experiments/cases/expNNN_cases.txt', date='YYYY-MM-DD', ratings_path='experiments/results/expNNN/ratings.json', key_path='experiments/results/expNNN/review_key.json')"
```

产出每 (变体, 种子) 一个 Case：`bad` = 腿脚 broken 计数，feedback = 盲评备注拼接。
然后逐 Case 复核 feedback、按 `cases/taxonomy.yaml` 填 tags；词典覆盖不了的现象
先填 `其他/未分类` 占位，提议新子 tag，**经用户确认后** bump taxonomy version 并
回填占位（仅限定稿前的占位可回填）。

### 8. 聚合分析、判定与收尾（本地）

```bash
python -m experiments.casebank.case_analyze --cases-dir experiments/cases
```

看 `by_variant`/`by_difficulty_variant` 的 `bad_rate` 与 `tag_freq_parent`（残余崩坏
模式分布）。判定框架：

- 对照预注册标准 + 用户揭盲观感定论（人工为决定性，自动指标仅参考）。
- 区分**模板遵从性问题**（LLM 没照做 → 迭代措辞重跑）与**规则本身问题**
  （规则有副作用 → 回退该条规则）。
- 单种子单轮的异常**不立案**，记为观察项；复现则走 B 线单规则消融。
- 无效或回退：`git revert <规则包 commit>`，Case 数据保留供后续分析。

收尾清单：结论文档写入 `docs/superpowers/specs/YYYY-MM-DD-expNNN-conclusion.md`
（含观察项、对下一轮的输入）；更新 `cases/CASE_NOTES.md`；采纳则合入 main。

## 关键要点（历史教训汇总）

1. **人工评判为决定性标准**，checker 未校准不可采信；盲评匿名乱序保证有效性。
2. **一切冻结物不可编辑**：benchmark 种子文本、variants/ 下已提交的 Prompt、
   Case 原文与已定稿 tags。发现冻结物有缺陷 → 记录，下一轮经用户批准后处理。
3. **腿脚自然展示第一原则**：任何优化不得靠藏脚/减少腿脚出镜来降崩坏率。
4. **每轮实验必须预留人工 feedback 空间**并归档为结构化 Case（本文件 §7），
   这是跨轮分析机制的数据基础。
5. `report.py` 的 `delta_pp` 只认 `baseline`/`slim` 变体名，其他变体名时该字段恒空，
   忽略即可（遗留问题）。
6. 生产/本地环境差异：生产默认配置直接跑；结果目录拷回本地时留意嵌套目录。
7. Negative Prompt 条数上限（3-5 条）目前靠模板软约束，存在对称性超限漂移，
   不影响 A/B 公平但属加固候选项。
