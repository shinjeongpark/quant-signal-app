# -*- coding: utf-8 -*-
"""
signal_engine.py - 신호 판정 및 자연어 해설 생성 모듈
최근 주가 데이터를 바탕으로 종목별 기술적 종합점수를 연산하고
매수/매도/관망 신호와 초보자용 가이드 설명을 생성합니다.
"""

import pandas as pd
import numpy as np

def calculate_detailed_scores(df, market_risk_on=True):
    """
    종목 데이터의 최근 값을 바탕으로 세부 영역 점수(추세, 모멘텀, 거래량, 손익비, 시장)를 계산하고
    100점 만점 기준의 종합점수를 도출합니다.
    """
    if df is None or df.empty or len(df) < 5:
        return {
            "total_score": 0, "trend_score": 0, "momentum_score": 0,
            "volume_score": 0, "rr_score": 0, "market_score": 0
        }
        
    last_row = df.iloc[-1]
    
    close = last_row.get('Adj Close', last_row.get('Close', 0))
    ma20 = last_row.get('MA20', close)
    ma50 = last_row.get('MA50', close)
    ma200 = last_row.get('MA200', close)
    rsi = last_row.get('RSI14', 50)
    atr = last_row.get('ATR14', close * 0.02)
    
    # 1. 추세 점수 (Trend Score - 25% 반영)
    # 정배열 여부 및 중요 이동평균선 상향 돌파 상태를 채점합니다.
    trend_score = 0
    if close > ma20: trend_score += 20
    if close > ma50: trend_score += 30
    if close > ma200: trend_score += 30
    if ma50 > ma200: trend_score += 20
    
    # 2. 모멘텀 점수 (Momentum Score - 25% 반영)
    # 3M, 6M, 12M 수익률과 RSI 강도를 결합하여 매수세 강도를 평가합니다.
    mom_score = 0
    ret_3m = last_row.get('Return_3m', 0)
    ret_6m = last_row.get('Return_6m', 0)
    ret_12m = last_row.get('Return_12m', 0)
    
    if ret_3m > 0: mom_score += 30
    if ret_6m > 0: mom_score += 30
    if ret_12m > 0: mom_score += 20
    if 45 <= rsi <= 65: mom_score += 20  # 매수하기 좋은 과열되지 않은 적정 매수 구간
    
    # 3. 거래량 점수 (Volume Score - 20% 반영)
    # 20일 평균 거래량 대비 당일 거래량이 실렸는지 평가합니다.
    volume_score = 10
    vol = last_row.get('Volume', 0)
    vol_ma20 = last_row.get('Volume_MA20', 1)
    if vol_ma20 > 0:
        ratio = vol / vol_ma20
        if ratio >= 1.5:
            volume_score = 100
        elif ratio >= 1.3:
            volume_score = 80
        elif ratio >= 1.0:
            volume_score = 60
        elif ratio >= 0.7:
            volume_score = 40
            
    # 4. 손익비 점수 (RiskReward Score - 15% 반영)
    # 현재가 기준, 예상 손절가(2ATR 아래) 대비 1차 목표가(2ATR 위)의 손익비를 계산합니다.
    # 기본적으로 타겟 설정이 우수할 경우 100점을 줍니다.
    rr_score = 50
    stop_loss = close - (atr * 2.0)
    target_1 = close + (atr * 2.0)
    
    risk = close - stop_loss
    reward = target_1 - close
    if risk > 0:
        ratio = reward / risk
        if ratio >= 2.0:
            rr_score = 100
        elif ratio >= 1.5:
            rr_score = 80
        elif ratio >= 1.0:
            rr_score = 60
        else:
            rr_score = 30
            
    # 5. 시장 상태 점수 (Market Score - 15% 반영)
    market_score = 100 if market_risk_on else 0
    
    # 종합점수 산정
    total_score = (
        (trend_score * 0.25) +
        (mom_score * 0.25) +
        (volume_score * 0.20) +
        (rr_score * 0.15) +
        (market_score * 0.15)
    )
    
    return {
        "total_score": round(total_score, 1),
        "trend_score": trend_score,
        "momentum_score": mom_score,
        "volume_score": volume_score,
        "rr_score": rr_score,
        "market_score": market_score
    }

