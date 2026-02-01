# app/main.py
from pathlib import Path


from fastapi import FastAPI, Security
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.security import APIKeyHeader
from app.routes import router
from app.db import Base, engine
import app.models

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI()

# Ensure all models are registered before creating tables
Base.metadata.create_all(bind=engine)

# Define API Key security scheme
api_key_scheme = APIKeyHeader(name="x-admin-key", auto_error=False)

# Apply security scheme to /admin/* router
for r in router.routes:
    if hasattr(r, "path") and r.path.startswith("/admin"):
        if hasattr(r, "dependencies"):
            r.dependencies.append(Security(api_key_scheme))


app.include_router(router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")