import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Search, TrendingUp, AlertCircle, Loader2, BarChart3, Zap,
  User, History, Bookmark, Trash2, Activity, Award, ChevronRight,
  TrendingDown, Minus,
} from 'lucide-react';
import { MOCK_STOCKS, MOCK_INDICES, MOCK_COMMODITIES } from './data/mockStocks.js';
import { api } from './lib/api.js';

// ──────────────────────────────────────────────────────────────────────────
// 상수
// ──────────────────────────────────────────────────────────────────────────
const QUICK_SEARCHES = [
  { label: '주도주 전체', query: '섹터 주도주 대장주 찾기' },
  { label: '배당 4% 이상', query: '배당수익률 4% 이상' },
  { label: '시총 50조↑ 주도주', query: '시총 50조 이상 주도주' },
  { label: 'RSI 50~70', query: 'RSI 50에서 70 사이' },
  { label: '반도체 섹터', query: '반도체 섹터' },
  { label: '금융 고배당', query: '금융 섹터 배당 4% 이상' },
  { label: '3년 연속 성장주', query: '3년 연속 영업이익 상승' },
];

const RSI_COLOR = (v) => {
  if (v >= 70) return 'text-red-500';
  if (v >= 50) return 'text-emerald-600';
  if (v >= 30) return 'text-yellow-500';
  return 'text-blue-400';
};

const fmt = (n) => (n != null ? n.toLocaleString() : '-');
const pct = (n, digits = 1) =>
  n != null ? `${n >= 0 ? '+' : ''}${n.toFixed(digits)}%` : '-';

