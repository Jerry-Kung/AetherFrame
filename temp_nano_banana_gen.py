# -*- coding: utf-8 -*-
"""
临时脚本：调用 Nano Banana 模型生成一张图片。

基于 app/tools/llm/nano_banana_pro.py 的调用逻辑简化而来，
所有配置已内联到本脚本，可脱离项目独立运行（仅需填写 API_KEY）。

Prompt 输入：在脚本执行的当前目录下创建 prompt.txt（UTF-8），脚本自动读取其内容作为生图 Prompt。
也可通过 --prompt-file 指定其他路径的 Prompt 文件。

用法示例（在项目根目录执行）:
    python temp_nano_banana_gen.py                # 纯文本生图
    python temp_nano_banana_gen.py --image        # 带参考图：自动使用当前目录下的图片
    python temp_nano_banana_gen.py --image D:\\path\\to\\ref.png   # 也可显式指定路径
    python temp_nano_banana_gen.py --aspect-ratio 1:1 --output-dir data/temp --file-name my_pic
"""

import argparse
import base64
import http.client
import json
import os
import sys
from datetime import datetime

# Windows 控制台默认 GBK，强制 UTF-8 避免中文输出乱码
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ---- 配置（原 app/tools/llm/config.py，已内联，脱离项目独立运行）----
# base_url 等普通配置直接写死；api_key 等敏感信息留空，请自行填写。
base_url = "yibuapi.com"
api_key = ""  # TODO: 填写你的 API Key（形如 sk-xxxxxxxx）

MODEL_ENDPOINT = "/v1beta/models/gemini-3.1-flash-image-preview:generateContent"

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def build_parts(prompt: str, image_path: str | None) -> list:
    """组装请求 parts：一段文本 + 最多一张本地参考图"""
    parts = [{"text": prompt}]
    if image_path:
        if not os.path.exists(image_path):
            sys.exit(f"错误：参考图片不存在: {image_path}")
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        mime_type = MIME_TYPES.get(os.path.splitext(image_path)[1].lower(), "image/jpeg")
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_base64}})
        print(f"已加载参考图: {image_path} (MIME: {mime_type}, base64 长度: {len(image_base64)})")
    return parts


def extract_first_image(json_data: dict) -> tuple[bytes, str] | None:
    """从响应 JSON 中提取第一张图片，返回 (图片字节, 扩展名)；未找到返回 None"""
    for candidate in json_data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                mime = inline.get("mimeType", "image/jpeg").lower()
                ext = "jpg"
                for key in ("png", "gif", "webp"):
                    if key in mime:
                        ext = key
                        break
                return base64.b64decode(inline["data"]), ext
    return None


def find_reference_image() -> str:
    """在当前目录自动查找参考图：仅一张图片时直接使用；多张时优先文件名为 ref 的那张"""
    candidates = [
        f
        for f in sorted(os.listdir("."))
        if os.path.isfile(f) and os.path.splitext(f)[1].lower() in MIME_TYPES
    ]
    if not candidates:
        sys.exit(
            f"错误：当前目录未找到参考图片: {os.path.abspath('.')}\n"
            f"请将参考图（{'/'.join(sorted(set(MIME_TYPES)))}）放到当前目录，或用 --image 指定路径。"
        )
    if len(candidates) == 1:
        return candidates[0]
    preferred = [f for f in candidates if os.path.splitext(f)[0].lower() in ("ref", "reference")]
    if len(preferred) == 1:
        return preferred[0]
    sys.exit(
        "错误：当前目录存在多张图片，无法确定参考图: " + ", ".join(candidates) + "\n"
        "请只保留一张，或将参考图命名为 ref.png/ref.jpg 等，或用 --image 指定路径。"
    )


def read_prompt(prompt_file: str) -> str:
    """从 Prompt 文件读取生图 Prompt，文件不存在或内容为空时报错退出"""
    if not os.path.exists(prompt_file):
        sys.exit(
            f"错误：未找到 Prompt 文件: {os.path.abspath(prompt_file)}\n"
            f"请在当前目录创建 prompt.txt（UTF-8 编码）并写入生图 Prompt。"
        )
    with open(prompt_file, "r", encoding="utf-8-sig") as f:
        prompt = f.read().strip()
    if not prompt:
        sys.exit(f"错误：Prompt 文件内容为空: {os.path.abspath(prompt_file)}")
    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="调用 Nano Banana 模型生成一张图片（Prompt 从 prompt.txt 读取）"
    )
    parser.add_argument("--prompt-file", default="prompt.txt", help="Prompt 文件路径，默认当前目录 prompt.txt")
    parser.add_argument(
        "--image",
        nargs="?",
        const="auto",
        default=None,
        help="带一张参考图。不带值时自动使用当前目录下的图片；也可显式指定图片路径",
    )
    parser.add_argument("--aspect-ratio", default="16:9", help="宽高比，如 16:9、1:1，默认 16:9")
    parser.add_argument("--output-dir", default="data/temp", help="输出目录，默认 data/temp")
    parser.add_argument("--file-name", default=None, help="输出文件名（不含扩展名时自动补全），默认按时间戳生成")
    parser.add_argument("--timeout", type=int, default=2700, help="HTTP 超时秒数，默认 2700")
    args = parser.parse_args()

    image_path = args.image
    if image_path == "auto":
        image_path = find_reference_image()

    prompt = read_prompt(args.prompt_file)
    print(f"已从 {os.path.abspath(args.prompt_file)} 读取 Prompt（{len(prompt)} 字符）")

    if not api_key:
        sys.exit("错误：api_key 为空，请先在脚本顶部的 api_key 处填写你的 API Key。")

    file_name = args.file_name or f"nano_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    payload = json.dumps(
        {
            "contents": [{"role": "user", "parts": build_parts(prompt, image_path)}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": args.aspect_ratio, "imageSize": "2K"},
            },
        }
    )
    headers = {
        "Authorization": "Bearer <token>",
        "Content-Type": "application/json",
    }

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"正在调用 Nano Banana（{base_url}），宽高比 {args.aspect_ratio}，请耐心等待...")
    conn = http.client.HTTPSConnection(base_url, timeout=args.timeout)
    try:
        conn.request("POST", f"{MODEL_ENDPOINT}?key={api_key}", payload, headers)
        res = conn.getresponse()
        data = res.read()
    finally:
        conn.close()

    decoded = data.decode("utf-8", errors="replace")
    if res.status != 200:
        sys.exit(f"API 请求失败，HTTP {res.status}:\n{decoded[:1000]}")

    try:
        json_data = json.loads(decoded)
    except json.JSONDecodeError:
        raw_path = os.path.join(args.output_dir, f"{file_name}_response.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(decoded)
        sys.exit(f"响应不是合法 JSON，原始内容已保存到: {raw_path}")

    result = extract_first_image(json_data)
    if result is None:
        raw_path = os.path.join(args.output_dir, f"{file_name}_response.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        sys.exit(f"响应中未找到图片数据，完整响应已保存到: {raw_path}")

    image_bytes, ext = result
    stem, existing_ext = os.path.splitext(file_name)
    if existing_ext.lower() in MIME_TYPES:
        save_path = os.path.join(args.output_dir, file_name)
    else:
        save_path = os.path.join(args.output_dir, f"{file_name}.{ext}")
    with open(save_path, "wb") as f:
        f.write(image_bytes)
    print(f"图片生成成功，已保存到: {save_path}（{len(image_bytes)} 字节）")


if __name__ == "__main__":
    main()
