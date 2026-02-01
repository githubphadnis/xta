import os
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text


from app.core.config import settings
from app.db.session import get_db
from app.routers import upload

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

# ---------------------------------------------------------
# 1. Static Files & Templates Setup
# ---------------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(upload.router)

# ---------------------------------------------------------
# 2. Routes
# ---------------------------------------------------------

@app.get("/")
def read_root(request: Request):
    """
    Renders the Dashboard HTML using Jinja2.
    """
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_name": settings.PROJECT_NAME,
        "environment": "production" # or dev, can be pulled from settings
    })

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
     robust health check.
    1. Verifies API is running.
    2. Pings the Database to ensure connectivity.
    """
    try:
        # Run a simple SQL query to check DB connection
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"

    return {
        "app_name": settings.PROJECT_NAME,
        "status": "online",
        "database": db_status
    }