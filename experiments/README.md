# experiments/ — 出图质量 A/B 实验层

设计文档：`docs/superpowers/specs/2026-07-05-creation-prompt-ab-experiment-design.md`

## exp001 完整操作顺序（生产环境执行 1–4，本地执行 5–7）

1. checker 校准（首次）：准备校准集 YAML（历史崩坏/正常图 + 真值标注）后
   `python -m experiments.checker.calibrate --calib <calib.yaml> --out experiments/results/calibration_report.json`
   不达标项（如多腿检出 < 90%）降级人工评判。
2. 基线冻结：`python -m experiments.baseline_gen --config experiments/configs/exp001.yaml`
   产物 `experiments/variants/exp001/baseline/*.txt` 需 git 提交；瘦身版由人工改写后放入
   `experiments/variants/exp001/slim/`（同名文件），经用户过目后提交。
3. 出图：`python -m experiments.runner --config experiments/configs/exp001.yaml`
   （并发 ≤ 10；中断后重跑自动续）
4. 核对：`python -m experiments.checker.run_checks --config experiments/configs/exp001.yaml`
5. 把 `experiments/results/exp001/` 整目录打包拷回本地。
6. 本地：`python -m experiments.report metrics --config ...` →
   `python -m experiments.report review --config ...` → 浏览器打开 review.html 盲评并导出 ratings.json
   （盲评期间不要打开 review_key.json）。（请对每张图完成全部三组评分再导出——未评分的图会计入分母稀释比例）
7. 合流：`python -m experiments.report final --config ... --ratings <ratings.json>`
   → `final_report.md` 对照预注册标准定论。

所有命令从仓库根运行（依赖 `app.*` 导入与 `app/tools/llm/config.py`）。
