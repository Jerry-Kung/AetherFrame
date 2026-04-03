# 文件服务架构设计文档

> 最后更新：2026-04-02  
> 所属项目：AetherFrame - 图片修补模块

---

## 概述

本文档描述 AetherFrame 项目文件服务的统一架构设计，采用三层服务架构，为所有模块提供通用、可扩展的文件和目录管理功能。

---

## 架构设计

### 三层服务架构

```
┌─────────────────────────────────────────┐
│   模块专用层 (Module-Specific)        │
│   - repair_file_service.py            │
│   - (未来) material_file_service.py   │
│   - (未来) beautify_file_service.py   │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   通用文件服务层 (Generic File)        │
│   - file_service.py                     │
│   * 通用文件验证                        │
│   * 通用文件保存/读取/删除             │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   目录服务层 (Directory)               │
│   - directory_service.py                │
│   * 目录结构初始化                      │
│   * 目录健康检查                        │
│   * 临时文件清理                        │
└─────────────────────────────────────────┘
```

### 设计原则

1. **轻量级优先**：本地文件系统，零配置
2. **易维护**：清晰的分层架构，职责分离
3. **可扩展**：通用层 + 专用层，便于新增模块
4. **安全可靠**：文件名安全处理，路径遍历防护

---

## 目录结构

### 完整 Data 目录

```
data/
├── README.md                        # Data 目录说明文档
├── db/                              # 数据库目录
│   └── aetherframe.db              # SQLite 主数据库
├── repair/                          # 图片修补模块
│   ├── tasks/                       # 任务数据
│   │   └── {task_id}/
│   │       ├── main_image.png      # 主图
│   │       ├── references/         # 参考图
│   │       ├── results/            # 结果图
│   │       └── task.json           # 元数据备份（可选）
│   └── templates/                   # Prompt 模板
│       └── templates.json
├── material/                        # 素材加工（预留）
├── beautify/                        # 美图创作（预留）
└── temp/                            # 临时文件（自动清理）
```

### 文件命名规范

| 文件类型 | 命名格式 | 说明 |
|---------|---------|------|
| 主图 | `main_image.{ext}` | 保留原始扩展名 |
| 参考图 | `ref_{index}.{ext}` | index 从 0 开始 |
| 结果图 | `result_{index}.png` | 统一 PNG 格式 |
| 临时文件 | `temp_{timestamp}.{ext}` | 带时间戳 |

---

## 服务模块说明

### 1. directory_service.py - 目录服务

**职责**：目录结构管理、健康检查、临时文件清理

**核心功能**：
- `initialize_data_directory()` - 初始化完整目录结构
- `check_data_directory_health()` - 目录健康检查
- `cleanup_temp_files()` - 清理旧临时文件
- `get_directory_stats()` - 获取目录统计
- `create_backup_suggestion()` - 生成备份建议

**目录路径函数**：
- `get_data_dir()`, `get_db_dir()`
- `get_repair_dir()`, `get_repair_tasks_dir()`
- `get_material_dir()`, `get_beautify_dir()` (预留)
- `get_temp_dir()`

---

### 2. file_service.py - 通用文件服务

**职责**：提供所有模块通用的文件操作功能

**核心功能**：

**文件验证**：
- `sanitize_filename()` - 安全化文件名
- `validate_file()` - 通用文件验证（支持扩展名/MIME类型过滤）

**文件保存**：
- `save_uploaded_file()` - 保存上传的文件
- `save_bytes_to_file()` - 保存字节数据到文件

**文件读取**：
- `get_file_path()` - 获取文件路径
- `list_files_in_dir()` - 列出目录文件

**文件删除**：
- `delete_file()` - 删除单个文件
- `delete_directory()` - 删除整个目录

**自定义异常**：
- `FileServiceError` - 基础异常
- `FileValidationError` - 验证失败
- `FileSaveError` - 保存失败
- `FileDeleteError` - 删除失败

---

### 3. repair_file_service.py - 修补模块文件服务

**职责**：专门处理图片修补模块的文件逻辑

**核心功能**：

**主图操作**：
- `save_main_image()` - 保存主图
- `get_main_image_path()` - 获取主图路径
- `delete_main_image()` - 删除主图

**参考图操作**：
- `save_reference_images()` - 批量保存参考图
- `get_reference_image_path()` - 获取参考图路径
- `list_reference_images()` - 列出参考图
- `delete_reference_image()` - 删除参考图

**结果图操作**：
- `save_result_image()` - 保存结果图
- `get_result_image_path()` - 获取结果图路径
- `list_result_images()` - 列出结果图

