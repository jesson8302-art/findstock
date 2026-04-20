"""기술적 지표 & 매수 점수 계산 유틸.

모든 함수는 pandas Series / DataFrame을 기대한다.
- RSI(14) : Wilder 방식
- MA      : 단순이평 (5, 20, 60, 120)
- buy_score : 섹터 주도주 / RSI 모멘텀 / 영업이익 연속 성장 / 최근 추세를 0~100 점으로 합산
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder smoothing
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def moving_averages(close: pd.Series, windows=(5, 20, 60, 120)) -> dict[int, pd.Series]:
    return {w: close.rolling(w, min_periods=1).mean() for w in windows}


def profit_growth_years(annual_profits: list[float]) -> int:
    """연간 영업이익 리스트(최근순이 아닌 과거→현재 순)를 받아 연속 증가 햇수 반환."""
    if not annual_profits or len(annual_profits) < 2:
        return 0
    streak = 0
    for prev, curr in zip(annual_profits, annual_profits[1:]):
        if curr > prev:
            streak += 1
        else:
            streak = 0
    return streak


def buy_score(
    rsi_value: float,
    rsi_prev: float,
    growth_years: int,
    is_leader: bool,
    price_vs_ma60: float,
) -> int:
    """0~100 스코어.

    - RSI 50~70 구간 모멘텀 가산
    - RSI 상승 전환 가산
    - 영업이익 연속 성장 햇수당 +8 (최대 +24)
    - 섹터 주도주 +15
    - 60일선 대비 주가 위치(+/-10%) 조정
    """
    score = 40.0

    if 50 <= rsi_value <= 70:
        score += 18
    elif 40 <= rsi_value < 50 or 70 < rsi_value <= 75:
        score += 10
    elif rsi_value < 30 or rsi_value > 80:
        score -= 10

    if rsi_value > rsi_prev:
        score += 8

    score += min(growth_years, 3) * 8

    if is_leader:
        score += 15

    # 60일선 대비 ±10% 범위만 인정
    pct = max(-0.1, min(0.1, price_vs_ma60))
    score += pct * 50  # ±5점 범위

    return int(max(0, min(100, round(score))))
