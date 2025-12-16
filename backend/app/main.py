from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import health, research

app = FastAPI(
    title=settings.APP_NAME,
    description="AI Research Agent",
    version="0.1.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 기본 포트
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health.router, tags=["health"])
app.include_router(research.router, prefix="/api/research", tags=["research"])


@app.on_event("startup")
async def startup_event():
    print(f"{settings.APP_NAME} 서버 시작")


@app.on_event("shutdown")
async def shutdown_event():
    print(f"{settings.APP_NAME} 서버 종료")