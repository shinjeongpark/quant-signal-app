# -*- coding: utf-8 -*-
"""
indicators.py - 기술적 지표 계산 모듈
주어진 일봉 데이터프레임(OHLCV)을 바탕으로 이동평균, 변동성, 모멘텀 등
다양한 기술적 투자 지표를 계산하여 반환하는 기능을 제공합니다.
"""

import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    OHLCV 데이터프레임에 다양한 기술적 지표 컬럼을 추가합니다.
    df: Open, High, Low, Close, Adj Close, Volume 컬럼을 포함하는 pandas.DataFrame
    """
    if df is None or df.empty:
        return None
    
    # 원본 데이터 손상을 방지하기 위해 복사본을 생성합니다.
    data = df.copy()
    
    # 수정종가(Adj Close)를 계산의 기준 가격으로 설정합니다.
    # 만약 수정종가가 존재하지 않는다면 일반 종가(Close)를 기본 가격으로 설정합니다.
    price_col = 'Adj Close' if 'Adj Close' in data.columns else 'Close'
    close = data[price_col]
    high = data['High']
    low = data['Low']
    volume = data['Volume']
    
    # 1. 이동평균선 (Simple Moving Average, SMA) 계산
    # 주가의 흐름을 부드럽게 만들어 추세를 파악하도록 돕습니다.
    data['MA5'] = close.rolling(window=5).mean()
    data['MA10'] = close.rolling(window=10).mean()
    data['MA20'] = close.rolling(window=20).mean()
    data['MA50'] = close.rolling(window=50).mean()
    data['MA60'] = close.rolling(window=60).mean()
    data['MA120'] = close.rolling(window=120).mean()
    data['MA200'] = close.rolling(window=200).mean()
    
    # 2. 지수이동평균선 (Exponential Moving Average, EMA) 계산
    # 최근 가격에 더 많은 가중치를 두어 추세 변화에 민감하게 반응합니다.
    data['EMA20'] = close.ewm(span=20, adjust=False).mean()
    data['EMA50'] = close.ewm(span=50, adjust=False).mean()
    
    # 3. RSI (Relative Strength Index, 상대강도지수) 계산
    # 주가의 상승압력과 하락압력 간의 상대적인 강도를 백분율로 나타냅니다.
    # 14일 기준을 사용하며, 30 이하는 과매수 해소(과매도), 70 이상은 과매열로 해석합니다.
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    # 0 분모 방지를 위해 아주 작은 값을 더해줍니다.
    rs = gain / (loss + 1e-10)
    data['RSI14'] = 100 - (100 / (1 + rs))
    
    # 4. ATR (Average True Range, 실제 평균 변동폭) 계산
    # 14일 동안의 주가 변동폭을 측정하여 변동성을 나타내며, 손절가 설정에 유용합니다.
    high_low = high - low
    high_close = (high - close.shift(1)).abs()
    low_close = (low - close.shift(1)).abs()
    
    # True Range(진짜 변동폭)는 세 값 중 가장 큰 값입니다.
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    data['ATR14'] = true_range.rolling(window=14).mean()
    
    # 5. 볼린저 밴드 (Bollinger Band) 계산
    # 20일 이동평균선을 기준으로 주가의 표준편차의 2배만큼 위아래에 밴드를 만듭니다.
    # 주가의 약 95%는 이 밴드 내에 위치한다는 통계적 근거를 바탕으로 합니다.
    std = close.rolling(window=20).std()
    data['BB_Middle'] = data['MA20']
    data['BB_Upper'] = data['MA20'] + (std * 2)
    data['BB_Lower'] = data['MA20'] - (std * 2)
    
    # 6. 가격 돌파 기준선 (Donchian Channel 및 신고가/신저가)
    # 터틀 트레이딩 등 돌파 매매 전략에서 사용되는 채널입니다.
    data['High_20'] = high.rolling(window=20).max() # 20일 고가
    data['High_55'] = high.rolling(window=55).max() # 55일 고가
    # 52주는 대략 252 거래일입니다.
    data['High_52w'] = high.rolling(window=252).max() # 52주 고가
    
    data['Low_20'] = low.rolling(window=20).min()   # 20일 저가
    data['Low_55'] = low.rolling(window=55).min()   # 55일 저가
    
    # 7. 거래량 지표 계산
    data['Volume_MA20'] = volume.rolling(window=20).mean() # 거래량 20일 평균
    data['Value'] = close * volume                         # 거래대금
    
    # 8. 기간별 수익률 계산 (모멘텀 측정용)
    # 현재 가격이 과거 가격 대비 얼마나 상승했는지 측정합니다.
    # 1개월(21일), 3개월(63일), 6개월(126일), 12개월(252일) 영업일 기준입니다.
    data['Return_1m'] = close.pct_change(periods=21)
    data['Return_3m'] = close.pct_change(periods=63)
    data['Return_6m'] = close.pct_change(periods=126)
    data['Return_12m'] = close.pct_change(periods=252)
    
    # 9. 20일 역사적 변동성 (Historical Volatility) 계산
    # 20일 동안의 일일 로그 수익률 표준편차를 연간 변동성(252 영업일 기준)으로 환산합니다.
    log_returns = np.log(close / close.shift(1))
    data['Volatility_20'] = log_returns.rolling(window=20).std() * np.sqrt(252)
    
    # 10. MDD (Maximum Drawdown, 최대 낙폭) 계산
    # 특정 기간 내 최고점 대비 주가가 얼마나 하락했는지 나타내는 가장 보수적인 리스크 지표입니다.
    # 여기서는 각 시점까지의 역사적 고점 대비 하락률을 구합니다.
    roll_max = close.cummax()
    drawdown = (close - roll_max) / roll_max
    data['Drawdown'] = drawdown
    # 전체 기간 중 최대 낙폭(MDD)은 drawdown.min()이 됩니다.
    data['MDD'] = drawdown.cummin()
    
    # 11. 가중 모멘텀 점수 (Weighted Momentum Score)
    # 듀얼 모멘텀과 스캐너 등에 사용될 통합 모멘텀 점수입니다.
    # 최근 모멘텀에 가중치를 더 둔 계산 방식 (예: 12 * 1m + 4 * 3m + 2 * 6m + 1 * 12m)
    # 값이 클수록 강한 추세를 보여줍니다.
    # 결측치(NaN)가 발생할 수 있으므로 fillna(0) 처리합니다.
    data['Momentum_Score'] = (
        (data['Return_1m'].fillna(0) * 12) +
        (data['Return_3m'].fillna(0) * 4) +
        (data['Return_6m'].fillna(0) * 2) +
        (data['Return_12m'].fillna(0) * 1)
    )
    
    return data