// ──────────────────────────────────────────────────────────────────────────
// IndexBar — 상단 지수/원자재 티커
// ──────────────────────────────────────────────────────────────────────────
const IndexBar = ({ indices, commodities }) => {
  const items = [
    ...indices.map((idx) => ({
      key: idx.idx_code,
      label: idx.idx_name,
      value: idx.close.toLocaleString(undefined, { maximumFractionDigits: 2 }),
      change: idx.change_pct,
      unit: '',
    })),
    ...commodities.map((c) => ({
      key: c.code,
      label: c.name,
      value: c.close.toLocaleString(undefined, { maximumFractionDigits: 1 }),
      change: null,
      unit: c.unit,
    })),
  ];

  return (
    <div className="bg-slate-900 text-white text-xs">
      <div className="max-w-7xl mx-auto px-4 h-9 flex items-center gap-6 overflow-x-auto no-scrollbar">
        {items.map((item) => (
          <div key={item.key} className="flex items-center gap-2 whitespace-nowrap shrink-0">
            <span className="text-slate-400 font-medium">{item.label}</span>
            <span className="font-bold text-white">
              {item.value}{item.unit ? <span className="text-slate-400 ml-0.5 font-normal">{item.unit}</span> : ''}
            </span>
            {item.change != null && (
              <span className={`font-bold ${item.change > 0 ? 'text-red-400' : item.change < 0 ? 'text-blue-400' : 'text-slate-400'}`}>
                {item.change > 0 ? '▲' : item.change < 0 ? '▼' : '─'} {Math.abs(item.change).toFixed(2)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// FilterBadges
// ──────────────────────────────────────────────────────────────────────────
const FilterBadges = ({ filters }) => {
  if (!filters) return null;
  const badges = [];
  if (filters.rsi) {
    const { min, max } = filters.rsi;
    if (min != null && max != null) badges.push(`RSI ${min}~${max}`);
    else if (min != null) badges.push(`RSI ≥ ${min}`);
    else if (max != null) badges.push(`RSI ≤ ${max}`);
  }
  if (filters.profit_growth_years) badges.push(`영업이익 ${filters.profit_growth_years}년 성장`);
  if (filters.is_leader) badges.push('섹터 주도주');
  if (filters.sector) badges.push(`${filters.sector} 섹터`);
  if (filters.market_cap_trillion_min) badges.push(`시총 ${filters.market_cap_trillion_min}조↑`);
  if (filters.dividend_yield_min) badges.push(`배당 ${filters.dividend_yield_min}%↑`);
  if (badges.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {badges.map((b) => (
        <span key={b} className="text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-bold border border-blue-200">
          {b}
        </span>
      ))}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// StockCard
// ──────────────────────────────────────────────────────────────────────────
const StockCard = ({ stock, selected, onClick }) => (
  <div
    onClick={onClick}
    className={`p-5 rounded-2xl border-2 transition-all cursor-pointer ${
      selected
        ? 'border-blue-500 bg-blue-50 ring-4 ring-blue-100 shadow-md'
        : 'border-white bg-white hover:border-blue-200 shadow-sm hover:shadow-md'
    }`}
  >
    <div className="flex justify-between items-start mb-2">
      <div>
        <div className="font-black text-lg text-slate-800 leading-tight">{stock.name}</div>
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">
          {stock.code} · {stock.sector}
        </div>
      </div>
      <div className="text-xs font-black text-blue-600 bg-blue-100 px-2.5 py-1 rounded-xl">
        {stock.buy_score}
      </div>
    </div>

    <div className="flex gap-1.5 mb-3 flex-wrap">
      {stock.is_leader && (
        <span className="text-[10px] bg-amber-400 text-white px-2 py-0.5 rounded-full font-black">주도주</span>
      )}
      {stock.profit_growth_years >= 3 && (
        <span className="text-[10px] bg-emerald-500 text-white px-2 py-0.5 rounded-full font-black">
          {stock.profit_growth_years}년 성장
        </span>
      )}
      {stock.dividend_yield >= 4 && (
        <span className="text-[10px] bg-violet-500 text-white px-2 py-0.5 rounded-full font-black">
          배당 {stock.dividend_yield?.toFixed(1)}%
        </span>
      )}
    </div>

    <div className="flex justify-between items-end">
      <div className="text-xs text-slate-500 space-y-0.5">
        <div>RSI <span className={`font-bold ${RSI_COLOR(stock.rsi)}`}>{stock.rsi}</span></div>
        {stock.market_cap_trillion && (
          <div className="text-slate-400">시총 {stock.market_cap_trillion.toFixed(0)}조</div>
        )}
      </div>
      <div className="text-right">
        <div className="font-black text-lg text-slate-900">{fmt(stock.price)}원</div>
        <div className={`text-xs font-bold ${stock.change >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
          {stock.change >= 0 ? '▲' : '▼'} {Math.abs(stock.change).toFixed(2)}%
        </div>
      </div>
    </div>
  </div>
);

// ──────────────────────────────────────────────────────────────────────────
// StockChart
// ──────────────────────────────────────────────────────────────────────────
const StockChart = ({ stock, filters, maVisible, setMaVisible, visibleRange, setVisibleRange }) => {
  const data = useMemo(() => stock.history.slice(-visibleRange), [stock, visibleRange]);
  const width = 800;
  const height = 340;
  const pad = 52;
  const volH = 60;

  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-300 border-2 border-dashed border-slate-100 rounded-2xl">
        차트 데이터 없음
      </div>
    );
  }

  const prices = data.flatMap((d) => [d.low, d.high]).filter(Boolean);
  const minP = Math.min(...prices) * 0.985;
  const maxP = Math.max(...prices) * 1.015;
  const maxV = Math.max(...data.map((d) => d.volume || 0));

  const getX = (i) => pad + (i * (width - pad * 2)) / Math.max(1, data.length - 1);
  const getY = (p) =>
    height - pad - volH - ((p - minP) / (maxP - minP)) * (height - pad * 2 - volH);
  const getVolY = (v) => height - pad - (v / (maxV || 1)) * volH;

  const MA_COLORS = { 5: '#f59e0b', 10: '#10b981', 20: '#ef4444', 60: '#3b82f6', 120: '#8b5cf6', 240: '#64748b' };

  const renderMA = (period, color) => {
    if (!maVisible[period]) return null;
    const pts = data
      .map((_, i) => {
        const fi = stock.history.length - visibleRange + i;
        if (fi < period - 1) return null;
        const sl = stock.history.slice(fi - period + 1, fi + 1);
        const avg = sl.reduce((a, c) => a + (c.close || 0), 0) / sl.length;
        return `${getX(i)},${getY(avg)}`;
      })
      .filter(Boolean)
      .join(' ');
    if (!pts) return null;
    return <polyline key={period} points={pts} fill="none" stroke={color} strokeWidth="1.5" opacity="0.85" />;
  };

  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-inner">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex flex-wrap gap-3">
          {[5, 10, 20, 60, 120, 240].map((p) => (
            <label key={p} className="flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={maVisible[p]}
                onChange={() => setMaVisible((prev) => ({ ...prev, [p]: !prev[p] }))}
                className="w-3 h-3 rounded"
              />
              <span className="text-[11px] font-bold" style={{ color: maVisible[p] ? MA_COLORS[p] : '#94a3b8' }}>
                MA{p}
              </span>
            </label>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="font-bold">{visibleRange}일</span>
          <input
            type="range" min="10" max="130" value={visibleRange}
            onChange={(e) => setVisibleRange(+e.target.value)}
            className="w-24 h-1.5 rounded-lg accent-blue-600"
          />
        </div>
      </div>

      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible select-none">
        {/* 격자선 */}
        {[0, 1, 2, 3, 4].map((i) => {
          const val = minP + (maxP - minP) * (i / 4);
          const y = getY(val);
          return (
            <g key={i}>
              <line x1={pad} y1={y} x2={width - pad} y2={y} stroke="#f1f5f9" strokeDasharray="4 4" />
              <text x={pad - 6} y={y} textAnchor="end" fontSize="10" fill="#94a3b8" dominantBaseline="middle">
                {Math.round(val).toLocaleString()}
              </text>
            </g>
          );
        })}

        {/* 캔들 + 거래량 */}
        {data.map((d, i) => {
          const x = getX(i);
          const isUp = (d.close || 0) >= (d.open || 0);
          const color = isUp ? '#ef4444' : '#3b82f6';
          const cy = getY(d.close || 0);
          const oy = getY(d.open || 0);
          const hy = getY(d.high || d.close || 0);
          const ly = getY(d.low || d.close || 0);
          const vy = getVolY(d.volume || 0);
          return (
            <g key={i}>
              <rect x={x - 3} y={vy} width="6" height={height - pad - vy} fill={color} opacity="0.18" />
              <line x1={x} y1={hy} x2={x} y2={ly} stroke={color} strokeWidth="1" />
              <rect
                x={x - 4} y={Math.min(cy, oy)}
                width="8" height={Math.max(1, Math.abs(cy - oy))}
                fill={color}
              />
            </g>
          );
        })}

        {/* 이동평균선 */}
        {Object.entries(MA_COLORS).map(([p, c]) => renderMA(+p, c))}

        {/* RSI 뱃지 */}
        {filters?.rsi && (
          <g transform={`translate(${width - pad - 105}, ${pad})`}>
            <rect width="95" height="22" rx="4" fill="#3b82f6" opacity="0.9" />
            <text x="47" y="15" textAnchor="middle" fontSize="11" fill="white" fontWeight="bold">
              RSI(14): {stock.rsi}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────
// StockDetail
// ──────────────────────────────────────────────────────────────────────────
const StockDetail = ({ stock, filters, bookmarked, onToggleBookmark, maVisible, setMaVisible, visibleRange, setVisibleRange }) => (
  <div className="bg-white rounded-3xl border border-slate-200 shadow-xl p-8 sticky top-24 overflow-hidden">
    {/* 헤더 */}
    <div className="flex justify-between items-start mb-6">
      <div className="flex items-center gap-4">
        <div className="w-13 h-13 w-[52px] h-[52px] bg-slate-900 rounded-2xl flex items-center justify-center text-white font-black text-xl shrink-0">
          {stock.name[0]}
        </div>
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-2xl font-black text-slate-900">{stock.name}</h2>
            <button onClick={onToggleBookmark} className="focus:outline-none">
              <Bookmark className={`w-6 h-6 transition-colors ${bookmarked ? 'fill-amber-400 text-amber-400' : 'text-slate-200 hover:text-amber-300'}`} />
            </button>
          </div>
          <div className="text-xs font-bold text-slate-400 mt-0.5">
            {stock.sector} 섹터 · {stock.code}
          </div>
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Score</div>
        <div className="flex items-baseline gap-1">
          <span className="text-5xl font-black text-blue-600">{stock.buy_score}</span>
          <span className="text-lg font-bold text-slate-300">/100</span>
        </div>
      </div>
    </div>

    {/* 4-stat 요약 */}
    <div className="grid grid-cols-4 gap-3 mb-6">
      {[
        { label: '현재가', value: `${fmt(stock.price)}원`, sub: `${stock.change >= 0 ? '▲' : '▼'} ${Math.abs(stock.change).toFixed(2)}%`, subColor: stock.change >= 0 ? 'text-red-500' : 'text-blue-500' },
        { label: 'RSI(14)', value: stock.rsi, sub: stock.rsi >= 70 ? '과매수' : stock.rsi <= 30 ? '과매도' : '정상', subColor: RSI_COLOR(stock.rsi) },
        { label: '시가총액', value: stock.market_cap_trillion ? `${stock.market_cap_trillion.toFixed(1)}조` : '-', sub: '', subColor: '' },
        { label: '배당수익률', value: stock.dividend_yield ? `${stock.dividend_yield.toFixed(1)}%` : '-', sub: '', subColor: '' },
      ].map(({ label, value, sub, subColor }) => (
        <div key={label} className="bg-slate-50 rounded-xl p-3 border border-slate-100 text-center">
          <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">{label}</div>
          <div className="font-black text-slate-900 text-sm">{value}</div>
          {sub && <div className={`text-[10px] font-bold mt-0.5 ${subColor}`}>{sub}</div>}
        </div>
      ))}
    </div>

    {/* 차트 */}
    <StockChart
      stock={stock}
      filters={filters}
      maVisible={maVisible}
      setMaVisible={setMaVisible}
      visibleRange={visibleRange}
      setVisibleRange={setVisibleRange}
    />

    {/* 하단 패널 */}
    <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* 섹터 위상 */}
      <div className="p-5 rounded-2xl border-2 bg-slate-50 border-slate-100">
        <h3 className="font-black text-slate-800 flex items-center gap-2 text-sm mb-3">
          <Award className="w-4 h-4 text-amber-500 fill-amber-500" /> 섹터 내 위상
        </h3>
        {stock.is_leader ? (
          <p className="text-sm text-amber-700 font-bold leading-relaxed">
            ★ 현재 {stock.sector} 섹터 주도 대장주입니다.
          </p>
        ) : (
          <p className="text-sm text-slate-500 leading-relaxed">
            섹터 주도주:{' '}
            <span className="text-blue-600 font-bold">{stock.leader_name}</span>
          </p>
        )}
        <div className="mt-3 text-xs text-slate-400 space-y-1">
          <div>영업이익 연속 성장: <span className="font-bold text-emerald-600">{stock.profit_growth_years}년</span></div>
        </div>
      </div>

      {/* 재무 요약 */}
      <div className="bg-slate-900 text-white p-5 rounded-2xl">
        <h3 className="font-black flex items-center gap-2 text-sm mb-3">
          <BarChart3 className="w-4 h-4 text-blue-400" /> DART 재무 요약
        </h3>
        <div className="grid grid-cols-3 gap-2 mb-3">
          {[
            { label: 'Revenue', value: stock.financials?.revenue, color: 'text-white' },
            { label: 'Profit', value: stock.financials?.profit, color: 'text-orange-400' },
            { label: 'ROE', value: stock.financials?.roe, color: 'text-emerald-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-slate-800 p-2 rounded-lg text-center">
              <div className="text-[9px] text-slate-500 uppercase font-bold">{label}</div>
              <div className={`text-sm font-black ${color}`}>{value || '-'}</div>
            </div>
          ))}
        </div>
        <p className="text-xs leading-relaxed text-slate-400 italic">
          {stock.financials?.desc ? `"${stock.financials.desc}"` : '재무 데이터를 불러오는 중...'}
        </p>
      </div>
    </div>
  </div>
);

// ──────────────────────────────────────────────────────────────────────────
// Main App
// ──────────────────────────────────────────────────────────────────────────
const App = () => {
  const [activeTab, setActiveTab] = useState('search');
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [activeFilters, setActiveFilters] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [error, setError] = useState(null);

  const [stocks, setStocks] = useState(MOCK_STOCKS);
  const [dataSource, setDataSource] = useState('mock');
  const [dataTimestamp, setDataTimestamp] = useState('MOCK 데이터 · 백엔드 미연결');

  const [indices, setIndices] = useState(MOCK_INDICES);
  const [commodities, setCommodities] = useState(MOCK_COMMODITIES);

  const [maVisible, setMaVisible] = useState({ 5: true, 10: false, 20: true, 60: true, 120: false, 240: false });
  const [visibleRange, setVisibleRange] = useState(60);

  const [savedQueries, setSavedQueries] = useState([
    { id: 1, text: 'RSI 50~70 사이 섹터 주도주', date: '2026-04-18' },
    { id: 2, text: '반도체 섹터 3년 연속 성장주', date: '2026-04-17' },
  ]);
  const [bookmarkedStocks, setBookmarkedStocks] = useState([]);

  // ── 초기 데이터 로드 ────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    // 종목 로드
    (async () => {
      try {
        const data = await api.listStocks();
        if (cancelled || !data?.stocks?.length) return;
        setStocks(data.stocks);
        setDataSource('api');
        setDataTimestamp(data.as_of || `${new Date().toLocaleString('ko-KR')} · 실시간`);
      } catch { /* mock 유지 */ }
    })();

    // 지수 로드
    (async () => {
      try {
        const data = await api.listIndices();
        if (cancelled || !data?.indices?.length) return;
        setIndices(data.indices);
      } catch { /* mock 유지 */ }
    })();

    // 원자재 로드
    (async () => {
      try {
        const data = await api.listCommodities();
        if (cancelled || !data?.commodities?.length) return;
        setCommodities(data.commodities);
      } catch { /* mock 유지 */ }
    })();

    return () => { cancelled = true; };
  }, []);

  // ── 히스토리 lazy-load (API 연결 시) ────────────────────────────────────
  useEffect(() => {
    if (!selectedStock || selectedStock.history?.length > 0 || dataSource !== 'api') return;
    (async () => {
      try {
        const data = await api.stockHistory(selectedStock.code);
        if (!data?.history?.length) return;
        setStocks((prev) =>
          prev.map((s) => s.code === selectedStock.code ? { ...s, history: data.history } : s)
        );
        setSelectedStock((prev) => prev ? { ...prev, history: data.history } : prev);
      } catch { /* 무시 */ }
    })();
  }, [selectedStock?.code, dataSource]);

  // ── 로컬 폴백 파서 ───────────────────────────────────────────────────────
  const localParse = useCallback((text) => {
    const f = {};

    const rsiRange = text.match(/RSI[^\d]*(\d{1,3})\s*(?:[~\-–에서]\s*(\d{1,3}))/i);
    const rsiMin   = text.match(/RSI[^\d]*(\d{1,3})\s*이상/i);
    const rsiMax   = text.match(/RSI[^\d]*(\d{1,3})\s*이하/i);
    if (rsiRange) f.rsi = { min: +rsiRange[1], max: +rsiRange[2] };
    else {
      const rsiPart = {};
      if (rsiMin) rsiPart.min = +rsiMin[1];
      if (rsiMax) rsiPart.max = +rsiMax[1];
      if (Object.keys(rsiPart).length) f.rsi = rsiPart;
    }

    const pg = text.match(/(\d+)\s*년.*(영업이익|이익)/);
    if (pg) f.profit_growth_years = +pg[1];

    if (/주도주|대장주/.test(text)) f.is_leader = true;

    const SECTORS = ['반도체', '자동차', '인터넷', '바이오', '2차전지', '금융', '화학', '철강', '통신', '건설', '유통', '엔터', '게임'];
    const sec = SECTORS.find((s) => text.includes(s));
    if (sec) f.sector = sec;

    const cap = text.match(/시총\s*(\d+(?:\.\d+)?)\s*조\s*이상/);
    if (cap) f.market_cap_trillion_min = +cap[1];

    const div = text.match(/배당\s*(?:수익률\s*)?(\d+(?:\.\d+)?)\s*%\s*이상/);
    if (div) f.dividend_yield_min = +div[1];

    return f;
  }, []);

  const applyFilters = useCallback((list, f) =>
    list.filter((s) => {
      if (f.rsi?.min != null && s.rsi < f.rsi.min) return false;
      if (f.rsi?.max != null && s.rsi > f.rsi.max) return false;
      if (f.profit_growth_years != null && s.profit_growth_years < f.profit_growth_years) return false;
      if (f.is_leader === true && !s.is_leader) return false;
      if (f.sector && s.sector !== f.sector) return false;
      if (f.market_cap_trillion_min != null) {
        if (!s.market_cap_trillion || s.market_cap_trillion < f.market_cap_trillion_min) return false;
      }
      if (f.dividend_yield_min != null) {
        if (!s.dividend_yield || s.dividend_yield < f.dividend_yield_min) return false;
      }
      return true;
    })
  , []);

  // ── 검색 핸들러 ─────────────────────────────────────────────────────────
  const handleSearch = useCallback(async (targetQuery = query) => {
    const q = targetQuery.trim();
    if (!q) return;
    setIsSearching(true);
    setError(null);
    setActiveTab('search');

    try {
      let filters = null;
      let filtered = null;

      try {
        const r = await api.search(q);
        filters = r.filters;
        filtered = r.results;
      } catch {
        try {
          filters = await api.parseQuery(q);
        } catch {
          filters = localParse(q);
        }
      }

      if (!filtered) filtered = applyFilters(stocks, filters || {});
      filtered = [...filtered].sort((a, b) => b.buy_score - a.buy_score);

      setActiveFilters(filters);
      setResults(filtered);
      if (filtered.length > 0) setSelectedStock(filtered[0]);

      if (!savedQueries.find((s) => s.text === q)) {
        setSavedQueries((prev) => [
          { id: Date.now(), text: q, date: new Date().toISOString().split('T')[0] },
          ...prev.slice(0, 19),
        ]);
      }
    } catch (err) {
      setError('검색 중 오류가 발생했어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsSearching(false);
    }
  }, [query, stocks, localParse, applyFilters, savedQueries]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSearch(); }
  };

  const toggleBookmark = (stock) =>
    setBookmarkedStocks((prev) =>
      prev.find((s) => s.code === stock.code)
        ? prev.filter((s) => s.code !== stock.code)
        : [...prev, stock]
    );

  const deleteQuery = (id) => setSavedQueries((prev) => prev.filter((q) => q.id !== id));

  // ── 렌더링 ──────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-16">
      {/* 지수 티커바 */}
      <IndexBar indices={indices} commodities={commodities} />

      {/* 상단 네비 */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div
            className="flex items-center gap-2.5 font-black text-2xl text-blue-600 cursor-pointer tracking-tight"
            onClick={() => setActiveTab('search')}
          >
            <TrendingUp strokeWidth={3} />
            <span>STOCK<span className="text-slate-800">NLP</span></span>
          </div>
          <div className="flex gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            {[
              { key: 'search', label: '종목 검색', icon: <Search className="w-4 h-4" /> },
              { key: 'mypage', label: '마이페이지', icon: <User className="w-4 h-4" /> },
            ].map(({ key, label, icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-5 py-2 rounded-lg text-sm font-bold transition-all flex items-center gap-2 ${
                  activeTab === key ? 'bg-white shadow-md text-blue-600' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {icon} {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 mt-8">
        {activeTab === 'search' ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* 검색 박스 (full width) */}
            <div className="lg:col-span-12">
              <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-200 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-2 h-full bg-blue-600 rounded-l-3xl" />
                <div className="flex justify-between items-center mb-5 gap-3 flex-wrap">
                  <h2 className="text-xl font-black flex items-center gap-2 text-slate-800">
                    <Zap className="w-5 h-5 text-blue-600 fill-blue-600" /> 자연어 종목 검색
                  </h2>
                  <span className={`text-xs px-3 py-1 rounded-full font-semibold border ${
                    dataSource === 'api'
                      ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                      : 'text-slate-500 bg-slate-100 border-slate-200'
                  }`}>
                    {dataSource === 'api' ? '● ' : '○ '}{dataTimestamp}
                  </span>
                </div>

                {/* 퀵 검색 버튼 */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {QUICK_SEARCHES.map((qs) => (
                    <button
                      key={qs.label}
                      onClick={() => { setQuery(qs.query); handleSearch(qs.query); }}
                      className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-blue-100 hover:text-blue-700 text-slate-600 rounded-full font-bold border border-slate-200 hover:border-blue-300 transition-all"
                    >
                      {qs.label}
                    </button>
                  ))}
                </div>

                <textarea
                  className="w-full h-20 p-4 bg-slate-50 border-2 border-slate-100 rounded-2xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 outline-none transition-all resize-none text-base font-medium shadow-inner"
                  placeholder="예: RSI 55~75 사이, 시총 30조 이상, 3년 연속 영업이익 상승 주도주"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                />

                {error && (
                  <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 px-4 py-2 rounded-xl">
                    <AlertCircle className="w-4 h-4 shrink-0" /> {error}
                  </div>
                )}

                <div className="flex items-center gap-4 mt-4">
                  <button
                    onClick={() => handleSearch()}
                    disabled={isSearching || !query.trim()}
                    className="px-10 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white py-3.5 rounded-2xl font-black text-base shadow-lg active:scale-95 transition-all flex items-center gap-2.5"
                  >
                    {isSearching
                      ? <><Loader2 className="animate-spin w-5 h-5" /> 분석 중...</>
                      : <><Activity className="w-5 h-5" /> AI 종목 분석</>
                    }
                  </button>
                  {activeFilters && (
                    <button
                      onClick={() => { setResults([]); setActiveFilters(null); setQuery(''); }}
                      className="text-sm text-slate-400 hover:text-red-500 font-bold transition-colors"
                    >
                      초기화
                    </button>
                  )}
                </div>

                <FilterBadges filters={activeFilters} />
              </div>
            </div>

            {/* 결과 목록 */}
            <div className="lg:col-span-4 space-y-4">
              <h3 className="font-black text-slate-400 text-xs uppercase tracking-widest px-1">
                검색 결과 ({results.length})
              </h3>
              <div className="space-y-3">
                {results.length === 0 ? (
                  <div className="p-8 rounded-2xl border-2 border-dashed border-slate-200 text-center text-sm text-slate-400">
                    위에서 검색하면 결과가 표시돼요
                  </div>
                ) : (
                  results.map((stock) => (
                    <StockCard
                      key={stock.code}
                      stock={stock}
                      selected={selectedStock?.code === stock.code}
                      onClick={() => setSelectedStock(stock)}
                    />
                  ))
                )}
              </div>
            </div>

            {/* 상세 패널 */}
            <div className="lg:col-span-8">
              {selectedStock ? (
                <StockDetail
                  stock={selectedStock}
                  filters={activeFilters}
                  bookmarked={!!bookmarkedStocks.find((s) => s.code === selectedStock.code)}
                  onToggleBookmark={() => toggleBookmark(selectedStock)}
                  maVisible={maVisible}
                  setMaVisible={setMaVisible}
                  visibleRange={visibleRange}
                  setVisibleRange={setVisibleRange}
                />
              ) : (
                <div className="h-[500px] flex flex-col items-center justify-center border-4 border-dashed border-slate-200 rounded-3xl text-slate-200 bg-white/50">
                  <Search className="w-16 h-16 mb-4 opacity-20" />
                  <p className="font-black text-lg uppercase tracking-widest opacity-30">
                    종목을 검색하거나 선택하세요
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* 마이페이지 */
          <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
            {/* 검색 기록 */}
            <div className="space-y-4">
              <h2 className="text-xl font-black flex items-center gap-2.5 text-slate-800">
                <History className="text-blue-600" /> 최근 검색 기록
              </h2>
              {savedQueries.length === 0 ? (
                <div className="p-6 rounded-2xl border-2 border-dashed border-slate-200 text-center text-sm text-slate-400">
                  검색 기록이 없어요.
                </div>
              ) : (
                savedQueries.map((q) => (
                  <div
                    key={q.id}
                    className="bg-white p-4 rounded-2xl border-2 border-white hover:border-blue-200 shadow-sm transition-all flex justify-between items-center group"
                  >
                    <div
                      className="cursor-pointer flex-1 min-w-0"
                      onClick={() => { setQuery(q.text); handleSearch(q.text); }}
                    >
                      <p className="font-bold text-slate-700 group-hover:text-blue-600 transition-colors text-sm truncate">{q.text}</p>
                      <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">{q.date}</span>
                    </div>
                    <div className="flex items-center gap-1 ml-2 shrink-0">
                      <button
                        onClick={() => { setQuery(q.text); handleSearch(q.text); }}
                        className="text-blue-400 hover:text-blue-600 p-1.5 transition-colors"
                        title="재검색"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                      <button onClick={() => deleteQuery(q.id)} className="text-slate-200 hover:text-red-500 p-1.5 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* 관심 종목 */}
            <div className="space-y-4">
              <h2 className="text-xl font-black flex items-center gap-2.5 text-slate-800">
                <Bookmark className="text-blue-600 fill-blue-600" /> 관심 종목
              </h2>
              {bookmarkedStocks.length === 0 ? (
                <div className="p-6 rounded-2xl border-2 border-dashed border-slate-200 text-center text-sm text-slate-400">
                  상세 화면에서 북마크 아이콘을 눌러 추가하세요.
                </div>
              ) : (
                bookmarkedStocks.map((stock) => (
                  <div
                    key={stock.code}
                    className="bg-white p-4 rounded-2xl border-2 border-white hover:border-blue-200 shadow-sm transition-all flex justify-between items-center"
                  >
                    <div
                      className="cursor-pointer flex-1 min-w-0"
                      onClick={() => { setSelectedStock(stock); setActiveTab('search'); }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-black text-base">{stock.name}</span>
                        <span className="text-[10px] font-bold text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">{stock.code}</span>
                        {stock.is_leader && (
                          <span className="text-[10px] bg-amber-400 text-white px-1.5 py-0.5 rounded-full font-black">주도주</span>
                        )}
                      </div>
                      <div className="text-[10px] font-black text-blue-500 uppercase mt-0.5">Score: {stock.buy_score}</div>
                    </div>
                    <div className="flex items-center gap-4 ml-2 shrink-0">
                      <div className="text-right">
                        <div className="font-black text-slate-900">{fmt(stock.price)}원</div>
                        <div className={`text-[10px] font-black ${stock.change >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {stock.change >= 0 ? '▲' : '▼'} {Math.abs(stock.change).toFixed(2)}%
                        </div>
                      </div>
                      <button onClick={() => toggleBookmark(stock)} className="text-slate-200 hover:text-red-500 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
