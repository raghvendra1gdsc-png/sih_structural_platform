from fastapi import FastAPI
from backend.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

@app.get("/")
def read_root():
    return {"status": "ok", "stack": "FastAPI + PostGIS + Celery + PyTorch"}
