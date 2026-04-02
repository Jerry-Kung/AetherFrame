# 前端代码迁移操作指南

## 概述

本文档用于指导如何从外部网页创作平台（如 Readdy）将加工好的网页及源代码迁移到 AetherFrame 项目中。

## 目录结构说明

```
AetherFrame/
├── refs/                    # 外部来源的前端代码存放目录
│   └── project_frontend/   # 示例：从外部平台导出的代码
├── page/                    # 项目正式的前端代码目录
├── app/                     # FastAPI 后端应用
│   └── static/              # 前端构建产物输出目录
└── docs/                    # 文档目录
```

## 迁移步骤

### 第一步：准备工作

1. **获取外部代码**
   - 从外部网页创作平台导出完整的前端源代码
   - 将代码放置在 `refs/` 目录下，例如 `refs/my_new_feature/`

2. **检查代码结构**
   ```bash
   # 查看外部代码目录结构
   Get-ChildItem -Recurse refs\your_project_name
   ```

3. **确认项目配置文件**
   - `package.json` - 前端依赖配置
   - `vite.config.ts` - Vite 构建配置
   - `tailwind.config.ts` - Tailwind CSS 配置
   - `tsconfig*.json` - TypeScript 配置

### 第二步：迁移代码到 page 目录

#### 方案 A：完全替换（适用于全新页面）

1. **备份当前 page 目录（可选但推荐）**
   ```bash
   # 创建备份
   Copy-Item -Path page -Destination page.backup -Recurse -Force
   ```

2. **清空 page 目录**
   ```bash
   # 删除 page 目录内容，保留目录本身
   Remove-Item -Path page\* -Recurse -Force
   ```

3. **复制新代码到 page 目录**
   ```bash
   # 从 refs 目录复制新代码
   Copy-Item -Path refs\your_project_name\* -Destination page -Recurse -Force
   ```

#### 方案 B：增量更新（适用于部分功能更新）

1. **识别需要更新的文件**
   - 对比 `refs/your_project_name/` 和 `page/` 目录
   - 确定哪些文件需要新增、修改或删除

2. **逐个更新文件**
   ```bash
   # 示例：复制特定文件或目录
   Copy-Item -Path refs\your_project_name\src\pages\new_page -Destination page\src\pages -Recurse -Force
   Copy-Item -Path refs\your_project_name\package.json -Destination page -Force
   ```

### 第三步：更新项目配置

#### 1. 更新 Vite 配置

编辑 `page/vite.config.ts`，确保以下配置正确：

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

const base = process.env.BASE_PATH || "/static/";

export default defineConfig({
  plugins: [react()],
  base,
  build: {
    sourcemap: true,
    outDir: '../app/static',  // 重要：输出到 app/static 目录
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: "0.0.0.0",
  },
});
```

#### 2. 更新 React Router 配置

编辑 `page/src/App.tsx`，确保 basename 配置为根路径：

```tsx
import { BrowserRouter } from "react-router-dom";

function App() {
  return (
    <BrowserRouter basename="/">  {/* 重要：basename 设置为 / */}
      {/* 其他组件 */}
    </BrowserRouter>
  );
}
```

#### 3. 更新 package.json（如需要）

检查 `page/package.json`，确保脚本命令正确：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx"
  }
}
```

### 第四步：安装依赖和构建

1. **进入 page 目录**
   ```bash
   cd page
   ```

2. **安装依赖**
   ```bash
   # 使用淘宝镜像加速
   npm config set registry https://registry.npmmirror.com
   npm install
   ```

3. **开发模式测试**
   ```bash
   npm run dev
   # 访问 http://localhost:3000 测试
   ```

4. **生产构建**
   ```bash
   npm run build
   # 构建产物将输出到 ../app/static 目录
   ```

### 第五步：更新后端配置（如需要）

#### 检查 FastAPI 路由

通常不需要修改，但如果有新的 API 端点，需要更新：

