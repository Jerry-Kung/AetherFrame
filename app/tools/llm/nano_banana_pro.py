import http.client
import json
import os
import base64
import sys
from datetime import datetime

# 处理导入路径问题：确保可以导入同目录下的config模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import base_url, api_key


def get_image_mime_type(image_path):
    """根据图片文件扩展名返回MIME类型"""
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_types.get(ext, "image/jpeg")


def image_to_base64(image_path):
    """读取本地图片文件并转换为base64编码"""
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            return image_base64
    except Exception as e:
        print(f"读取图片文件失败: {image_path}, 错误: {e}")
        return None


def _resolve_image_save_path(output_path: str, file_name: str, mime_ext: str) -> str:
    """
    生成图片完整保存路径。若 file_name 无扩展名，则按 MIME 对应格式追加后缀（如 .jpg）。
    mime_ext 不含点，如 'jpg'、'png'。
    """
    _stem, ext = os.path.splitext(file_name)
    ext_lower = ext.lower()
    known = (".jpg", ".jpeg", ".png", ".gif", ".webp")
    if ext_lower not in known:
        return os.path.join(output_path, f"{file_name}.{mime_ext}")
    return os.path.join(output_path, file_name)


def generate_image_with_nano_banana_pro(
    Content,
    output_path: str,
    file_name: str,
    aspect_ratio: str = "16:9",
):
    """
    调用 nano_banana_pro 模型生成图片并保存到指定目录。

    参数:
        Content: 列表，格式为 [{"text": "xxx"}, {"picture": "url"}, ...]
                - text: 纯文本内容
                - picture: 图片的本地路径
        output_path: 输出目录（不存在则创建）
        file_name: 保存的图片文件名（可带扩展名；无扩展名时按响应 MIME 自动补全）
        aspect_ratio: 生成图片的宽高比，如 "16:9"、"1:1" 等，默认为 "16:9"

    返回:
        bool: 成功返回 True，失败返回 False
    """
    try:
        print("=" * 50)
        print("开始调用 nano_banana_pro 模型生成图片")
        print("=" * 50)

        # 1. 解析Content列表，组装parts
        parts = []
        for i, item in enumerate(Content):
            if "text" in item:
                # 处理文本
                text_content = item["text"]
                parts.append({"text": text_content})
                print(
                    f"[{i+1}] 添加文本: {text_content[:50]}..."
                    if len(text_content) > 50
                    else f"[{i+1}] 添加文本: {text_content}"
                )
            elif "picture" in item:
                # 处理图片
                picture_url = item["picture"]
                print(f"[{i+1}] 处理图片: {picture_url}")

                # 检查文件是否存在
                if not os.path.exists(picture_url):
                    print(f"错误: 图片文件不存在: {picture_url}")
                    return False

                # 读取图片并转换为base64
                image_base64 = image_to_base64(picture_url)
                if image_base64 is None:
                    return False

                # 获取MIME类型
                mime_type = get_image_mime_type(picture_url)

                # 组装为inline_data格式（注意：请求时使用下划线命名）
                parts.append(
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}}
                )
                print(
                    f"  图片已转换为base64，MIME类型: {mime_type}, 大小: {len(image_base64)} 字符"
                )
            else:
                print(f"警告: Content[{i}] 中未找到 'text' 或 'picture' 字段，跳过")

        if not parts:
            print("错误: Content列表为空或未包含有效内容")
            return False

        print(f"\n共组装 {len(parts)} 个parts")

        # 2. 构建payload
        payload = json.dumps(
            {
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": "2K"},
                },
            }
        )

        # 3. 发送API请求
        print("\n正在发送API请求...")
        conn = http.client.HTTPSConnection(base_url)
        headers = {
            "Authorization": "Bearer <token>",
            "Content-Type": "application/json",
        }
        conn.request(
            "POST",
            f"/v1beta/models/gemini-3-pro-image-preview:generateContent?key={api_key}",
            payload,
            headers,
        )

        res = conn.getresponse()
        data = res.read()

        # 检查HTTP状态码
        if res.status != 200:
            print(f"错误: API请求失败，HTTP状态码: {res.status}")
            print(f"响应内容: {data.decode('utf-8')}")
            return False

        print(f"API请求成功，HTTP状态码: {res.status}")

        # 4. 解析响应
        decoded_data = data.decode("utf-8")
        print("\n响应内容预览:")
        print(decoded_data[:500] + "..." if len(decoded_data) > 500 else decoded_data)

        # 5. 创建输出目录并保存结果
        os.makedirs(output_path, exist_ok=True)
        print(f"\n输出目录: {output_path}")

        # 保存 JSON 响应
        json_file_path = os.path.join(output_path, "response.json")
        try:
            json_data = json.loads(decoded_data)
            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            print(f"JSON响应数据已保存到: {json_file_path}")

            # 提取并保存图片数据
            # 根据JSON结构：candidates[].content.parts[].inlineData.data
            image_saved = False
            if "candidates" in json_data:
                for i, candidate in enumerate(json_data.get("candidates", [])):
                    if "content" in candidate and "parts" in candidate["content"]:
                        for j, part in enumerate(candidate["content"]["parts"]):
                            # 注意字段名是 inlineData（驼峰命名），不是 inline_data
                            if "inlineData" in part:
                                inline_data = part["inlineData"]
                                image_data_base64 = inline_data.get("data", "")
                                mime_type = inline_data.get("mimeType", "image/jpeg")

                                if image_data_base64:
                                    # 确定文件扩展名
                                    ext = "jpg"  # 默认jpg
                                    if (
                                        "jpeg" in mime_type.lower()
                                        or "jpg" in mime_type.lower()
                                    ):
                                        ext = "jpg"
                                    elif "png" in mime_type.lower():
                                        ext = "png"
                                    elif "gif" in mime_type.lower():
                                        ext = "gif"
                                    elif "webp" in mime_type.lower():
                                        ext = "webp"

                                    # 将base64数据解码为图片
                                    try:
                                        image_bytes = base64.b64decode(
                                            image_data_base64
                                        )
                                        # 仅将第一张图写入用户指定的 file_name
                                        if not image_saved:
                                            image_file_path = _resolve_image_save_path(
                                                output_path, file_name, ext
                                            )
                                            with open(image_file_path, "wb") as f:
                                                f.write(image_bytes)
                                            print(
                                                f"图片已保存到: {image_file_path} (MIME类型: {mime_type}, 大小: {len(image_bytes)} 字节)"
                                            )
                                            image_saved = True
                                        else:
                                            print(
                                                f"提示: 响应中另有图片 (candidates[{i}].parts[{j}])，已跳过（仅保存第一张到 {file_name}）"
                                            )
                                    except Exception as e:
                                        print(f"解码图片数据时出错: {e}")
                                        return False
                                else:
                                    print(
                                        f"警告: candidates[{i}].content.parts[{j}] 中的 inlineData.data 为空"
                                    )

            if not image_saved:
                print("警告: 响应中未找到图片数据")

            print("\n" + "=" * 50)
            print("图片生成完成！")
            print("=" * 50)
            return True

        except json.JSONDecodeError as e:
            # 如果不是JSON格式，直接保存为文本
            with open(json_file_path, "w", encoding="utf-8") as f:
                f.write(decoded_data)
            print(f"响应不是JSON格式，已保存为文本: {json_file_path}")
            print(f"JSON解析错误: {e}")
            return False

    except Exception as e:
        print(f"\n错误: 执行过程中发生异常: {e}")
        import traceback

        traceback.print_exc()
        return False


# 示例用法（可以注释掉）
if __name__ == "__main__":
    # 示例：只使用文本
    content_example = [{"text": "please draw a picture of a cat"}]

    # 示例：使用文本和图片
    # content_example = [
    #     {"text": "please draw a picture of a cat"},
    #     {"picture": r"D:\Huawei\Projects\swt_dfms\video_creation\output\img1.png"},
    #     {"text": "make it more colorful"}
    # ]

    result = generate_image_with_nano_banana_pro(
        content_example,
        output_path="data",
        file_name=f"nano_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
    )
    print(f"\n函数执行结果: {result}")
