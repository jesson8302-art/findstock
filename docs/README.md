# StockNLP · 자연어 종목 검색 MVP

> "RSI 55~75 사이, 3년 연속 영업이익 상승인 반도체 섹터 주도주" 같은 자연어를
> Gemini로 파싱 → 한국 주식 데이터에서 걸러 보여주는 단일 페이지 앱.

## 폴더 구조

```
종목자연어검색/
├── frontend/          # Vite + React + Tailwind
│   ├── src/App.jsx    # UI 메인 (검색창 + 결과 + 차트 + 마이페이지)
│   ├── src/lib/api.js # 백엔드 호출
│   └── src/data/mockStocks.js
├── backend/           # FastAPI + Supabase + Gemini
│   ├── app.py               # /api/* 엔드포인트
│   ├── data_collector.py    # 공공데이터 → Supabase 배치
│   ├── indicators.py        # RSI / 매수 점수
│   └── gemini_client.py     # 자연어 → 필터 JSON
└── docs/
    ├── setup_flow.md  # 실행 가이드 (여기부터 보세요)
    └── schema.sql     # Supabase DDL
```

## 빠른 시작

```bash
# 백엔드 없이 UI만 먼저 확인
cd frontend && npm install && npm run dev

# 풀 스택 실행은 docs/setup_flow.md 참고
```

## MVP 범위

- [x] 자연어 → 필터 JSON 변환 (Gemini + 정규식 폴백)
- [x] RSI / 영업이익 연속성장 / 섹터 주도주 기반 필터링
- [x] 캔들차트 + 이평선(5/20/60/120/240) 토글
- [x] 섹터 내 위상 + DART 재무 요약 카드
- [x] 최근 검색 / 북마크 (세션 내 메모리)
- [ ] DART 실제 연동 (재무 JSON 채우기)
- [ ] 검색/북마크 서버 저장
- [ ] 인증 (유저별 데이터 분리)

## 스택

- **Frontend**: Vite, React 18, Tailwind, lucide-react, SVG 기반 자체 차트
- **Backend**: FastAPI, pandas, Supabase Python SDK
- **LLM**: Gemini 2.5 Flash (`google-generativeai`)
- **DB**: Supabase Postgres
