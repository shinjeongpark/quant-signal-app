# -*- coding: utf-8 -*-
"""
strategies.py - 퀀트 트레이딩 전략 정의 모듈
전략 A부터 전략 G까지의 매수/매도 규칙을 정의하고, 
각 영업일별 진입/청산 신호와 타겟 가격(손절가, 목표가 등)을 계산합니다.
"""

import pandas as pd
import numpy as np

def apply_market_filter(df, market_risk_on=None, use_filter=True):
    """
    시장 필터를 적용합니다. 
    use_filter가 True이고 market_risk_on 시리즈가 주어지면, Risk-Off 기간에는 신규 매수 신호를 제한합니다.
    """
    if use_filter and market_risk_on is not None:
        # 인덱스 기준으로 market_risk_on과 매핑하여 Risk-On 여부를 반환합니다.
        # 결측치는 안전하게 True(Risk-On)로 채웁니다.
        return market_risk_on.reindex(df.index).fillna(True)
    return pd.Series(True, index=df.index)

def calculate_strategy_signals(df, strategy_name, params=None, market_risk_on=None, use_filter=True):
    """
    지정된 전략의 신호와 타겟 가격을 계산합니다.
    
    [반환 데이터프레임 추가 컬럼]
    - Signal: 1 (매수 진입), -1 (매도 청산), 0 (관망/유지)
    - Position: 1 (보유 중), 0 (미보유)
    - Stop_Loss: 손절 기준가
    - Target_1: 1차 목표가
    - Target_2: 2차 목표가
    - Trailing_Stop: ATR 기반 트레일링 스탑 가격
    """
    if df is None or df.empty:
        return None
        
    data = df.copy()
    n = len(data)
    
    # 기본 파라미터 세팅
    if params is None:
        params = {}
    
    # 파라미터 기본값 설정
    ma_short = params.get('ma_short', 20)
    ma_medium = params.get('ma_medium', 50)
    ma_long = params.get('ma_long', 200)
    rsi_lower = params.get('rsi_lower', 35)
    rsi_upper = params.get('rsi_upper', 55)
    atr_mult = params.get('atr_mult', 2.0)
    vol_mult = params.get('vol_mult', 1.3)
    k = params.get('k', 0.5) # 변동성 돌파 k값
    
    # 필요한 지표 확인 및 계산 누락 방지
    # (data_loader에서 넘어온 후 calculate_indicators가 적용되어 있어야 함)
    for col in ['MA20', 'MA50', 'MA200', 'RSI14', 'ATR14']:
        if col not in data.columns:
            # 만약 지표가 없다면 임시로 계산해서 넣음
            from src.indicators import calculate_indicators
            data = calculate_indicators(data)
            break

    # 시장 필터 구하기
    risk_on = apply_market_filter(data, market_risk_on, use_filter)
    
    # 신호 컬럼 초기화
    data['Signal'] = 0
    data['Stop_Loss'] = np.nan
    data['Target_1'] = np.nan
    data['Target_2'] = np.nan
    data['Trailing_Stop'] = np.nan
    
    # 룩어헤드 바이어스를 방지하기 위해 모든 조건 검사는 전일 종가(shift(1)) 기준을 원칙으로 합니다.
    close = data['Adj Close']
    
    if strategy_name == "전략 A: 추세 모멘텀 눌림목":
        # 매수 조건: Risk-On & Close > MA50 & MA50 > MA200 & RSI14 [40, 65] & Price near MA20 or above MA50
        # 매수 트리거: 전일 고가 돌파 또는 20일 고가 돌파
        # 매도 조건: Close < MA20 (50% 매도), Close < MA50 (전량 매도), 또는 ATR trailing stop 이탈
        
        # 원활한 시뮬레이션을 위해 루프 돌며 포지션과 손절가 상태 추적
        in_position = False
        half_sold = False
        stop_price = 0.0
        
        for i in range(1, n):
            # 전일 지표 값들
            prev_close = close.iloc[i-1]
            prev_high = data['High'].iloc[i-1]
            prev_ma20 = data['MA20'].iloc[i-1]
            prev_ma50 = data['MA50'].iloc[i-1]
            prev_ma200 = data['MA200'].iloc[i-1]
            prev_rsi = data['RSI14'].iloc[i-1]
            prev_atr = data['ATR14'].iloc[i-1]
            prev_high_20 = data['High_20'].iloc[i-1]
            
            curr_open = data['Open'].iloc[i]
            curr_high = data['High'].iloc[i]
            curr_low = data['Low'].iloc[i]
            curr_close = close.iloc[i]
            
            # 1. 매수 진입 검사 (미보유 상태)
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma50 and prev_ma50 > prev_ma200
                cond_rsi = 40 <= prev_rsi <= 65
                # MA20 근처 (2% 이내) 또는 MA50 위
                cond_near_ma = (abs(prev_close - prev_ma20) / prev_ma20 <= 0.02) or (prev_close > prev_ma50)
                
                # 트리거: 전일 고가 상향 돌파 또는 20일 고가 돌파
                trigger_break = (curr_high > prev_high) or (curr_high > prev_high_20)
                
                if cond_market and cond_trend and cond_rsi and cond_near_ma and trigger_break:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    half_sold = False
                    # 초기 손절가: 진입 시점 전일 종가 - 2 * ATR
                    stop_price = prev_close - (prev_atr * atr_mult)
                    data.loc[data.index[i], 'Stop_Loss'] = stop_price
                    data.loc[data.index[i], 'Target_1'] = prev_close + (prev_atr * atr_mult * 1.5)
                    data.loc[data.index[i], 'Target_2'] = prev_close + (prev_atr * atr_mult * 3.0)
            
            # 2. 매도 청산 검사 (보유 상태)
            elif in_position:
                # ATR 트레일링 스탑 갱신 (고가가 상승함에 따라 손절 라인을 올림)
                prev_atr = data['ATR14'].iloc[i-1]
                stop_price = max(stop_price, prev_close - (prev_atr * atr_mult))
                data.loc[data.index[i], 'Trailing_Stop'] = stop_price
                
                # 매도 트리거 체크
                # 가. 손절가 하향 이탈
                if curr_low < stop_price:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False
                # 나. 종가 < MA50 (전량 청산)
                elif curr_close < prev_ma50:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False
                # 다. 종가 < MA20 (절반 매도 - 여기서는 단순화하여 전량 청산 신호 또는 포지션 조절로 백테스터가 처리하도록 함)
                # MVP 구조 상 Signal을 -1로 주어 전량 청산하는 규칙으로 심플하게 구현하되 자연어 설명에 추가
                elif curr_close < prev_ma20:
                    if not half_sold:
                        # 50% 축소 신호 (여기서는 부분 매도를 지원하기 위해 -0.5로 구분)
                        data.loc[data.index[i], 'Signal'] = -0.5
                        half_sold = True
                    else:
                        # 이미 절반 판 상태에서 추가 이탈 시 전량 매도
                        data.loc[data.index[i], 'Signal'] = -1
                        in_position = False

    elif strategy_name == "전략 B: 20일 신고가 돌파":
        # 매수: 종가 > MA200 & 20일 신고가 돌파 & 거래량 > 거래량 20일 평균의 1.3배 & 시장 Risk-On
        # 매도: 10일 저가 이탈 또는 ATR trailing stop 이탈
        in_position = False
        stop_price = 0.0
        
        # 10일 저가 계산
        data['Low_10'] = data['Low'].rolling(window=10).min()
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_ma200 = data['MA200'].iloc[i-1]
            prev_vol = data['Volume'].iloc[i-1]
            prev_vol_ma20 = data['Volume_MA20'].iloc[i-1]
            prev_high_20 = data['High_20'].iloc[i-1]
            prev_atr = data['ATR14'].iloc[i-1]
            
            curr_high = data['High'].iloc[i]
            curr_low = data['Low'].iloc[i]
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma200
                cond_vol = prev_vol > prev_vol_ma20 * vol_mult
                # 고가 돌파 트리거
                cond_break = curr_high > prev_high_20
                
                if cond_market and cond_trend and cond_vol and cond_break:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    stop_price = prev_close - (prev_atr * atr_mult)
                    data.loc[data.index[i], 'Stop_Loss'] = stop_price
                    data.loc[data.index[i], 'Target_1'] = prev_close + (prev_atr * atr_mult * 2.0)
            
            elif in_position:
                prev_low_10 = data['Low_10'].iloc[i-1]
                prev_atr = data['ATR14'].iloc[i-1]
                stop_price = max(stop_price, prev_close - (prev_atr * atr_mult))
                data.loc[data.index[i], 'Trailing_Stop'] = stop_price
                
                # 매도 청산 조건
                if curr_low < prev_low_10 or curr_low < stop_price:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False

    elif strategy_name == "전략 C: 터틀 스타일 55일 돌파":
        # 매수: 55일 고가 돌파 & 종가 > MA200 & ATR 기준 변동성 필터 통과 (ATR/Close < 0.06 등)
        # 매도: 20일 저가 이탈 또는 2ATR 손절
        in_position = False
        stop_price = 0.0
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_ma200 = data['MA200'].iloc[i-1]
            prev_high_55 = data['High_55'].iloc[i-1]
            prev_low_20 = data['Low_20'].iloc[i-1]
            prev_atr = data['ATR14'].iloc[i-1]
            
            curr_high = data['High'].iloc[i]
            curr_low = data['Low'].iloc[i]
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma200
                cond_break = curr_high > prev_high_55
                # 변동성 필터: ATR이 가격의 6% 이내인 상대적 저변동성 구간 선호
                cond_vol = (prev_atr / prev_close) < 0.06 if prev_close > 0 else False
                
                if cond_market and cond_trend and cond_break and cond_vol:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    stop_price = prev_close - (prev_atr * 2.0) # 2ATR 손절
                    data.loc[data.index[i], 'Stop_Loss'] = stop_price
                    data.loc[data.index[i], 'Target_1'] = prev_close + (prev_atr * 4.0)
            
            elif in_position:
                # 터틀은 고정 2ATR 손절 또는 20일 저가 이탈 시 청산
                if curr_low < prev_low_20 or curr_low < stop_price:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False

    elif strategy_name == "전략 D: 듀얼 모멘텀":
        # 매수: 시장 지수보다 강함 (스캐너용 조건) & 1M,3M,6M,12M 가중 모멘텀이 양수 & 절대 모멘텀 양수
        # 매도: 모멘텀 하락 또는 종가 < MA120
        # 개별 종목 백테스트 시에는 절대 모멘텀 양수(Return_3m > 0 등) 및 종가 > MA120 필터 중심 작동
        in_position = False
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_ma120 = data['MA120'].iloc[i-1]
            prev_mom_score = data['Momentum_Score'].iloc[i-1]
            prev_atr = data['ATR14'].iloc[i-1]
            
            curr_low = data['Low'].iloc[i]
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma120
                cond_mom = prev_mom_score > 0
                
                if cond_market and cond_trend and cond_mom:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    # 초기 손절 설정
                    data.loc[data.index[i], 'Stop_Loss'] = prev_close - (prev_atr * 2.5)
            
            elif in_position:
                if curr_low < prev_ma120 or prev_mom_score < 0:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False

    elif strategy_name == "전략 E: 변동성 돌파":
        # 매수: 당일 고가가 당일 매수 기준가(전일 종가 + k * 전일 Range)를 돌파할 때 진입
        # 매도: 다음날 시가 청산(기본) 혹은 다음날 종가 청산, 혹은 MA5 이탈
        # 파라미터 k: 0.3, 0.4, 0.5, 0.6 등
        in_position = False
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_high = data['High'].iloc[i-1]
            prev_low = data['Low'].iloc[i-1]
            prev_range = prev_high - prev_low
            
            curr_open = data['Open'].iloc[i]
            curr_high = data['High'].iloc[i]
            curr_low = data['Low'].iloc[i]
            curr_close = close.iloc[i]
            
            # 당일 매수 타겟가 계산
            target_buy_price = prev_close + k * prev_range
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_break = curr_high > target_buy_price
                
                if cond_market and cond_break:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    # 손절 라인은 전일 종가 또는 당일 시가 기준 2% 내외 설정
                    data.loc[data.index[i], 'Stop_Loss'] = curr_open * 0.97
            
            elif in_position:
                # 다음날 즉시 청산 (변동성 돌파 오버나잇 전략)
                # 여기서는 당일 장중에 들어갔다가 다음날 시가 청산하는 형태이므로
                # 보유 후 1일이 지나면 바로 매도 신호 생성
                data.loc[data.index[i], 'Signal'] = -1
                in_position = False

    elif strategy_name == "전략 F: 상승장 RSI 평균회귀":
        # 매수: 시장 Risk-On & 종가 > MA200 & RSI14 < 35 & 가격이 볼린저 하단 근처 (Close <= BB_Lower * 1.02)
        # 매도: RSI14 > 55 또는 종가 > MA20 또는 2ATR 손절
        in_position = False
        stop_price = 0.0
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_ma200 = data['MA200'].iloc[i-1]
            prev_rsi = data['RSI14'].iloc[i-1]
            prev_bb_lower = data['BB_Lower'].iloc[i-1]
            prev_atr = data['ATR14'].iloc[i-1]
            
            curr_low = data['Low'].iloc[i]
            curr_close = close.iloc[i]
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma200
                cond_rsi = prev_rsi < 35
                cond_bb = prev_close <= prev_bb_lower * 1.02
                
                if cond_market and cond_trend and cond_rsi and cond_bb:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    stop_price = prev_close - (prev_atr * 2.0)
                    data.loc[data.index[i], 'Stop_Loss'] = stop_price
                    data.loc[data.index[i], 'Target_1'] = data['MA20'].iloc[i-1]
            
            elif in_position:
                # 매도 청산 조건
                prev_rsi = data['RSI14'].iloc[i-1]
                prev_ma20 = data['MA20'].iloc[i-1]
                
                if prev_rsi > 55 or curr_close > prev_ma20 or curr_low < stop_price:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False

    elif strategy_name == "전략 G: 이동평균 크로스":
        # 매수: MA20이 MA60을 상향 골든크로스 & 종가 > MA120 & 시장 Risk-On
        # 매도: MA20이 MA60을 하향 데드크로스 또는 종가 < MA60
        in_position = False
        
        for i in range(1, n):
            prev_close = close.iloc[i-1]
            prev_ma20 = data['MA20'].iloc[i-1]
            prev_ma60 = data['MA60'].iloc[i-1]
            prev_ma120 = data['MA120'].iloc[i-1]
            
            # 이전 2영업일의 20일선 및 60일선 값 (크로스 여부 판별)
            prev_ma20_2d = data['MA20'].iloc[i-2] if i >= 2 else prev_ma20
            prev_ma60_2d = data['MA60'].iloc[i-2] if i >= 2 else prev_ma60
            
            curr_low = data['Low'].iloc[i]
            curr_close = close.iloc[i]
            
            if not in_position:
                cond_market = risk_on.iloc[i-1]
                cond_trend = prev_close > prev_ma120
                # 골든크로스 조건: 전일 20일선 > 60일선 이고 전전일 20일선 <= 60일선
                cond_cross = (prev_ma20 > prev_ma60) and (prev_ma20_2d <= prev_ma60_2d)
                
                if cond_market and cond_trend and cond_cross:
                    data.loc[data.index[i], 'Signal'] = 1
                    in_position = True
                    # 초기 손절가: 최근 20일 저가
                    data.loc[data.index[i], 'Stop_Loss'] = data['Low_20'].iloc[i-1]
            
            elif in_position:
                # 데드크로스 조건: 전일 20일선 < 60일선 이고 전전일 20일선 >= 60일선
                cond_dead_cross = (prev_ma20 < prev_ma60) and (prev_ma20_2d >= prev_ma60_2d)
                cond_below_ma60 = curr_close < prev_ma60
                
                if cond_dead_cross or cond_below_ma60:
                    data.loc[data.index[i], 'Signal'] = -1
                    in_position = False
                    
    # 보유 포지션 추적 컬럼 채우기
    # Signal 컬럼의 값을 스캔하여 포지션을 1과 0으로 마킹합니다.
    pos = 0.0
    position_series = []
    for i in range(n):
        sig = data['Signal'].iloc[i]
        if sig == 1:
            pos = 1.0 # 매수 진입
        elif sig == -1:
            pos = 0.0 # 매도 청산
        elif sig == -0.5:
            pos = 0.5 # 절반 매도
        position_series.append(pos)
        
    data['Position'] = position_series
    
    return data

def get_strategy_list():
    """
    제공하는 전략 목록 명칭을 반환합니다.
    """
    return [
        "전략 A: 추세 모멘텀 눌림목",
        "전략 B: 20일 신고가 돌파",
        "전략 C: 터틀 스타일 55일 돌파",
        "전략 D: 듀얼 모멘텀",
        "전략 E: 변동성 돌파",
        "전략 F: 상승장 RSI 평균회귀",
        "전략 G: 이동평균 크로스"
    ]
