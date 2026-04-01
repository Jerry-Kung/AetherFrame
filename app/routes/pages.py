import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

# 获取静态文件目录路径
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
index_path = os.path.join(static_dir, "index.html")


@router.get("/")
async def index():
    # 如果构建后的 index.html 存在，返回它；否则返回简单页面
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "React app not built yet. Please run 'npm run build' first."}


# 为 React 路由提供 fallback - 确保所有路由都返回 index.html
@router.get("/{path:path}")
async def catch_all(path: str):
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "React app not built yet. Please run 'npm run build' first."}
