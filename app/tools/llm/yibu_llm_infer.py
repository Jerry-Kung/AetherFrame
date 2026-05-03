import http.client
import json
import base64
import os
import logging
from datetime import datetime
import time


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


YIBU_API_KEY = "sk-fcrGfFltSSsEhyPm0kwRiXyoogcoqwDYrEPlOZDPqAmB8EgV"


def get_image_mime_type(image_path: str) -> str:
    """
    根据文件扩展名获取图片的MIME类型

    Args:
        image_path: 图片文件路径

    Returns:
        MIME类型字符串
    """
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_types.get(ext, "image/png")


def image_to_base64(image_path: str) -> tuple[str, str]:
    """
    将图片文件转换为base64编码

    Args:
        image_path: 图片文件路径

    Returns:
        (mime_type, base64_data) 元组
    """
    mime_type = get_image_mime_type(image_path)
    with open(image_path, "rb") as f:
        base64_data = base64.b64encode(f.read()).decode("utf-8")
    return mime_type, base64_data


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    截断文本，只显示开头部分

    Args:
        text: 原始文本
        max_length: 最大显示长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def yibu_gemini_infer(
    prompt: str,
    image_path: list[str] | None = None,
    model: str = "gemini-3.1-pro-preview",
    system_instruction: str = "You are a helpful assistant.",
    temperature: float = 0.5,
    top_p: float = 1.0,
    thinking_level: str = "medium",
    host: str = "yibuapi.com",
    timeout: int = 300,
) -> str:
    """
    使用一步API调用Gemini模型进行推理，支持图片理解

    Args:
        prompt: 用户输入的提示词
        image_path: 图片路径列表，最多支持5张图片，默认为空
        model: 模型名称，默认为gemini-3.1-pro-preview
        system_instruction: 系统指令，默认为"You are a helpful assistant."
        temperature: 温度参数，控制生成的随机性
        top_p: top-p采样参数
        thinking_level: 思考层级，可选值为 "low"、"medium"、"high"，默认为 "medium"
        host: API主机地址
        timeout: 请求超时时间（秒）

    Returns:
        模型返回的纯文本结果（已过滤thinking部分）

    Raises:
        Exception: API请求失败或解析错误时抛出异常
        ValueError: 参数无效时抛出异常
    """
    start_time = datetime.now()
    logger.info(f"========== 开始Gemini推理任务 ==========")
    logger.info(f"模型: {model}")
    logger.info(f"思考层级: {thinking_level}")
    logger.info(f"温度参数: {temperature}, top_p: {top_p}")
    logger.info(
        f"系统指令长度: {len(system_instruction)}, 内容: {truncate_text(system_instruction)}"
    )
    logger.info(f"用户提示长度: {len(prompt)}, 内容: {truncate_text(prompt)}")

    # 验证thinking_level参数
    valid_thinking_levels = ["low", "medium", "high"]
    if thinking_level not in valid_thinking_levels:
        logger.error(f"无效的thinking_level参数: {thinking_level}")
        raise ValueError(f"thinking_level必须是以下值之一: {valid_thinking_levels}")

    # 验证image_path参数
    if image_path is None:
        image_path = []
    if len(image_path) > 5:
        logger.error(f"图片数量超过限制: {len(image_path)}张")
        raise ValueError("image_path最多支持5张图片")

    logger.info(f"图片数量: {len(image_path)}张")

    # 构建parts列表
    parts = []

    # 添加图片（在text之前）
    for idx, img_path in enumerate(image_path):
        if not os.path.exists(img_path):
            logger.error(f"图片文件不存在: {img_path}")
            raise ValueError(f"图片文件不存在: {img_path}")

        file_size = os.path.getsize(img_path)
        logger.info(
            f"处理图片 {idx+1}/{len(image_path)}: {img_path} (大小: {file_size} bytes)"
        )

        mime_type, base64_data = image_to_base64(img_path)
        logger.info(f"  - MIME类型: {mime_type}, base64长度: {len(base64_data)}")

        parts.append({"inline_data": {"mime_type": mime_type, "data": base64_data}})

    # 添加文本提示
    parts.append({"text": prompt})

    # 构建请求体
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "topP": top_p,
            "thinkingConfig": {"thinkingLevel": thinking_level},
        },
    }

    # 设置请求头
    headers = {"x-goog-api-key": YIBU_API_KEY, "Content-Type": "application/json"}

    # 发送请求
    logger.info(f"发送API请求到: https://{host}/v1beta/models/{model}:generateContent")
    request_start_time = datetime.now()

    max_retries = 2  # 额外重试 2 次
    total_attempts = 1 + max_retries

    for attempt_idx in range(total_attempts):
        request_start_time = datetime.now()
        conn = http.client.HTTPSConnection(host, timeout=timeout)
        try:
            logger.info(f"第 {attempt_idx + 1}/{total_attempts} 次：发送API请求...")
            conn.request(
                "POST",
                f"/v1beta/models/{model}:generateContent",
                json.dumps(payload),
                headers,
            )
            res = conn.getresponse()
            data = res.read()

            request_duration = (datetime.now() - request_start_time).total_seconds()
            logger.info(f"API响应状态码: {res.status}, 耗时: {request_duration:.2f}秒")

            if res.status != 200:
                error_msg = data.decode("utf-8")
                logger.error(f"API请求失败: {error_msg}")
                raise Exception(f"API请求失败，状态码: {res.status}, 响应: {error_msg}")

            # 解析响应
            logger.info("解析API响应...")
            result = json.loads(data.decode("utf-8"))

            # 提取token使用信息
            if "usageMetadata" in result:
                usage = result["usageMetadata"]
                logger.info(
                    "Token使用情况: 输入=%s, 输出=%s, 总计=%s, 思考=%s",
                    usage.get("promptTokenCount", 0),
                    usage.get("candidatesTokenCount", 0),
                    usage.get("totalTokenCount", 0),
                    usage.get("thoughtsTokenCount", 0),
                )

            # 提取纯文本，过滤thinking部分
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                finish_reason = candidate.get("finishReason", "UNKNOWN")
                logger.info(f"推理完成原因: {finish_reason}")

                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    # 只过滤明确标记为thought的部分，保留带thoughtSignature的真实回答
                    text_parts = [
                        part["text"]
                        for part in parts
                        if "text" in part and not part.get("thought")
                    ]
                    response_text = "".join(text_parts)

                    logger.info(f"响应文本长度: {len(response_text)}")
                    logger.info(f"响应内容: {truncate_text(response_text, 200)}")

                    total_duration = (datetime.now() - start_time).total_seconds()
                    logger.info(
                        f"========== 推理任务完成，总耗时: {total_duration:.2f}秒 =========="
                    )
                    return response_text

            logger.error("无法从响应中提取有效文本")
            # 如果 result 解析成功但结构不对，打印便于排查
            print(result)
            raise Exception("无法从响应中提取有效文本")

        except Exception as e:
            logger.error(
                f"推理过程异常（第 {attempt_idx + 1}/{total_attempts} 次）: {str(e)}",
                exc_info=True,
            )
            if attempt_idx < max_retries:
                logger.info("等待 1000ms 后进行重试...")
                time.sleep(10)
                continue
            raise
        finally:
            conn.close()


# 示例用法
if __name__ == "__main__":
    try:
        # 纯文本示例
        response = yibu_gemini_infer(
            prompt="你是谁?",
            system_instruction="你是一只可爱的小猪，回复必须以'哼哼'开头。",
        )
        print("纯文本响应:", response)

        # 图片理解示例（需要实际图片文件）
        # response = yibu_gemini_infer(
        #     prompt="describe this image",
        #     image_path=["D:/Huawei/Prompts/AI_image/Project/video_creation/template/temp1.jpg"]
        # )
        # print("图片理解响应:", response)

    except Exception as e:
        print("错误:", str(e))