**任务整体操作**：
- `ensure_task_dirs()` - 确保任务目录存在
- `delete_task_files()` - 删除任务所有文件

**配置**：
- 支持格式：PNG, JPG/JPEG, WebP
- 主图/参考图限制：10MB/张

---

## 使用示例

### 初始化目录结构

```python
from app.services import directory_service

# 应用启动时调用
directory_service.initialize_data_directory()

# 检查健康状态
health = directory_service.check_data_directory_health()
if health["issues"]:
    print(f"发现问题: {health['issues']}")

# 清理临时文件
cleaned = directory_service.cleanup_temp_files(max_age_hours=24)
```

### 保存和获取文件（通用）

```python
from app.services import file_service
from fastapi import UploadFile

# 保存上传的文件
def handle_upload(file: UploadFile):
    saved_name = file_service.save_uploaded_file(
        file,
        save_dir="/path/to/save",
        save_filename="custom_name.png",
        allowed_extensions={".png", ".jpg"},
        allowed_mimetypes={"image/png", "image/jpeg"}
    )
    return saved_name

# 获取文件路径
filepath = file_service.get_file_path("/path/to/save", "custom_name.png")

# 列出文件
files = file_service.list_files_in_dir("/path/to/save", {".png"})
```

### 修补模块文件操作

```python
from app.services import repair_file_service
from fastapi import UploadFile

task_id = "task-001"

# 保存主图
main_file: UploadFile = ...
saved_name = repair_file_service.save_main_image(task_id, main_file)

# 保存参考图
ref_files: List[UploadFile] = [...]
saved_refs = repair_file_service.save_reference_images(task_id, ref_files)

# 保存结果图（从字节数据）
result_data: bytes = ...
repair_file_service.save_result_image(task_id, result_data, index=0)

# 列出文件
refs = repair_file_service.list_reference_images(task_id)
results = repair_file_service.list_result_images(task_id)

# 删除任务文件
repair_file_service.delete_task_files(task_id)
```

---

## 配置项

### 环境变量

```python
DATA_DIR = os.getenv("DATA_DIR", "./data")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB
```

### 图片配置（修补模块）

```python
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_IMAGE_MIMETYPES = {"image/png", "image/jpeg", "image/webp"}
```

---

## 日志记录

所有服务都使用 Python 标准 `logging` 模块：

```python
import logging
logger = logging.getLogger(__name__)

logger.info("操作信息")
logger.debug("调试细节")
logger.error("错误信息", exc_info=True)
```

---

## 为新模块添加文件服务

### 步骤

1. **创建模块专用文件服务**：`app/services/{module}_file_service.py`
2. **导入通用服务**：从 `file_service` 和 `directory_service` 导入需要的功能
3. **实现模块特定逻辑**：封装模块特有的文件操作
4. **定义模块目录路径**：在 `directory_service` 中添加目录路径函数（如需要）

### 示例：素材加工模块

```python
# app/services/material_file_service.py
from app.services.directory_service import get_material_dir
from app.services.file_service import (
    save_uploaded_file,
    get_file_path,
    list_files_in_dir,
    delete_file
)

def save_material_asset(asset_id: str, file: UploadFile) -> str:
    save_dir = os.path.join(get_material_dir(), "assets")
    return save_uploaded_file(file, save_dir, f"asset_{asset_id}.png")
```

---

## 备份建议

### 备份策略
- **完整备份**：每周备份整个 `data/` 目录
- **增量备份**：每天备份有变化的任务目录
- **数据库备份**：每次应用关闭时复制 `aetherframe.db`

### 备份建议生成

```python
from app.services import directory_service

suggestion = directory_service.create_backup_suggestion()
print(f"建议备份: {suggestion['should_backup']}")
print(f"原因: {suggestion['reason']}")
print(f"预估大小: {suggestion['estimated_backup_size']} 字节")
```

---

## 测试

整合测试文件：`tests/test_file_services.py`

包含测试用例：
- 通用文件服务测试（3个）
- 目录服务测试（3个）
- 修补模块文件服务测试（4个）
- 完整集成测试（1个）

运行测试：
```bash
python -m pytest tests/test_file_services.py -v
```

---

## 总结

本架构采用三层设计：
1. **目录服务层**：通用目录管理
2. **通用文件服务层**：通用文件操作
3. **模块专用层**：各模块特定逻辑

这种设计确保了：
- ✅ 代码复用（通用层被所有模块共享）
- ✅ 易扩展（新增模块只需添加专用层）
- ✅ 易维护（清晰的职责分离）
- ✅ 轻量级（无额外依赖）
