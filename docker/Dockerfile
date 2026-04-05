# 第一阶段：构建前端
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# 复制前端依赖文件
COPY page/package*.json ./

# 安装前端依赖（使用淘宝镜像加速）
RUN npm config set registry https://registry.npmmirror.com && \
    npm install

# 复制前端源代码
COPY page/index.html ./
COPY page/tsconfig*.json ./
COPY page/vite.config.ts ./
COPY page/tailwind.config.ts ./
COPY page/postcss.config.ts ./
COPY page/eslint.config.ts ./
COPY page/src ./src
COPY page/eslint-rules ./eslint-rules

# 构建前端（输出到 ../app/static，相对于 /frontend 就是 /app/static）
RUN npm run build

# 第二阶段：构建后端
FROM python:3.12-slim

WORKDIR /app

# 复制 Python 依赖
COPY requirements.txt .

# 安装 Python 依赖（使用清华镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端代码
COPY app /app/app

# 从前端构建阶段复制构建产物（前端构建输出到 /app/static）
COPY --from=frontend-builder /app/static /app/app/static

# 复制 data 目录的占位符（实际运行时通过挂载提供）
RUN mkdir -p /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