def generate_natural_language_explanation(ticker, name, df, total_score, signal_type):
    """
    종목의 상태와 매매 판단 사유를 일반 투자자가 이해하기 쉬운 한글 자연어로 생성합니다.
    """
    if df is None or df.empty:
        return "데이터가 없어 설명을 제공할 수 없습니다."
        
    last_row = df.iloc[-1]
    close = last_row.get('Adj Close', last_row.get('Close', 0))
    ma20 = last_row.get('MA20', close)
    ma50 = last_row.get('MA50', close)
    ma200 = last_row.get('MA200', close)
    rsi = last_row.get('RSI14', 50)
    atr = last_row.get('ATR14', 0)
    
    # 이평선 위치 판단
    trend_desc = ""
    if close > ma50 and close > ma200:
        trend_desc = "현재 주가가 주요 장기 이평선(MA50, MA200) 위에 위치하여 안정적인 장기 우상향 추세에 있습니다."
    elif close > ma50 and close < ma200:
        trend_desc = "현재 중기 이평선(MA50)은 상회하고 있으나, 장기 저항선인 MA200 아래에 위치하여 반등 흐름에 속합니다."
    else:
        trend_desc = "현재 주가가 MA50과 MA200 아래에 머물러 있어 추세적으로 약세 흐름이 지속되는 구간입니다."
        
    # RSI 상태 판단
    rsi_desc = ""
    if rsi >= 70:
        rsi_desc = "RSI14 지표가 70 이상으로 단기 과열권에 진입했으므로 추격 매수 시 단기 조정 리스크가 있습니다."
    elif rsi <= 35:
        rsi_desc = "RSI14 지표가 35 이하로 과매도 구간에 들어와 기술적 반등 가능성이 높아 보입니다."
    else:
        rsi_desc = f"RSI14 지표는 {rsi:.1f}로 과열되지 않은 비교적 안정적인 궤도에 있습니다."
        
    # 모멘텀 세기 판단
    ret_3m = last_row.get('Return_3m', 0)
    mom_desc = ""
    if ret_3m > 0.15:
        mom_desc = "최근 3개월 수익률이 15% 이상으로 강한 시장 주도력을 나타냅니다."
    elif ret_3m < -0.10:
        mom_desc = "최근 3개월 주가가 하락세를 타며 모멘텀이 위축되어 있습니다."
    else:
        mom_desc = "단기 모멘텀은 횡보 혹은 완만한 흐름을 유지하고 있습니다."
        
    # 결론 문구
    stop_price = close - (atr * 2.0)
    conclusion = ""
    if signal_type == "BUY":
        conclusion = f"종합 점수는 {total_score}점으로 매우 긍정적이며 매수 전략 조건에 만족합니다. 권장 진입 타점은 현재가 부근이며, 초기 손절가는 ATR 기준 {stop_price:,.0f} 내외로 설정하는 것이 안전합니다."
    elif signal_type == "WATCH":
        conclusion = f"종합 점수는 {total_score}점의 관심 종목군에 위치하지만, 명확한 돌파나 추가 신호가 완성될 때까지 차트 변곡점을 관망(WATCH)하시는 것을 권장합니다."
    elif signal_type == "SELL":
        conclusion = "이평선 이탈이나 주요 트레일링 스탑 라인 훼손이 발생하여 리스크 관리 차원의 비중 축소 또는 매도(SELL) 판단이 적합합니다."
    elif signal_type == "HOLD":
        conclusion = "기존 진입 자산은 포지션을 유지(HOLD)하며 이평선 우상향 이탈 흐름을 관찰할 수 있는 구간입니다."
    else:
        conclusion = "현재 시장 상태 또는 기술적 지표 상 뚜렷한 진입 근거가 부재하므로 신규 진입을 보류(NO_ACTION)하고 대기하는 편이 좋습니다."
        
    return f"{name}({ticker})의 {trend_desc} {rsi_desc} {mom_desc} 결론적으로, {conclusion}"

