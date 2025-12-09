import logging
logging.basicConfig(level=logging.DEBUG)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.database import engine
from database import models
from routers import receipts

# DB 모델 생성
models.Base.metadata.create_all(bind=engine)

# FastAPI 인스턴스 생성
app = FastAPI(
    title="Spendy API",
    description="영수증 기반 소비 심리 분석 API",
    version="1.0.0"
)


# 업로드 폴더 정적 파일 제공
app.mount("/api/uploads", StaticFiles(directory="uploads"), name="uploads")

# static 폴더도 정적 파일 제공
# app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(receipts.router)

# 기본 루트
@app.get("/")
def root():
    return {
        "message": "Spendy API Server",
        "version": "1.0.0",
        "status": "running"
    }


# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# 앱 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

