# LLM调用指南

本指南详细介绍如何使用项目中的LLM（大语言模型）调用工具。

## 目录
- [概述](#概述)
- [配置说明](#配置说明)
- [Nano Banana Pro 图片生成](#nano-banana-pro-图片生成)
- [Gemini 3.1 对话与图片理解](#gemini-31-对话与图片理解)
- [示例代码](#示例代码)

## 概述

项目中的LLM调用工具位于 `app/tools/llm/` 目录下，提供了两个主要功能模块：

1. **Nano Banana Pro** (`nano_banana_pro.py`) - 用于图片创作，支持参考图片
2. **Gemini 3.1** (`yibu_llm_infer.py`) - 用于对话和图片理解

## 配置说明

### API配置

API配置位于 `app/tools/llm/config.py` 文件中：

```python
base_url = "yibuapi.com"
api_key = "sk-fcrGfFltSSsEhyPm0kwRiXyoogcoqwDYrEPlOZDPqAmB8EgV"
```

> **注意**: 带有默认值的参数基本都是模型配置参数，一般情况下无需修改或传参。

## Nano Banana Pro 图片生成

### 函数签名

```python
def generate_image_with_nano_banana_pro(
    Content,
    output_path: str,
    file_name: str,
    aspect_ratio: str = "16:9",
)
```

### 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| Content | list | 是 | 内容列表，格式为 `[{"text": "xxx"}, {"picture": "url"}, ...]` |
| output_path | str | 是 | 输出目录（不存在则自动创建） |
| file_name | str | 是 | 保存的图片文件名（可带扩展名） |
| aspect_ratio | str | 否 | 生成图片的宽高比，默认为 "16:9" |

### Content列表格式

Content列表可以包含以下两种元素：

1. **文本元素**: `{"text": "描述文本"}`
2. **图片元素**: `{"picture": "本地图片路径"}`

可以混合使用多种元素，按照顺序排列。

### 返回值

- `bool`: 成功返回 `True`，失败返回 `False`

### 支持的图片格式

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)

## Gemini 3.1 对话与图片理解

### 函数签名

```python
def yibu_gemini_infer(
    prompt: str,
    image_path: list[str] | None = None,
    model: str = "gemini-3.1-pro-preview",
    system_instruction: str = "You are a helpful assistant.",
    temperature: float = 0.5,
    top_p: float = 1.0,
    thinking_level: str = "medium",
    host: str = "yibuapi.com",
    timeout: int = 300
) -> str
```

### 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| prompt | str | 是 | 用户输入的提示词 |
| image_path | list[str] | 否 | 图片路径列表，最多支持5张图片 |
| model | str | 否 | 模型名称，默认为 "gemini-3.1-pro-preview" |
| system_instruction | str | 否 | 系统指令，默认为 "You are a helpful assistant." |
| temperature | float | 否 | 温度参数，控制生成的随机性，默认为 0.5 |
| top_p | float | 否 | top-p采样参数，默认为 1.0 |
| thinking_level | str | 否 | 思考层级，可选值为 "low"、"medium"、"high"，默认为 "medium" |
| host | str | 否 | API主机地址，默认为 "yibuapi.com" |
| timeout | int | 否 | 请求超时时间（秒），默认为 300 |

### 返回值

- `str`: 模型返回的纯文本结果（已过滤thinking部分）

### 异常

- `Exception`: API请求失败或解析错误时抛出异常
- `ValueError`: 参数无效时抛出异常

## 示例代码

### 示例 1: 使用Nano Banana Pro生成图片（仅文本）

```python
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro
from datetime import datetime

content = [{"text": "请画一只可爱的猫咪"}]

result = generate_image_with_nano_banana_pro(
    content,
    output_path="data",
    file_name=f"cat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
)

print(f"执行结果: {result}")
```

### 示例 2: 使用Nano Banana Pro生成图片（文本+参考图片）

```python
from app.tools.llm.nano_banana_pro import generate_image_with_nano_banana_pro
from datetime import datetime

content = [
    {"text": "根据这张图片"},
    {"picture": r"D:\path\to\reference.jpg"},
    {"text": "让它变得更有艺术感"}
]

result = generate_image_with_nano_banana_pro(
    content,
    output_path="output",
    file_name=f"art_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
    aspect_ratio="1:1"
)

print(f"执行结果: {result}")
```

### 示例 3: 使用Gemini 3.1进行纯文本对话

```python
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

try:
    response = yibu_gemini_infer(
        prompt="介绍一下Python编程语言",
        system_instruction="你是一位专业的技术讲师，用简洁明了的语言回答问题。"
    )
    print("响应:", response)
except Exception as e:
    print("错误:", str(e))
```

### 示例 4: 使用Gemini 3.1进行图片理解

```python
from app.tools.llm.yibu_llm_infer import yibu_gemini_infer

try:
    response = yibu_gemini_infer(
        prompt="详细描述这张图片的内容",
        image_path=[
            r"D:\path\to\image1.jpg",
            r"D:\path\to\image2.png"
        ],
        temperature=0.7,
        thinking_level="high"
    )
    print("图片描述:", response)
except Exception as e:
    print("错误:", str(e))
```

## 注意事项

1. **图片路径**: 请确保提供的图片路径存在且可访问
2. **文件大小**: 过大的图片可能会导致API请求失败，建议使用适当大小的图片
3. **网络连接**: 确保网络连接正常，API请求需要访问外部服务
4. **超时设置**: 对于复杂任务，可以适当增加timeout参数值
5. **重试机制**: Gemini 3.1接口内置了重试机制，请求失败会自动重试2次
