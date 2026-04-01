from fastapi import APIRouter
from app.services.file_service import read_hello_file

router = APIRouter(prefix="/api")


@router.get("/hello")
async def get_hello():
    success, result = read_hello_file()
    if success:
        return {"success": True, "content": result}
    else:
        return {"success": False, "error": result}
