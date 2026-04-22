// 백엔드(FastAPI) 프록시 클라이언트.
// dev에서는 Vite proxy(/api → localhost:8000)를 태우고,
// prod에서는 VITE_API_BASE 환경변수를 쓴다.

const BASE = import.meta.env.VITE_API_BASE?.replace(/\/$/, '') || '';

async function request(path, init) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${path} ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export const api = {
  // GET /api/stocks → 종목 리스트 + 최근 지표
  listStocks: () => request('/api/stocks'),

  // GET /api/stocks/:code/history → 차트용 과거 가격
  stockHistory: (code) => request(`/api/stocks/${code}/history`),

  // GET /api/indices → KOSPI/KOSDAQ/KRX300 최신 지수
  listIndices: () => request('/api/indices'),

  // GET /api/commodities → 금/원유/구리 최신 시세
  listCommodities: () => request('/api/commodities'),

  // POST /api/parse-query → Gemini 기반 자연어 → 필터 JSON
  parseQuery: (text) =>
    request('/api/parse-query', {
      method: 'POST',
      body: JSON.stringify({ query: text }),
    }),

  // POST /api/search → parseQuery + listStocks 필터를 서버사이드에서 수행
  search: (text) =>
    request('/api/search', {
      method: 'POST',
      body: JSON.stringify({ query: text }),
    }),

  // GET /api/stocks/:code/dart → 실시간 DART 재무 4년치
  stockDart: (code) => request(`/api/stocks/${code}/dart`),

  // GET /api/stocks/:code/disclosures → 최근 공시 목록
  stockDisclosures: (code, days = 90) => request(`/api/stocks/${code}/disclosures?days=${days}`),
};
