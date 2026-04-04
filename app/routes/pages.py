import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope


class SPAAPIRoute(APIRoute):
    """
    SPA 回退路由不得参与 /api、/docs 等路径的匹配。

    否则对 ``POST /api/repair/tasks`` 等请求：若因尾随斜杠等与 API 路由未完全匹配，
    会只剩 ``GET /{path:path}`` 的「路径命中、方法不符」的 PARTIAL 匹配，
    Starlette 会返回 405 且 Allow: GET（易被误判为「不允许 POST」）。
    """

    def matches(self, scope: Scope):
        if scope.get("type") == "http":
            path = scope.get("path") or ""
            if path.startswith("/api") or path.startswith("/docs") or path.startswith(
                "/openapi"
            ) or path.startswith("/redoc"):
                return Match.NONE, {}
        return super().matches(scope)


router = APIRouter(route_class=SPAAPIRoute)

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
