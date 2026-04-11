# 素材加工模块数据管理文档

> 最后更新：2026-04-08  
> 所属项目：AetherFrame - 素材加工模块

---

## 概述

本文档详细说明素材加工模块的数据库结构和文件目录组织，帮助其他模块快速定位和使用该模块的数据。

---

## 一、数据库架构

### 数据库位置
- **路径**: `{DATA_DIR}/db/aetherframe.db`
- **类型**: SQLite
- **默认 DATA_DIR**: `./data` (可通过环境变量配置)

### 数据表结构

#### 1. MaterialCharacter - 角色主表

**表名**: `material_characters`

| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| id | String (主键) | 角色ID，格式 `mchar_{uuid10}` | 自动生成 |
| name | String(200) | 角色名称 | 必填 |
| display_name | String(200) | 显示名称 | name |
| status | String(20) | 状态：idle/draft/processing/done | "idle" |
| setting_text | Text | 角色设定文本 | "" |
| setting_source_filename | String(255), 可空 | 最近一次通过 .txt/.md 上传写入设定时的原始文件名（仅展示用） | NULL |
| avatar_filename | String(255) | 头像文件名 | None |
| official_photos_json | Text | 标准照槽位URL数组JSON | "[null,null,null,null,null]" |
| bio_json | Text | 角色小档案JSON | "{}" |
| created_at | DateTime | 创建时间 | 自动生成 |
| updated_at | DateTime | 更新时间 | 自动更新 |

**关键字段说明**:
- `official_photos_json`: 包含5个标准照槽位，顺序为：`[full_front, full_side, half_front, half_side, face_close]`
- `bio_json`: 存储角色小档案的JSON数据

**关系**: 一对多关联到 `MaterialCharacterRawImage`

#### 2. MaterialCharacterRawImage - 原始参考图元数据

**表名**: `material_character_raw_images`

| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| id | String (主键) | 图片ID，UUID | 自动生成 |
| character_id | String (外键) | 所属角色ID | 必填 |
| stored_filename | String(255) | 存储文件名 | 必填 |
| type | String(20) | 类型：official/fanart | "official" |
| tags_json | Text | 标签数组JSON | "[]" |
| created_at | DateTime | 创建时间 | 自动生成 |

**外键**: `character_id` → `material_characters.id` (CASCADE删除)

#### 3. MaterialStandardPhotoTask - 标准照任务

**表名**: `material_standard_photo_tasks`

| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| id | String (主键) | 任务ID，格式 `mphoto_{uuid10}` | 自动生成 |
| character_id | String (外键唯一) | 所属角色ID | 必填 |
| shot_type | String(20) | 拍摄类型 | 必填 |
| aspect_ratio | String(10) | 长宽比 | "9:16" |
| output_count | Integer | 生成数量 | 2 |
| status | String(20) | 状态：pending/processing/completed/failed | "pending" |
| error_message | Text | 错误信息 | None |
| selected_raw_image_ids_json | Text | 选中的参考图ID数组JSON | "[]" |
| result_images_json | Text | 结果图片URL数组JSON | "[]" |
| created_at | DateTime | 创建时间 | 自动生成 |
| updated_at | DateTime | 更新时间 | 自动更新 |

**外键**: `character_id` → `material_characters.id` (CASCADE删除)

**shot_type 可选值**:
- `full_front`: 全身正面
- `full_side`: 全身侧面  
- `half_front`: 半身正面
- `half_side`: 半身侧面
- `face_close`: 脸部特写

---

## 二、文件目录结构

### 完整目录树

```
data/
├── db/
│   └── aetherframe.db                    # SQLite数据库
└── material/
    └── characters/
        └── {character_id}/               # 角色ID，如 mchar_abc123
            ├── raw/                       # 原始参考图
            │   ├── official/               # 官方形象参考图
            │   │   ├── {image_id}.png    # 图片ID作为文件名
            │   │   └── ...
            │   └── fanart/                # 同人立绘参考图
            │       ├── {image_id}.jpg
            │       └── ...
            ├── standard_photo/             # 标准照任务
            │   ├── {task_id}/            # 任务ID，如 mphoto_xyz789
            │   │   └── results/          # 生成结果
            │   │       ├── result_0_20260408_123456_789012.png
            │   │       ├── result_1_20260408_123457_123456.png
            │   │       └── ...            # 唯一时间戳命名
            │   └── ...                   # 历史任务目录
            └── standard_photo_slots/      # 正式标准照槽位
                ├── full_front.png         # 全身正面
                ├── full_side.png          # 全身侧面
                ├── half_front.png         # 半身正面
                ├── half_side.png          # 半身侧面
                └── face_close.png         # 脸部特写
```

