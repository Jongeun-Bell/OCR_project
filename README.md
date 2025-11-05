# 🧾 Spendy
> **영수증 기반 소비 심리 분석 서비스 (Receipt-based Spending Psychology Analyzer)**  
> AI Cloud Bootcamp | 2025

## 🚀 Overview
**Spendy**는 영수증 OCR 기술을 활용해 개인의 소비 패턴을 자동 분석하고,  
**VALS(Values and Lifestyles)** 심리 모델 기반의 소비 성향을 분석해주는  
**개인 재무 관리 서비스**입니다.

📸 **영수증 업로드 → 💬 자동 인식 → 📊 소비 통계 + 🐰 심리 캐릭터 분석**

---

## 💡 Key Features
- **OCR 자동 인식** (Google Cloud Vision API)
- **결과 즉시 수정** 기능 (저장 전)
- **소비 카테고리 분류 (7가지)**
- **VALS 4가지 성향 분석** 🦊🐻🐰🐼
- **월간 통계 파이차트 시각화**
- **SQLite 기반 로컬 데이터 저장**
- **모노톤 디자인 + 캐릭터형 피드백**

---

## 🧠 VALS Model Simplification
VALS 원래 모델은 8개 타입이지만, Spendy는 이해도와 개발 효율을 위해 **4개 타입**만 사용합니다.

| 타입 | 캐릭터 | 설명 |
|------|--------|------|
| 🦊 **Trendsetter** | 쇼핑 중심, 트렌드 리더형 |
| 🐻 **Thinker** | 장보기·계획형 소비자 |
| 🐰 **Experiencer** | 외식·여가 중심의 경험추구형 |
| 🐼 **Believer** | 절약·균형형, 합리소비 추구 |

**간소화 이유**
- 7일 내 완성 목표로 개발 기간 단축
- 사용자 이해도 향상 (8개보다 직관적)
- 알고리즘 단순화 및 캐릭터 제작 부담 완화

---

## 🧩 Tech Stack

| 구분 | 기술 | 설명 |
|------|------|------|
| **Frontend** | React, Tailwind CSS | 컴포넌트 기반, 빠른 UI 개발 |
| **Backend** | Node.js, Express | RESTful API, 비동기 처리 |
| **Database** | SQLite | 로컬 개발, 간편 배포 |
| **OCR** | Google Cloud Vision API | 높은 인식률, 쉬운 연동 |
| **Infra** | Vercel (FE), Kakao Cloud Ubuntu (BE) | 무료 CI/CD 환경 및 서버 호스팅 |

---

## 🗄️ Database Schema

### receipts
```sql
CREATE TABLE receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT NOT NULL,
    store_name TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK(amount > 0),
    category TEXT NOT NULL CHECK(category IN 
        ('Dining out','Groceries','Shopping','Entertainment',
         'Transportation','Subscription','Others')),
    receipt_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
### monthly_stats
```
CREATE TABLE monthly_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month TEXT NOT NULL,
    category TEXT NOT NULL,
    total_amount INTEGER NOT NULL,
    count INTEGER NOT NULL,
    avg_amount INTEGER,
    UNIQUE(year_month, category)
);
```

### vals results 
```
CREATE TABLE vals_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month TEXT NOT NULL UNIQUE,
    vals_type TEXT NOT NULL,
    score_trendsetter REAL,
    score_thinker REAL,
    score_experiencer REAL,
    score_believer REAL,
    total_receipts INTEGER,
    total_amount INTEGER
);
```

### 🔚 API Endpoint

| Method | Endpoint               | 설명              |
| ------ | ---------------------- | --------------- |
| POST   | `/api/receipts/upload` | OCR 인식 (저장 안 함) |
| POST   | `/api/receipts`        | 영수증 저장          |
| GET    | `/api/receipts`        | 전체 목록           |
| GET    | `/api/receipts/:id`    | 상세 조회           |
| PUT    | `/api/receipts/:id`    | 수정              |
| DELETE | `/api/receipts/:id`    | 삭제              |
| GET    | `/api/stats/monthly`   | 월별 통계           |
| GET    | `/api/vals/analyze`    | VALS 분석 결과      |

### 📱 주요 화면 구성

| 화면                      | 기능 요약            |
| ----------------------- | ---------------- |
| **Splash**              | 앱 로딩 + 로고 표시     |
| **Upload Home**         | 영수증 업로드 및 OCR 처리 |
| **Check Your Purchase** | OCR 결과 수정 후 저장   |
| **Purchase List**       | 월별 소비 목록 확인/삭제   |
| **Purchase Details**    | 상세 수정            |
| **Statistics**          | 파이차트 + VALS 결과   |
| **Sign Up (UI only)**   | 향후 회원가입 대비       |

### 7 - Day MVP Timeline

| Day     | 단계        | 주요 작업                         |
| ------- | --------- | ----------------------------- |
| **1**   | 기획 및 설계   | 요구사항 정의, DB 스키마               |
| **2-3** | 백엔드 구축    | Express, SQLite, OCR 연동       |
| **4-5** | 프론트 UI    | React, Tailwind 구현            |
| **6**   | VALS 알고리즘 | 분석 로직 적용                      |
| **7**   | QA & 배포   | 테스트 및 Vercel + Kakao Cloud 배포 |

### 📊 기대효과

| 항목        | Before | After   |
| --------- | ------ | ------- |
| 데이터 입력 시간 | 5분     | 10초     |
| 인식 정확도    | 70%    | 85%↑    |
| 사용자 지속률   | 낮음     | +30% 향상 |

### ⚠️ 리스크 관리

| 리스크        | 확률 | 대응 방안        |
| ---------- | -- | ------------ |
| OCR 인식률 저조 | 중  | 수동 수정 UI 제공  |
| API 한도 초과  | 낮음 | 모니터링 및 요청 제한 |
| 일정 지연      | 중  | 핵심 기능 우선 개발  |

### 🌱 향후 확장 계획
- 회원가입 / 로그인 기능
- AI 기반 자동 카테고리 분류
- 예산 초과 알림
- 다크모드 지원

#### 📜 License
MIT © 2025 Jong W.