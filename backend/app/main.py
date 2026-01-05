from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine, SessionLocal
from .models import User
from .utils import hash_password
from .routers import auth, users, datasets, submissions, leaderboard, apitest
import logging
import os

logging.basicConfig(
    level=os.getenv("APP_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="LUNA25 Evaluation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    """Initialize database with tables and seed data."""
    from .seeders import seed_all

    # Create database tables (only when explicitly requested)
    Base.metadata.create_all(bind=engine)

    # Seed initial data
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()

init_db()


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(datasets.router)
app.include_router(submissions.router)
app.include_router(leaderboard.router)
app.include_router(apitest.router)
# Note: apitest router endpoints are available at both /apitest/* and via the /api prefix
# This makes them accessible at /api/apitest/v1/predict/lesion for consistency

@app.get("/")
def root():
    return {"message": "LUNA25 Evaluation API is running"}
