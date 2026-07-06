# AetherFrame - 二次元美图开发引擎

## 项目概述

轻量级个人图像处理工具，面向喜爱二次元风格的用户，提供素材加工、美图创作、图片修补三大功能模块。

## 技术栈

- **前端**: React 19 + TypeScript + Vite + Tailwind CSS
- **后端**: FastAPI + Python 3.12
- **部署**: Docker + Docker Compose

## 项目结构

```
AetherFrame/
├── app/                  # FastAPI 后端应用
│   ├── main.py          # 应用入口
│   ├── routes/          # 路由模块
│   │   ├── pages.py     # 页面路由
│   │   └── api.py       # API 路由
│   ├── services/        # 业务逻辑
│   ├── static/          # 静态文件（前端构建产物）
│   └── templates/       # Jinja2 模板
├── page/                # React 前端源代码
│   ├── src/             # 前端源代码
│   ├── index.html       # 入口 HTML
│   ├── package.json     # 前端依赖
│   └── vite.config.ts   # Vite 配置
├── data/                # 数据目录
├── docker/              # Docker 配置
├── compose.yaml         # Docker Compose 配置
└── requirements.txt     # Python 依赖
```

## 快速开始

### 开发模式

#### 前端开发

```bash
# 进入前端目录
cd page

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本（输出到 app/static）
npm run build
```

#### 后端开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker 部署

```bash
# 构建并启动服务
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

## 功能模块

1. **素材加工** - 图像裁剪、格式转换、批量处理等
2. **美图创作** - AI 绘图、风格化生成等
3. **图片修补** - 去水印、背景抹除、修复等

## 访问地址

- 应用主页: http://localhost:8000
- API 文档: http://localhost:8000/docs
