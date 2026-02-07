# 🦦 Otter Diary Backend

사주 기반 **데일리 다이어리 앱**의 백엔드 서버입니다.  
아침에는 오늘의 운세를 확인하고,  
밤에는 하루 1번 일기를 쓰면  
해달 캐릭터가 사주 요소를 은근히 녹여 **피드백 편지**를 전달합니다.

---

## 📌 프로젝트 개요

### 한 줄 요약
> 사주를 설명하지 않고, **하루의 리듬과 감정 흐름**으로 해석해주는  
> 데일리 다이어리 백엔드 API 서버

### 핵심 컨셉
- 하루 사용 흐름을 **3번으로 제한**
  - 아침: 오늘의 운세
  - 밤: 일기 작성
  - 이후: 해달의 피드백 편지
- 사주를 **지식이 아닌 감정/컨디션 언어**로 해석
- 기능 과잉 없이, **습관 형성에 집중**

---

## 🛠 기술 스택

- **Language**: Python 3.10+
- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Auth**: JWT (OAuth2PasswordBearer)
- **DB**: PostgreSQL (개발 초기 SQLite 가능)
- **Migration**: Alembic
- **API Docs**: Swagger / OpenAPI

---

## 📂 프로젝트 구조

app/
├── api/ # API 라우터
├── core/ # 설정, DB, 보안
├── crud/ # DB CRUD 로직
├── models/ # SQLAlchemy 모델
├── schemas/ # Pydantic 스키마
├── services/ # 운세/편지 생성 로직
├── utils/ # 공용 유틸
├── main.py # FastAPI 진입점
└── router.py # 라우터 묶음


---

## 🧱 주요 기능

### 1️⃣ 인증 / 사용자
- 회원가입 / 로그인 / 로그아웃
- JWT 기반 인증
- 토큰 블랙리스트 관리

### 2️⃣ 사주 프로필
- 생년월일 / 출생시간 / 출생지 입력
- 사주 계산은 **저장하지 않고 생성 시 계산**

### 3️⃣ 오늘의 운세
- 유저당 하루 1개
- 애정운 / 학업·일 / 조심할 점 / 좋은 일 / 살풀이
- 사주 오행을 직접 드러내지 않고 힌트 형태로 제공

### 4️⃣ 일기
- 하루 1회 작성 제한
- 감정 태그 선택 가능

### 5️⃣ 해달 피드백 편지
- 일기 기반 자동 생성
- 사주 흐름 + 일기 감정 반영
- 일기 1개당 편지 1개 (1:1)

### 6️⃣ 알림 설정
- 운세 알림 / 일기 알림 ON/OFF
- 알림 시간 설정

---

## 🗄 데이터베이스 설계 요약

users
├─ user_birth_profiles (1:1)
├─ notification_settings (1:1)
├─ daily_fortunes (1:N)
├─ diary_entries (1:N)
│ └─ otter_letters (1:1)
└─ auth_tokens (1:N)


---

## 🚀 실행 방법

### 1️⃣ 환경 변수 설정

`.env`
```env
DATABASE_URL=postgresql://user:password@localhost:5432/otter_diary
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
2️⃣ 가상환경 및 의존성 설치
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
3️⃣ 서버 실행
uvicorn app.main:app --reload
4️⃣ API 문서
Swagger: http://localhost:8000/docs

Redoc: http://localhost:8000/redoc

🔮 향후 확장 계획
타로 리딩 기능 추가

LLM 기반 문장 생성 고도화

사용자 감정 패턴 분석

주간 / 월간 회고 리포트

📎 개발 원칙
하루 1회 제한은 DB 제약으로 보장

API는 멱등성을 최대한 유지

생성 로직과 CRUD 로직 분리

프론트엔드가 단순해지도록 서버에서 책임