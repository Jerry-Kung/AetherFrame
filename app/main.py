import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import pages, api

app = FastAPI()

# 使用绝对路径，避免路径问题
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(pages.router)
app.include_router(api.router)
