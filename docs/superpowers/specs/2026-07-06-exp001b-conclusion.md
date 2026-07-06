# exp001b 实验结论归档：slim 生产落地回归验证（slim 人工版 vs regression 新链路）

> 日期：2026-07-06
> 前置：`docs/superpowers/specs/2026-07-06-slim-prompt-production-design.md`（方案 A 落地，commit 序列 766368c..624b214）
> 操作手册：`docs/superpowers/specs/2026-07-06-exp001b-regression-runbook.md`
> 原始产物：`experiments/results/exp001b/`（gitignore，本地留存：manifest.json / prompts / images / reveal.html）

## 实验概况

- 目的：验证 slim 化后的生产链路（step1/step2 自动产出）达到 exp001 人工改写 slim 版水准
- 规模：2 变体 × 6 种子 × 3 张 = 36 张，全部 ok；同种子同参考图同画布
- slim 组 = exp001 人工改写冻结件出图（对照金标准）；regression 组 = 改造后生产链路自动产出

## 出图前规则遵从抽查（runbook §3）：通过

6 份 regression Prompt 全量扫描：

- 正文字符数 1595–1868，全部落在 1400–2100 区间
- 枚举回填行 6/6 为零，镜头段均以自然语言开头
- 锚点 4–5 条，全部单物件、≤8 字、带（见参考图）、无五官描述
- 神态主表情 6/6 命中白名单
- 文学修辞仅 cas_easy_window 2 处轻微泄漏，其余 5 份干净；解剖学词汇 6/6 为零
- Negative：5 份 5 条、1 份 6 条（cas_easy_window）；无权重语法。
  校准说明：「穿鞋/光脚」类条目在 slim 冻结件中 5/6 份同样存在（1 份达 7 条），
  属人工金标准自身惯例，不判为 regression 违规

## 实验条件不对称（均不利于 regression，已修复）

首轮执行时 runner 存在两个基建缺陷：

1. **机器码未剥离**：runner 原样发送变体全文，regression 组 6/6 带 [COMPOSITION_DECISION]
   决策块出图（runbook 手工剥离步骤被跳过）；slim 冻结件本身无机器码
2. **画幅错位**：runner 画布强取 benchmark，而新链路 step1 自主决策画幅，3/6 种子正文
   声明与实际画布打架（cas_easy_window 文 16:9 渲 3:4、cas_hard_wsit 文 3:4 渲 4:3、
   hys_hard_bubble 文 3:4 渲 16:9）；slim 组 6/6 一致

两者都朝不利于 regression 的方向偏——regression 在更苛刻条件下参赛。

**修复（本次落盘）**：`experiments/runner.py` 新增 `resolve_send_inputs`——发送前
`strip_machine_code`，画幅优先跟随决策块 aspect_ratio（镜像生产语义），存档保持原样；
runbook §4 已同步，后续实验不再需要手工处理。
生产链路本就无此二问题（`quick_create_service.py:343` 发图前剥离；`:356-364` auto 画幅
跟随 step1 决策），实验伪影不影响生产正确性。

## 最终判定（用户定论）

**regression 出图效果未显著劣于 slim 人工版 → regression 采纳为正式版本，slim 落地完成。**
且因两项不利条件的存在，"无回退"结论更稳（苛刻条件下仍持平）。

## 遗留问题（待后续版本）

1. cas_easy_window 一份质量偏弱：Negative 6 条超上限、2 处修辞泄漏（"增添一丝自然生机"
   "体现轻盈空灵感"）、神态段视线描述（"穿过镜头注视上方"）与决策块 to_camera 有歧义
2. 神态段视线描述偶带修辞（"温柔而安静地""满含温情"），白名单只约束了主表情
3. 个别生造词/重字笔误（"微米粒子""自然自然"），LLM 语义漂移
4. Negative 与正文正向声明的重复（"穿鞋"类）——slim 金标准自身同款，若要收紧需连
   good_template 一起改，属规则迭代而非遵从问题
5. checker 校准仍是欠账（本轮未跑自动指标）
6. 第二阶段主目标不变：腿脚崩坏专项（exp001 结论 §对第二阶段的输入）
