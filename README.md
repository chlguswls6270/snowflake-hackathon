# 🏙️ Q-Dong (큐동)
### AI가 큐레이션하는 나만의 동네 | Powered by Snowflake Cortex

> **"자연어 한 문장으로, 나에게 딱 맞는 서울의 동네를 찾아드립니다."**

Q-Dong은 Snowflake Marketplace의 3개 데이터셋(RichGo · SPH · AJD)을 교차 분석하고,  
Snowflake Cortex AI로 사용자의 자연어 조건을 14개 라이프스타일 파라미터로 해석하여  
예산과 라이프스타일에 가장 잘 맞는 서울 동(洞)을 지도 위에 큐레이션하는 웹 애플리케이션입니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|--|--|
| **자연어 동네 검색** | "신혼부부, 카페 좋아하고 교육 중요, 예산 9억" → AI가 14개 파라미터 JSON으로 자동 파싱 |
| **지도 시각화** | 서울 법정동 GeoJSON 기반 추천 동 폴리곤 시각화 + 자동 포커싱 |
| **동네 심층 Q&A** | 선택한 동네에 대해 Cortex AI에게 직접 질문 (서브챗 패널) |
| **렌탈 가전 추천** | AJD 실거래 데이터 기반으로 이사 후 필요한 렌탈 가전을 AI가 자동 추천 |

---

## 🛠️ 기술 스택

| 레이어 | 기술 |
|--|--|
| **AI** | Snowflake Cortex (`mistral-large2`) |
| **데이터** | Snowflake Snowpark, 3개 Marketplace DB |
| **백엔드** | Python 3.11 · FastAPI · Uvicorn |
| **프론트엔드** | Next.js 15 · Tailwind CSS · React-Leaflet |

---

## 📦 데이터셋 (Snowflake Marketplace)

앱을 실행하려면 아래 3개의 Snowflake Marketplace 데이터셋을 본인 계정에 마운트해야 합니다.

| 변수명 | Marketplace 데이터셋 이름 |
|--|--|
| `SNOWFLAKE_DB_RICHGO` | Korean Population & Apartment Market Price Data |
| `SNOWFLAKE_DB_SPH` | Seoul District-Level Data: Floating Population, Consumption and Assets |
| `SNOWFLAKE_DB_AJD` | South Korea Telecom Subscription Analytics: Contracts, Marketing and Call Center Insights by Region |

---

## 🚀 실행 방법

### 사전 요구사항
- Python **3.11** (검증한 실행 환경)
- Node.js **20.19+**

> 계정 비밀번호나 `.env` 파일은 저장소 및 배포 ZIP에 포함하지 않습니다.

---

### 1. 저장소 압축 해제 (또는 클론)

```bash
# ZIP 파일 압축 해제 후 해당 폴더로 이동
cd snowflake-hackathon
```

---

### 2. 백엔드 설정

```bash
cd backend

# Python 가상환경 생성 (반드시 Python 3.11 사용)
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

> **🔧 본인 Snowflake 계정 설정**  
> `backend/.env.example`을 복사하여 `.env`로 저장한 뒤,  
> 본인의 Snowflake 자격증명과 Marketplace DB 이름을 입력하세요.
> ```bash
> cp .env.example .env
> # .env 파일을 열어 내용 채우기
> ```

```bash
# 백엔드 서버 실행
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

`Application startup complete.` 메시지가 나오면 성공입니다.

---

### 3. 프론트엔드 설정

새 터미널 창을 열고:

```bash
cd frontend

# 패키지 설치
npm install

# 개발 서버 실행
npm run dev
```

브라우저에서 **`http://localhost:3000`** 을 열면 앱이 실행됩니다.

---

### ⚡ 한 눈에 보는 실행 순서

```
터미널 1 (백엔드)            │  터미널 2 (프론트엔드)
─────────────────────────   │  ──────────────────────────
cd backend                  │  cd frontend
python3.11 -m venv .venv    │  npm install
source .venv/bin/activate   │  npm run dev
pip install -r requirements.txt │
uvicorn app.main:app \      │
  --reload --port 8001      │
─────────────────────────   │  ──────────────────────────
→ localhost:8001 실행 확인  │  → localhost:3000 브라우저 열기
```

브라우저에서 **[http://localhost:3000](http://localhost:3000)** 접속

> 💡 백엔드(8001)와 프론트엔드(3000) 서버가 **둘 다** 실행 중이어야 정상 작동합니다.

---

## 📁 프로젝트 구조

```
snowflake-hackathon/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 엔드포인트 (3개 API)
│   │   └── database.py      # Snowflake 세션 관리
│   ├── .env.example         # 환경변수 템플릿 (→ .env로 복사 후 입력)
│   └── requirements.txt     # Python 의존성
│
├── frontend/
│   ├── src/app/
│   │   ├── components/
│   │   │   ├── ChatInput.js   # 메인 UI (검색 + 카드 패널)
│   │   │   ├── Map.js         # Leaflet 지도 컴포넌트
│   │   │   └── MapWrapper.js  # SSR 방지 래퍼
│   │   ├── page.js
│   │   └── globals.css
│   └── public/
│       └── seoul_geo_merged.json  # 서울 법정동 GeoJSON
│
└── README.md
```

---

## 🌐 API 엔드포인트

| Method | Path | 설명 |
|--|--|--|
| `POST` | `/api/analyze-prompt` | 자연어 → 14개 파라미터 JSON 파싱 (Cortex) |
| `POST` | `/api/recommend-apartments` | 동 단위 라이프스타일 매칭 스코어 연산 |
| `POST` | `/api/ask-dong` | 특정 동에 대한 Cortex Q&A |
| `POST` | `/api/rental-insight` | AJD 데이터 기반 렌탈 가전 AI 추천 |

API 문서: 백엔드 실행 후 `http://localhost:8001/docs` 접속

---

## ❗ 자주 발생하는 오류

| 오류 | 해결 방법 |
|--|--|
| `Address already in use` | 기존 서버 터미널에서 Ctrl+C로 종료하거나 다른 포트를 선택 |
| `Snowflake session error` | `.env` 파일의 계정 정보 및 DB 이름 재확인 |
| `Map not loading` | 프론트엔드가 `localhost:3000`에서 실행 중인지 확인 |
| Python 버전 오류 | `python3.11 -m venv .venv` 로 반드시 3.11 사용 |

---

*Snowflake AI & Data Hackathon 2026*

## 보안 설정

`backend/.env`에 32자 이상의 무작위 `DEMO_ACCESS_TOKEN`을 설정하세요. 브라우저에서 분석할 때 접근 코드를 입력합니다. 코드를 비워두면 API가 차단됩니다. 로컬에서만 테스트하려면 `ALLOW_LOCAL_DEMO=true`로 명시하고 서버를 `127.0.0.1`에 바인딩하세요. 배포 시 `ALLOWED_ORIGINS`와 프론트엔드의 공개 URL 설정 `NEXT_PUBLIC_API_BASE_URL`을 지정하세요. 상세 내용은 [SECURITY.md](SECURITY.md)를 참고하세요.

