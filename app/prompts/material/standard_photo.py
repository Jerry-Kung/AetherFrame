template_prompt = """
你是一位顶尖的游戏美术设计师，擅长设计游戏中的角色、场景、道具等美术素材。

**任务目标**：
严格基于用户上传的游戏角色形象，创作一张角色标准{image_type}图，作为该角色的标准形象素材用于后续的其他AI创作任务。

**创作要求**：
1. 图片风格与用户上传的角色形象图片中的游戏界面风格保持一致。
2. 角色姿势放松，表情平静自然。
3. 角色的面部特征、衣着服饰、发型、配饰等细节与用户上传的角色形象图片中的游戏角色保持一致。
4. 背景简约，突出角色主体。
5、若要求创作全身图，请确保角色的所有身体部位都完整呈现，包括手部、脚部、鞋子等。
6、若要求创作正面图，请保证角色面部朝向镜头。

**注意事项**：
1. 尽可能准确还原角色的面部细节特征，尤其是眼睛、嘴角等反映角色性格与情绪的部位。

**用户输入**：
"""

full_front_prompt = template_prompt.format(image_type="全身正面")
full_side_prompt = template_prompt.format(image_type="全身侧面")
half_front_prompt = template_prompt.format(image_type="半身正面")
half_side_prompt = template_prompt.format(image_type="半身侧面")
face_close_prompt = template_prompt.format(image_type="脸部特写")
