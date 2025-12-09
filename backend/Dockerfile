FROM python:3.10-slim

WORKDIR /app

# ✅ Tesseract OCR 설치 (한국어/영어 지원)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-kor \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# FastAPI 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]

