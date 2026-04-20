// 백엔드 연결 실패 시 폴백으로 쓰는 목데이터.
// 실데이터는 /api/stocks 로 불러오고, 실패 시 이 데이터가 노출됩니다.

const generateMockHistory = (basePrice, count = 150) => {
  let price = basePrice;
  return Array.from({ length: count }, (_, i) => {
    const change = (Math.random() - 0.5) * 0.04;
    const open = price;
    const close = price * (1 + change);
    const high = Math.max(open, close) * (1 + Math.random() * 0.015);
    const low = Math.min(open, close) * (1 - Math.random() * 0.015);
    price = close;
    return {
      date: `2026-${String(Math.floor(i / 30) + 1).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}`,
      open,
      high,
      low,
      close,
      volume: Math.floor(Math.random() * 3_000_000) + 200_000,
    };
  });
};

export const MOCK_STOCKS = [
  // ── 반도체 ──────────────────────────────────────────────────────────────
  {
    code: '000660', name: 'SK하이닉스', sector: '반도체',
    is_leader: true, leader_name: 'SK하이닉스',
    buy_score: 95, rsi: 72, rsi_prev: 60, profit_growth_years: 1,
    price: 185000, change: -0.5,
    market_cap_trillion: 134.7, dividend_yield: 0.4,
    history: generateMockHistory(185000),
    financials: { revenue: '45.1조', profit: '8.2조', roe: '15.1%',
      desc: 'HBM 시장 독점적 지위 확보로 섹터 내 가장 강력한 주도주 모멘텀 보유.' },
  },
  {
    code: '005930', name: '삼성전자', sector: '반도체',
    is_leader: false, leader_name: 'SK하이닉스',
    buy_score: 74, rsi: 68, rsi_prev: 48, profit_growth_years: 3,
    price: 72500, change: 1.2,
    market_cap_trillion: 432.8, dividend_yield: 2.1,
    history: generateMockHistory(72500),
    financials: { revenue: '302.2조', profit: '35.8조', roe: '12.5%',
      desc: '메모리 업황 회복세가 뚜렷하며 3년 연속 영업이익 우상향 기조 유지 중.' },
  },
  {
    code: '042700', name: '한미반도체', sector: '반도체',
    is_leader: false, leader_name: 'SK하이닉스',
    buy_score: 83, rsi: 65, rsi_prev: 55, profit_growth_years: 4,
    price: 96000, change: 2.8,
    market_cap_trillion: 9.8, dividend_yield: 0.8,
    history: generateMockHistory(96000),
    financials: { revenue: '5.2조', profit: '1.4조', roe: '28.3%',
      desc: 'HBM 패키징 장비 독점 수혜, 4년 연속 영업이익 성장세.' },
  },
  // ── 자동차 ──────────────────────────────────────────────────────────────
  {
    code: '005380', name: '현대차', sector: '자동차',
    is_leader: true, leader_name: '현대차',
    buy_score: 88, rsi: 58, rsi_prev: 45, profit_growth_years: 4,
    price: 250000, change: 2.1,
    market_cap_trillion: 53.2, dividend_yield: 3.8,
    history: generateMockHistory(250000),
    financials: { revenue: '162.7조', profit: '15.1조', roe: '10.8%',
      desc: '하이브리드 및 전기차 믹스 개선으로 역대 최대 실적 경신 중.' },
  },
  {
    code: '000270', name: '기아', sector: '자동차',
    is_leader: false, leader_name: '현대차',
    buy_score: 82, rsi: 55, rsi_prev: 42, profit_growth_years: 3,
    price: 95500, change: 1.8,
    market_cap_trillion: 38.4, dividend_yield: 4.2,
    history: generateMockHistory(95500),
    financials: { revenue: '99.8조', profit: '11.6조', roe: '16.2%',
      desc: 'SUV 믹스 개선과 미국 시장 호조로 역대 최대 수준 영업이익 유지.' },
  },
  // ── 2차전지 ─────────────────────────────────────────────────────────────
  {
    code: '373220', name: 'LG에너지솔루션', sector: '2차전지',
    is_leader: true, leader_name: 'LG에너지솔루션',
    buy_score: 71, rsi: 52, rsi_prev: 44, profit_growth_years: 2,
    price: 382000, change: 0.8,
    market_cap_trillion: 89.4, dividend_yield: 0.0,
    history: generateMockHistory(382000),
    financials: { revenue: '33.7조', profit: '2.1조', roe: '6.3%',
      desc: '북미 IRA 수혜 및 원통형 배터리 수주 확대로 중장기 성장 궤도 진입.' },
  },
  {
    code: '006400', name: '삼성SDI', sector: '2차전지',
    is_leader: false, leader_name: 'LG에너지솔루션',
    buy_score: 65, rsi: 48, rsi_prev: 40, profit_growth_years: 1,
    price: 278000, change: -1.2,
    market_cap_trillion: 19.1, dividend_yield: 0.9,
    history: generateMockHistory(278000),
    financials: { revenue: '22.7조', profit: '1.6조', roe: '5.8%',
      desc: '전기차 수요 둔화 영향 하에서도 전고체 배터리 선점 전략 유지.' },
  },
  // ── 인터넷 ──────────────────────────────────────────────────────────────
  {
    code: '035420', name: 'NAVER', sector: '인터넷',
    is_leader: true, leader_name: 'NAVER',
    buy_score: 67, rsi: 45, rsi_prev: 42, profit_growth_years: 2,
    price: 192000, change: 0.5,
    market_cap_trillion: 31.5, dividend_yield: 0.6,
    history: generateMockHistory(192000),
    financials: { revenue: '9.6조', profit: '1.4조', roe: '8.2%',
      desc: '광고 및 커머스 성장세는 안정적이나 신사업 투자 비용 증가 추세.' },
  },
  {
    code: '035720', name: '카카오', sector: '인터넷',
    is_leader: false, leader_name: 'NAVER',
    buy_score: 51, rsi: 38, rsi_prev: 35, profit_growth_years: 0,
    price: 38500, change: -0.9,
    market_cap_trillion: 17.1, dividend_yield: 0.0,
    history: generateMockHistory(38500),
    financials: { revenue: '7.8조', profit: '0.3조', roe: '2.1%',
      desc: '규제 리스크와 콘텐츠 비용 부담으로 수익성 회복이 지연되는 상황.' },
  },
  // ── 바이오 ──────────────────────────────────────────────────────────────
  {
    code: '207940', name: '삼성바이오로직스', sector: '바이오',
    is_leader: true, leader_name: '삼성바이오로직스',
    buy_score: 79, rsi: 61, rsi_prev: 50, profit_growth_years: 3,
    price: 872000, change: 1.5,
    market_cap_trillion: 58.3, dividend_yield: 0.0,
    history: generateMockHistory(872000),
    financials: { revenue: '4.8조', profit: '1.6조', roe: '11.4%',
      desc: '글로벌 CMO 수주 확대로 5공장 조기 완공 추진, 실적 가시성 높음.' },
  },
  {
    code: '068270', name: '셀트리온', sector: '바이오',
    is_leader: false, leader_name: '삼성바이오로직스',
    buy_score: 73, rsi: 58, rsi_prev: 47, profit_growth_years: 2,
    price: 163000, change: 0.9,
    market_cap_trillion: 22.8, dividend_yield: 0.5,
    history: generateMockHistory(163000),
    financials: { revenue: '3.9조', profit: '0.9조', roe: '8.7%',
      desc: '램시마SC·트룩시마 등 바이오시밀러 글로벌 시장 점유 확대 중.' },
  },
  // ── 금융 ────────────────────────────────────────────────────────────────
  {
    code: '105560', name: 'KB금융', sector: '금융',
    is_leader: true, leader_name: 'KB금융',
    buy_score: 76, rsi: 60, rsi_prev: 52, profit_growth_years: 3,
    price: 89200, change: 0.6,
    market_cap_trillion: 36.6, dividend_yield: 5.1,
    history: generateMockHistory(89200),
    financials: { revenue: '18.3조', profit: '5.1조', roe: '9.4%',
      desc: '순이자마진 안정과 자본비율 개선으로 고배당 기조 유지.' },
  },
  {
    code: '055550', name: '신한지주', sector: '금융',
    is_leader: false, leader_name: 'KB금융',
    buy_score: 72, rsi: 57, rsi_prev: 49, profit_growth_years: 2,
    price: 52800, change: 0.4,
    market_cap_trillion: 25.3, dividend_yield: 4.8,
    history: generateMockHistory(52800),
    financials: { revenue: '15.7조', profit: '4.2조', roe: '8.6%',
      desc: '베트남 등 해외 이익 비중 확대로 성장성 개선, 배당 안정성 높음.' },
  },
  // ── 통신 ────────────────────────────────────────────────────────────────
  {
    code: '017670', name: 'SK텔레콤', sector: '통신',
    is_leader: true, leader_name: 'SK텔레콤',
    buy_score: 68, rsi: 53, rsi_prev: 50, profit_growth_years: 2,
    price: 52300, change: 0.2,
    market_cap_trillion: 12.8, dividend_yield: 6.3,
    history: generateMockHistory(52300),
    financials: { revenue: '17.6조', profit: '1.6조', roe: '7.8%',
      desc: 'AI 인프라 투자 확대, 배당 6%대 고배당주로 안정적 수요.' },
  },
  // ── 철강 ────────────────────────────────────────────────────────────────
  {
    code: '005490', name: 'POSCO홀딩스', sector: '철강',
    is_leader: true, leader_name: 'POSCO홀딩스',
    buy_score: 63, rsi: 46, rsi_prev: 42, profit_growth_years: 1,
    price: 312000, change: -0.6,
    market_cap_trillion: 26.5, dividend_yield: 3.5,
    history: generateMockHistory(312000),
    financials: { revenue: '77.1조', profit: '1.2조', roe: '2.8%',
      desc: '리튬 사업부 가치 재평가 및 철강 업황 회복 기대감 반영.' },
  },
];

// 지수 목데이터
export const MOCK_INDICES = [
  { idx_code: 'KOSPI',  idx_name: '코스피',  date: '2026-04-19', close: 2650.3,  change_pct: 0.52 },
  { idx_code: 'KOSDAQ', idx_name: '코스닥',  date: '2026-04-19', close: 860.7,   change_pct: -0.21 },
  { idx_code: 'KRX300', idx_name: 'KRX300', date: '2026-04-19', close: 1820.1,  change_pct: 0.38 },
];

// 원자재 목데이터
export const MOCK_COMMODITIES = [
  { code: 'GOLD',      name: '금',     date: '2026-04-19', close: 480250, unit: '원/g' },
  { code: 'DUBAI_OIL', name: '두바이유', date: '2026-04-19', close: 74.3,   unit: '$/배럴' },
  { code: 'WTI',       name: 'WTI',    date: '2026-04-19', close: 72.1,   unit: '$/배럴' },
];
