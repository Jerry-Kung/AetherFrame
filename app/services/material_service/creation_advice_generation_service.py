"""【已弃用】旧创作建议生成 Pipeline。

新代码请使用：
- creative_direction_generation_service.run_creative_direction_task
- seed_prompt_generation_service.run_seed_prompt_task

本文件保留为 deprecation stub，避免外部历史日志/链接失效。
"""


def _deprecated(*args, **kwargs):
    raise NotImplementedError(
        "creation_advice_generation_service is deprecated; "
        "use creative_direction_generation_service + seed_prompt_generation_service"
    )


run_creation_advice_pipeline = _deprecated
load_chara_profile_prerequisite_contents = _deprecated
parse_seed_prompt_llm_json = _deprecated
STEP_CREATION_ADVICE = "creation_advice"
STEP_CREATION_SEED = "creation_seed"
