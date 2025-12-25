from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# 모델 import (relationship 등록용)
from app.auth.models import User
from app.settings.models import UserSettings
from app.batch.models import BatchRun
from app.issues.models import Issue, IssueDailySnapshot, IssueArticle
from app.insights.models import IssueInsight

from app.auth.router import router as auth_router
from app.issues.router import router as issues_router, report_router
from app.batch.router import router as batch_router
from app.settings.router import router as settings_router
from app.content import router as content_router

app = FastAPI(
    title=settings.APP_NAME,
    description="AI Research Agent",
    version="0.1.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router, prefix="/api")
app.include_router(issues_router, prefix="/api")
app.include_router(report_router, prefix="/api")
app.include_router(batch_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(content_router, prefix="/api")

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}


@app.on_event("startup")
async def startup_event():
    print(f"{settings.APP_NAME} 서버 시작")


@app.on_event("shutdown")
async def shutdown_event():
    print(f"{settings.APP_NAME} 서버 종료")