### 目录说明

#### 2.1 原始参考图目录 `raw/`

**路径**: `data/material/characters/{character_id}/raw/`

**子目录**:
- `official/`: 官方形象参考图
- `fanart/`: 同人立绘参考图

**文件命名**: `{image_id}.{ext}`
- `image_id`: 数据库中 `MaterialCharacterRawImage.id`
- `ext`: 原始扩展名，支持 `.png`, `.jpg`, `.jpeg`, `.webp`

#### 2.2 标准照任务目录 `standard_photo/`

**路径**: `data/material/characters/{character_id}/standard_photo/`

**子目录**:
- `{task_id}/results/`: 每次任务的生成结果

**文件命名**: `result_{index}_{timestamp}.png`
- `index`: 结果序号 (0, 1, 2, ...)
- `timestamp`: 精确到微秒的时间戳 `%Y%m%d_%H%M%S_%f`
- **注意**: 使用时间戳避免浏览器缓存旧图

#### 2.3 正式标准照槽位 `standard_photo_slots/`

**路径**: `data/material/characters/{character_id}/standard_photo_slots/`

**固定文件**:
- `full_front.png`: 全身正面标准照
- `full_side.png`: 全身侧面标准照
- `half_front.png`: 半身正面标准照
- `half_side.png`: 半身侧面标准照
- `face_close.png`: 脸部特写标准照

**说明**: 这些文件通过「保存到正式内容」操作从任务结果复制而来，不受新任务影响

---

## 三、数据访问接口

### 3.1 Repository 层

**文件**: `app/repositories/material_repository.py`

**核心类**: `MaterialCharacterRepository`

**常用方法**:
- `get_by_id(character_id: str)`: 获取角色详情
- `list_by_updated(skip, limit)`: 按更新时间倒序列表
- `create(data)`: 创建新角色
- `update(character_id, data)`: 更新角色
- `delete(character_id)`: 删除角色
- `add_raw_image(...)`: 添加原始参考图记录
- `list_raw_images(character_id)`: 列出原始参考图
- `delete_raw_image(character_id, image_id)`: 删除原始参考图
- `get_standard_photo_task_by_character_id(character_id)`: 获取标准照任务
- `upsert_standard_photo_task(...)`: 创建或更新标准照任务
- `save_official_photo_by_shot_type(...)`: 保存正式标准照到槽位
- `clear_official_photo_at_index(character_id, slot_index)`: 清空标准照槽位

### 3.2 File Service 层

**文件**: `app/services/material_service/material_file_service.py`

**目录路径函数**:
- `get_character_dir(character_id)`: 角色根目录
- `get_character_raw_dir(character_id)`: 原始参考图目录
- `get_character_raw_type_dir(character_id, type)`: 按类型分目录
- `get_character_standard_photo_dir(character_id)`: 标准照目录
- `get_standard_photo_task_dir(character_id, task_id)`: 任务目录
- `get_standard_photo_task_results_dir(character_id, task_id)`: 任务结果目录
- `get_standard_photo_slot_dir(character_id)`: 槽位目录

**文件操作函数**:
- `save_raw_image(character_id, image_id, file, type)`: 保存原始参考图
- `get_raw_image_path(character_id, filename, type)`: 获取原始参考图路径
- `delete_raw_image_file(character_id, filename, type)`: 删除原始参考图文件
- `save_standard_photo_result_bytes(character_id, task_id, data, index)`: 保存任务结果
- `get_standard_photo_result_image_path(character_id, task_id, filename)`: 获取任务结果路径
- `copy_task_result_to_official_slot(...)`: 复制结果到槽位
- `get_standard_slot_image_path(character_id, shot_type)`: 获取槽位文件路径
- `delete_standard_slot_image_file(character_id, shot_type)`: 删除槽位文件
- `delete_character_files(character_id)`: 删除角色所有文件

### 3.3 API 端点

**路由前缀**: `/api/material`

#### 角色管理
- `GET /characters` - 角色列表
- `POST /characters` - 创建角色
- `GET /characters/{character_id}` - 角色详情
- `DELETE /characters/{character_id}` - 删除角色
- `PUT /characters/{character_id}/setting` - 更新设定文本

#### 原始参考图
- `POST /characters/{character_id}/raw-images` - 上传参考图
- `DELETE /characters/{character_id}/raw-images/{image_id}` - 删除参考图
- `GET /characters/{character_id}/images/raw/{filename}` - 获取参考图文件

