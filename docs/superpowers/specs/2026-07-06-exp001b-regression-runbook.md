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

runner 发送前自动剥离 [COMPOSITION_DECISION] 决策块（`strip_machine_code`），画幅优先
跟随变体决策块的 aspect_ratio、无决策块时取 benchmark（`resolve_send_inputs`，镜像
生产语义）。无需手工处理变体文件。
（注：exp001b 首轮执行时 runner 尚无此能力，regression 组曾带机器码出图且 3/6 种子
画幅与正文声明错位——两者均不利于 regression，判定结论因此更稳，详见结论归档。）

取回 `experiments/results/exp001b/` 后，参照 `experiments/results/exp001b/exp001b/_reveal.py`
生成并排对照页（slim 列 = exp001 人工改写版出图，regression 列 = 新链路出图）。

## 5. 判定

- 用户人工确认无回退 → slim 落地完成
- 系统性回退 → 区分“模板遵从性问题”（LLM 没照做 → 迭代模板措辞）
  与“规则本身问题”（自动链路下有副作用 → 回退该条规则）
- checker 自动指标可照跑，仍只作参考值（未校准）
