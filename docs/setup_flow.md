# StockNLP · 실데이터 연동 가이드

> pykrx(API 키 불필요) + Supabase로 실제 한국 주식 데이터를 서빙하는 전체 흐름입니다.

---

## 0. 빠른 미리보기 (백엔드 없이)

```bash
open 종목자연어검색/stocknlp_demo.html
# → 브라우저에서 바로 열기 (mock 데이터 동작)
```

---

## 1. Supabase 프로젝트 준비

1. [supabase.com](https://supabase.com) → 새 프로젝트 생성 (free tier OK)
2. **SQL Editor** → `docs/schema.sql` 전체를 붙여넣고 **Run**
3. **Settings > API** 에서 3가지 복사:
   - `Project URL` → SUPABASE_URL
   - `anon` public key → SUPABASE_ANON_KEY
   - `service_role` secret key → SUPABASE_SERVICE_ROLE_KEY

---

## 2. 백엔드 .env 설정

```bash
cd 종목자연어검색/backend
cp .env.example .env
# 텍스트 에디터로 .env 열고 값 채우기
```

---

## 3. 파이썬 환경 & 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> pykrx 포함 — 공공데이터포털 API 키 없이 KRX 데이터를 바로 수집합니다.

---

## 4. 최초 데이터 시드 (1회만)

```bash
python data_collector.py --seed
# 43개 종목, 6개월 OHLCV + RSI/buy_score → Supabase 적재
# 약 5~8분 소요 (KRX 서버 부하 방지 딜레이 포함)
```

완료 후 Supabase 대시보드 Table Editor → stocks 에서 확인.

---

## 5. 백엔드 서버 실행

```bash
uvicorn app:app --reload --port 8000
```

```bash
curl http://localhost:8000/api/health
# → {"ok":true,"supabase":true,...}

curl http://localhost:8000/api/stocks | python -m json.tool | head -50
```

---

## 6. 프론트엔드 실행

```bash
cd ../frontend
npm install && npm run dev
# → http://localhost:5173
```

화면 우측 상단 배지가 "· Supabase" 로 바뀌면 실데이터 연결 성공!

---

## 7. 일별 업데이트 자동화

```bash
# crontab -e (매일 오후 4시 30분, 장 마감 후)
30 16 * * 1-5  cd /path/to/backend && .venv/bin/python data_collector.py --daily
```

---

## 8. DART 재무 데이터 연동 (선택)

```bash
# .env 에 DART_API_KEY 추가 후 (opendart.fss.or.kr 에서 발급)
python data_collector.py --dart
# 분기별 1회 권장
```

---

## 수집 대상 종목 (43개)

| 섹터 | 주도주 | 포함 종목 |
|------|--------|-----------|
| 반도체 | SK하이닉스 | 삼성전자, 삼성전기, 한미반도체, 리노공업 |
| 자동차 | 현대차 | 기아, 현대모비스, 현대위아 |
| 2차전지 | LG에너지솔루션 | 삼성SDI, LG화학, 에코프로비엠, 에코프로 |
| 인터넷 | NAVER | 카카오, 크래프톤 |
| 바이오 | 삼성바이오로직스 | 셀트리온, 유한양행, 한미약품 |
| 금융 | KB금융 | 신한지주, 하나금융지주, 우리금융지주, 삼성생명 |
| 철강 | POSCO홀딩스 | 현대제철 |
| 화학 | LG화학 | 한화솔루션, 롯데케미칼 |
| 통신 | SK텔레콤 | KT, LG유플러스 |
| 건설 | 현대건설 | GS건설 |
| 유통 | 이마트 | 롯데쇼핑 |
| 엔터 | HYBE | SM엔터, JYP엔터 |
| 게임 | 엔씨소프트 | 넷마블, 카카오게임즈 |
