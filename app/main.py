from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import pages, api

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(api.router)
