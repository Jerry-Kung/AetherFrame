# API 文档目录

本目录包含 AetherFrame 项目的 API 参考文档，供前端开发人员使用。

## 文档列表

| 文档 | 说明 |
|------|------|
| [repair_module_api_complete.md](./repair_module_api_complete.md) | 修补模块完整 API 参考文档 |

## 快速开始

### 基础路径

所有 API 端点的基础路径为：`/api/repair`

### 统一响应格式

```json
{
  "success": true,
  "data": { /* 具体数据 */ },
  "message": "操作成功"
}
```

### 错误响应

```json
{
  "success": false,
  "data": null,
  "message": "错误描述"
}
```

## API 分类

### 任务管理接口
- `GET /api/repair/tasks` - 获取任务列表
- `POST /api/repair/tasks` - 创建新任务
- `GET /api/repair/tasks/{task_id}` - 获取任务详情
- `PUT /api/repair/tasks/{task_id}` - 更新任务信息
- `DELETE /api/repair/tasks/{task_id}` - 删除任务

### 文件上传接口
- `POST /api/repair/tasks/{task_id}/main-image` - 上传主图
- `POST /api/repair/tasks/{task_id}/reference-images` - 批量上传参考图
- `GET /api/repair/tasks/{task_id}/images/{image_type}/{filename}` - 获取图片文件
- `DELETE /api/repair/tasks/{task_id}/main-image` - 删除主图
- `DELETE /api/repair/tasks/{task_id}/reference-images/{filename}` - 删除参考图

### Prompt 模板接口
- `GET /api/repair/templates` - 获取模板列表
- `POST /api/repair/templates` - 创建自定义模板
- `GET /api/repair/templates/{template_id}` - 获取模板详情
- `PUT /api/repair/templates/{template_id}` - 更新模板
- `DELETE /api/repair/templates/{template_id}` - 删除模板

### 任务执行接口
- `POST /api/repair/tasks/{task_id}/start` - 启动修补任务
- `GET /api/repair/tasks/{task_id}/status` - 获取任务状态

## 完整修补任务流程

1. 创建任务：`POST /api/repair/tasks`
2. 上传主图：`POST /api/repair/tasks/{id}/main-image`
3. 上传参考图（可选）：`POST /api/repair/tasks/{id}/reference-images`
4. 启动修补任务：`POST /api/repair/tasks/{id}/start`
5. 轮询任务状态：`GET /api/repair/tasks/{id}/status`
6. 获取最终结果：`GET /api/repair/tasks/{id}`

详细使用说明请参考 [repair_module_api_complete.md](./repair_module_api_complete.md)。

## 其他

- **Swagger UI**: 访问 `http://localhost:8000/docs` 查看交互式 API 文档
- **ReDoc**: 访问 `http://localhost:8000/redoc` 查看更美观的 API 文档