def generate_signals_for_universe(tickers, market="US", strategy_name="전략 A: 추세 모멘텀 눌림목", market_risk_on=True):
    """
    유니버스의 종목 리스트를 스캔하여 종합 정보 테이블을 생성합니다.
    """
    from src.data_loader import get_stock_data
    from src.strategies import calculate_strategy_signals
    
    results = []
    
    # tickers는 딕셔너리 형태 {"AAPL": "애플"} 또는 리스트 형태를 모두 호환
    ticker_list = list(tickers.keys()) if isinstance(tickers, dict) else tickers
    ticker_names = tickers if isinstance(tickers, dict) else {t: t for t in tickers}
    
    for tk in ticker_list:
        try:
            # 6년치 데이터 로드 (지표 연산에 200일 이상 필요)
            df = get_stock_data(tk, market=market, force_refresh=False)
            if df is None or df.empty or len(df) < 200:
                continue
                
            # 신호 계산
            df_sig = calculate_strategy_signals(df, strategy_name, market_risk_on=pd.Series(market_risk_on, index=df.index))
            if df_sig is None or df_sig.empty:
                continue
                
            last_row = df_sig.iloc[-1]
            close = last_row.get('Adj Close', last_row.get('Close', 0))
            atr = last_row.get('ATR14', close * 0.02)
            
            # 종합점수 산정
            scores = calculate_detailed_scores(df_sig, market_risk_on)
            tot_score = scores['total_score']
            
            # 신호 판정
            # 최근 3일 이내에 매수 신호(Signal==1)가 감지되었고 종합점수가 우수하면 BUY
            recent_signals = df_sig['Signal'].iloc[-3:]
            has_buy_sig = 1 in recent_signals.values
            has_sell_sig = -1 in recent_signals.values
            
            if has_buy_sig and tot_score >= 75:
                sig_type = "BUY"
            elif tot_score >= 75:
                sig_type = "WATCH"
            elif has_sell_sig or last_row.get('Position', 0) == 0:
                sig_type = "SELL" if has_sell_sig else "NO_ACTION"
            else:
                sig_type = "HOLD"
                
            # 타점 계산
            trigger_price = last_row.get('High_20', close)  # 20일 고가 돌파 기준
            stop_price = close - (atr * 2.0)
            target_1 = close + (atr * 2.0)
            target_2 = close + (atr * 4.0)
            
            risk = close - stop_price
            reward = target_1 - close
            rr_ratio = reward / risk if risk > 0 else 0
            
            desc = generate_natural_language_explanation(tk, ticker_names[tk], df_sig, tot_score, sig_type)
            
            results.append({
                "시장": "미국" if market == "US" else "한국",
                "티커": tk,
                "종목명": ticker_names[tk],
                "현재가": round(close, 2) if market == "US" else int(close),
                "전략명": strategy_name,
                "신호": sig_type,
                "종합점수": tot_score,
                "추세점수": scores['trend_score'],
                "모멘텀점수": scores['momentum_score'],
                "거래량점수": scores['volume_score'],
                "변동성점수": round(last_row.get('Volatility_20', 0) * 100, 1),
                "매수 트리거 가격": round(trigger_price, 2) if market == "US" else int(trigger_price),
                "손절가": round(stop_price, 2) if market == "US" else int(stop_price),
                "1차 목표가": round(target_1, 2) if market == "US" else int(target_1),
                "2차 목표가": round(target_2, 2) if market == "US" else int(target_2),
                "손익비": round(rr_ratio, 2),
                "ATR": round(atr, 2),
                "RSI14": round(last_row.get('RSI14', 50), 1),
                "MA20": round(last_row.get('MA20', close), 2) if market == "US" else int(last_row.get('MA20', close)),
                "MA50": round(last_row.get('MA50', close), 2) if market == "US" else int(last_row.get('MA50', close)),
                "MA120": round(last_row.get('MA120', close), 2) if market == "US" else int(last_row.get('MA120', close)),
                "MA200": round(last_row.get('MA200', close), 2) if market == "US" else int(last_row.get('MA200', close)),
                "설명": desc
            })
        except Exception as e:
            print(f"[스캐너 종목 연산 실패] {tk}: {e}")
            
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        # 종합 점수 높은 순으로 기본 정렬
        df_res.sort_values(by="종합점수", ascending=False, inplace=True)
    return df_res