1. **检查 `app/routes/pages.py`**
   - 确保能正确返回 React 应用的 index.html
   - 确保 catch-all 路由配置正确

2. **检查 `app/routes/api.py`**
   - 添加新的 API 端点（如需要）

3. **检查 `app/main.py`**
   - 确保路由注册顺序正确（API 路由在前，页面路由在后）

### 第六步：更新 Docker 配置

#### 1. 检查 Dockerfile

通常不需要修改，除非有特殊的构建需求。当前 `docker/Dockerfile` 应该已经：
- 包含多阶段构建
- 正确复制 `page/` 目录下的文件
- 正确复制构建产物到 `app/static/`

#### 2. 测试 Docker 构建

```bash
# 在项目根目录执行
docker compose up -d --build

# 查看日志
docker compose logs -f

# 测试访问
# 打开浏览器访问 http://localhost:8000
```

### 第七步：更新 Git 配置

#### 1. 检查 .gitignore

确保以下内容已包含在 `.gitignore` 中：

```
# Frontend - Node.js
page/node_modules/

# Frontend - Build outputs
app/static/*
!app/static/.gitkeep
!app/static/css/.gitkeep
!app/static/js/.gitkeep

# Frontend - Vite cache
page/.vite/

# Frontend - Auto-generated types
page/auto-imports.d.ts
```

#### 2. 提交更改

```bash
# 查看更改
git status

# 添加更改
git add page/
git add app/static/  # 仅在需要提交构建产物时（通常不建议）
git add docker/Dockerfile
git add .gitignore

# 提交
git commit -m "feat: 更新前端页面，添加新功能"

# 推送到远程仓库
git push
```

## 常见问题处理

### 问题 1：React Router 不渲染页面

**错误信息：**
```
<Router basename="/static/"> is not able to match the URL "/"
```

**解决方案：**
修改 `page/src/App.tsx`：
```tsx
<BrowserRouter basename="/">  {/* 改为 "/" */}
```

### 问题 2：静态资源 404

**原因：** Vite 的 base 配置不正确

**解决方案：**
修改 `page/vite.config.ts`：
```typescript
const base = process.env.BASE_PATH || "/static/";  // 确保是 "/static/"
```

### 问题 3：构建产物路径错误

**解决方案：**
检查 `page/vite.config.ts` 的 build.outDir：
```typescript
build: {
  outDir: '../app/static',  // 确保是相对路径
}
```

### 问题 4：依赖安装失败

**解决方案：**
```bash
cd page
# 清除缓存
rm -rf node_modules package-lock.json
# 重新安装
npm config set registry https://registry.npmmirror.com
npm install
```

## 最佳实践

### 1. 迁移前
- ✅ 总是先在 refs 目录中检查代码
- ✅ 备份当前的 page 目录
- ✅ 阅读外部代码的 README（如有）

### 2. 迁移中
- ✅ 分步执行，每步验证
- ✅ 保留配置文件的关键设置（Vite base、Router basename）
- ✅ 及时提交小的变更

### 3. 迁移后
- ✅ 本地开发模式测试
- ✅ 生产构建测试
- ✅ Docker 部署测试
- ✅ 清理 refs 目录中的临时文件（可选）

## 快速参考命令

```bash
# 查看当前项目结构
Get-ChildItem -Force

# 前端开发
cd page
npm install
npm run dev
npm run build

# 后端开发
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Docker 部署
docker compose up -d --build
docker compose logs -f
docker compose down

# Git 操作
git status
git add .
git commit -m "描述信息"
git push
```

## 附录：文件清单

迁移时需要特别注意的配置文件：

- `page/vite.config.ts` - Vite 构建配置
- `page/src/App.tsx` - React Router 配置
- `page/package.json` - 依赖和脚本
- `docker/Dockerfile` - Docker 构建配置
- `.gitignore` - Git 忽略配置
- `app/routes/pages.py` - FastAPI 页面路由

---

**文档版本：** 1.0  
**最后更新：** 2026-04-02  
**维护者：** AetherFrame 开发团队