#### 标准照任务
- `POST /characters/{character_id}/standard-photo/start` - 启动标准照任务
- `POST /characters/{character_id}/standard-photo/retry` - 重试任务
- `GET /characters/{character_id}/standard-photo/status` - 任务状态
- `POST /characters/{character_id}/standard-photo/select` - 保存结果到槽位
- `DELETE /characters/{character_id}/standard-photo/slot/{slot_index}` - 清空槽位

#### 文件访问
- `GET /characters/{character_id}/standard-photo/result-images/{filename}` - 获取任务结果图
- `GET /characters/{character_id}/standard-photo/slot-images/{shot_type}` - 获取槽位图

---

## 四、数据使用指南

### 4.1 获取角色数据

**步骤**:
1. 通过 `MaterialCharacterRepository.get_by_id()` 获取角色记录
2. 解析 `official_photos_json` 获取标准照槽位URL
3. 通过 `list_raw_images()` 获取原始参考图列表
4. 通过文件服务函数获取实际文件路径

**示例**:
```python
from app.repositories.material_repository import MaterialCharacterRepository

repo = MaterialCharacterRepository(db)
character = repo.get_by_id("mchar_abc123")

# 获取标准照槽位
import json
official_photos = json.loads(character.official_photos_json)
# official_photos[0] = full_front URL
# official_photos[1] = full_side URL
# ...

# 获取原始参考图
raw_images = repo.list_raw_images("mchar_abc123")
for img in raw_images:
    path = get_raw_image_path(img.character_id, img.stored_filename, img.type)
```

### 4.2 访问标准照文件

**任务结果图**（临时）:
```python
from app.services.material_service import material_file_service

# 获取任务结果
task = repo.get_standard_photo_task_by_character_id("mchar_abc123")
result_urls = json.loads(task.result_images_json)

# 解析文件名
filename = result_urls[0].split('/')[-1].split('?')[0]
path = material_file_service.get_standard_photo_result_image_path(
    "mchar_abc123", task.id, filename
)
```

**正式槽位图**（稳定）:
```python
# 获取半身正面标准照
path = material_file_service.get_standard_slot_image_path("mchar_abc123", "half_front")
# 结果: data/material/characters/mchar_abc123/standard_photo_slots/half_front.png
```

### 4.3 清理策略

**自动清理**:
- 标准照任务结果保留在历史任务目录中，不会自动清理
- 新任务会清空当前任务的 `results/` 目录，不影响历史任务

**手动清理**:
```python
# 清空标准照槽位
repo.clear_official_photo_at_index("mchar_abc123", 0)
material_file_service.delete_standard_slot_image_file("mchar_abc123", "full_front")

# 删除整个角色
repo.delete("mchar_abc123")
material_file_service.delete_character_files("mchar_abc123")
```

---

## 五、数据安全与备份

### 5.1 数据完整性

**数据库与文件一致性**:
- 删除角色时，数据库记录通过CASCADE自动删除关联记录
- 文件需要通过 `delete_character_files()` 单独清理
- 建议在事务中同时操作数据库和文件

### 5.2 备份建议

**重要数据**:
1. SQLite数据库: `data/db/aetherframe.db`
2. 所有角色数据: `data/material/characters/`

**备份方法**:
```bash
# 备份整个data目录
cp -r data data_backup_$(date +%Y%m%d)

# 或使用tar压缩
tar -czf aetherframe_backup_$(date +%Y%m%d).tar.gz data/
```

### 5.3 恢复步骤

1. 停止应用服务
2. 恢复数据库文件: `data/db/aetherframe.db`
3. 恢复角色文件目录: `data/material/characters/`
4. 重启应用服务

---

## 六、常见问题

### Q1: 如何找到某个角色的所有标准照？

**A**: 查询 `MaterialCharacter.official_photos_json` 字段，然后访问 `standard_photo_slots/` 目录。

### Q2: 任务结果图会被覆盖吗？

**A**: 不会。每次任务创建新的 `{task_id}/results/` 目录，文件名带时间戳，不会冲突。

### Q3: 如何区分临时结果和正式标准照？

**A**: 
- 临时结果: `standard_photo/{task_id}/results/` 目录，API路径带 `result-images`
- 正式标准照: `standard_photo_slots/` 目录，API路径带 `slot-images`

### Q4: 删除参考图会影响标准照吗？

**A**: 不会。标准照任务只保存选中的参考图ID到 `selected_raw_image_ids_json`，任务执行时使用这些ID，后续删除参考图不影响已保存的标准照。

### Q5: 如何获取最新的标准照任务？

**A**: 使用 `get_standard_photo_task_by_character_id()`，每角色只保留一个任务记录，新任务会覆盖旧任务。

---

## 七、版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-04-08 | 初始版本，完整描述数据库和文件结构 |
