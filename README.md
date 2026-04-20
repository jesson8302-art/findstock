# StockNLP · 자연어 종목 검색 서비스

> "RSI 55~75, 시총 30조 이상, 3년 연속 영업이익 상승 주도주" 같은 문장으로 종목을 찾는 AI 검색 서비스

**스택:** React 18 + Vite + Tailwind · FastAPI + Supabase · Gemini 2.5 Flash  
**데이터:** 공공데이터포털 금융위원회 5개 API (상업적 이용 가능, 무료)

---

## 배포 구조

```
GitHub 저장소
├── frontend/   →  Netlify (정적 사이트, 무료)
└── backend/    →  Render.com (Python FastAPI, 무료)
```

---

## STEP 1 — GitHub에 올리기

```bash
cd 종목자연어검색
git init
git add .
git commit -m "feat: StockNLP MVP"

# GitHub에서 새 저장소 만든 후:
git remote add origin https://github.com/YOUR_USER/stocknlp.git
git push -u origin main
```

---

## STEP 2 — Supabase 스키마 적용

1. [supabase.com](https://supabase.com) → 프로젝트 → **SQL Editor**
2. `docs/schema_full.sql` 전체 복사 → 붙여넣기 → **Run**

---

## STEP 3 — Render 백엔드 배포

1. [render.com](https://render.com) → **New Web Service** → GitHub 연결
2. 저장소 선택 → Render가 `render.yaml` 자동 인식
3. **Environment Variables** 탭에서 아래 값 입력:

| 변수명 | 값 위치 |
|--------|--------|
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API Keys → service_role |
| `SUPABASE_ANON_KEY` | 같은 페이지 anon |
| `PUBLIC_DATA_KEY` | data.go.kr 마이페이지 → 활용신청 목록 |
| `DART_API_KEY` | opendart.fss.or.kr → 인증키 신청 |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key |

4. **Create Web Service** 클릭 → 배포 완료 후 URL 복사  
   (예: `https://stocknlp-api.onrender.com`)

---

## STEP 4 — 데이터 시드 (최초 1회, 약 15분)

**방법 A — Render Shell** (권장):  
Render 대시보드 → 서비스 → **Shell** 탭:
```bash
python data_collector.py --seed
python data_collector.py --dart   # DART 재무 (선택)
```

**방법 B — 로컬에서 실행**:
```bash
cd backend
pip install -r requirements.txt
python data_collector.py --seed
```

---

## STEP 5 — Netlify 프론트엔드 배포 🚀

1. [netlify.com](https://netlify.com) → **Add new site** → **Import from Git**
2. GitHub 저장소 선택 → Netlify가 `netlify.toml` 자동 인식
3. **Environment variables** 추가:

| 변수명 | 값 |
|--------|---|
| `VITE_API_BASE` | Render URL (예: `https://stocknlp-api.onrender.com`) |

4. **Deploy site** 클릭 → 완료!

---

## 로컬 개발

```bash
# 터미널 1 — 백엔드
cd backend && pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# 터미널 2 — 프론트엔드
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

---

## 기능

- **자연어 검색** — RSI / 섹터 / 주도주 / 시총 / 배당 필터 (Gemini AI + 로컬 정규식 폴백)
- **퀵서치 버튼** — 주도주 / 배당 4%↑ / 시총 50조↑ 등 7개 원클릭 검색
- **지수 티커바** — KOSPI / KOSDAQ / KRX300 + 금 / 두바이유 / WTI 실시간
- **캔들차트** — MA5/10/20/60/120/240, 거래량 바, 범위 슬라이더
- **상세 패널** — 현재가 / RSI / 시총 / 배당 4-stat + DART 재무 요약
- **마이페이지** — 검색 기록 + 관심종목 북마크
- **폴백 설계** — 백엔드 없어도 Mock 데이터로 UI 완전 동작
