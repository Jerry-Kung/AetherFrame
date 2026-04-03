# 后端设计文档目录

本目录包含 AetherFrame 项目的后端设计和架构文档，供后端开发人员参考。

## 注意

API 参考文档已迁移至 [docs/api](../api/) 目录。前端开发人员请查看 [docs/api](../api/) 目录。

## 文档列表

| 文档 | 说明 |
|------|------|
| [architecture_review.md](./architecture_review.md) | API 架构 Review 与优化建议 |
| [async_task_processing.md](./async_task_processing.md) | 异步任务处理设计文档 |
| [image_generation_integration.md](./image_generation_integration.md) | 图片生成工具集成设计文档 |
| [repair_module_review.md](./repair_module_review.md) | 图片修补模块后端架构 Review |
| [database/](./database/) | 数据库相关文档 |
| [file_service/](./file_service/) | 文件服务相关文档 |

## 目录结构

```
docs/backend/
├── README.md                    # 本文件
├── architecture_review.md       # API 架构 Review
├── async_task_processing.md     # 异步任务处理设计
├── image_generation_integration.md # 图片生成集成
├── repair_module_review.md      # 修补模块 Review
├── database/                    # 数据库文档
│   ├── README.md
│   ├── architecture.md
│   └── reference.md
└── file_service/                # 文件服务文档
    └── file_services.md
```

## 相关文档

- **API 参考**: [docs/api](../api/) - 前端调用的 API 文档
- **前端文档**: [docs/frontend](../frontend/) - 前端开发文档
