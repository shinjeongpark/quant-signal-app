# -*- coding: utf-8 -*-
"""
portfolio.py - 다중 종목 포트폴리오 시뮬레이터 모듈
여러 종목에 대해 투자 비중을 조절하고, 자산 분배 및 리스크 관리 
(허용 리스크 비율, 종목당 최대 비중)를 반영한 통합 백테스트를 실행합니다.
"""

import pandas as pd
import numpy as np
from src.data_loader import get_stock_data
from src.strategies import calculate_strategy_signals

def run_portfolio_backtest(tickers, market="US", strategy_name="전략 A: 추세 모멘텀 눌림목",
                            initial_capital=10000000, risk_ratio=0.01, max_holdings=5,
                            max_weight=0.20, rebalance_period="weekly", fee_roundtrip=0.002,
                            start_date="2018-01-01", end_date=None, market_risk_on=None):
    """
    다중 종목 포트폴리오 시뮬레이션을 수행합니다.
    
    [입력 파라미터]
    - tickers: 투자 대상 종목 리스트 또는 딕셔너리
    - market: "US" 또는 "KR"
    - strategy_name: 적용할 전략 명칭
    - initial_capital: 초기 투자금
    - risk_ratio: 1회 거래당 총자산 대비 최대 허용 리스크 (예: 1% -> 0.01)
    - max_holdings: 최대 보유 가능 종목 수 (기본 5개)
    - max_weight: 개별 종목의 최대 자산 비중 (기본 20% -> 0.20)
    - rebalance_period: 리밸런싱 주기 ("daily", "weekly", "monthly")
    - fee_roundtrip: 왕복 수수료
    """
    fee_one_way = fee_roundtrip / 2.0
    
    # 1. 각 종목 데이터 로드 및 전략 신호 계산
    ticker_list = list(tickers.keys()) if isinstance(tickers, dict) else tickers
    ticker_names = tickers if isinstance(tickers, dict) else {t: t for t in tickers}
    
    stock_dfs = {}
    all_dates = set()
    
    for tk in ticker_list:
        df = get_stock_data(tk, market=market, start_date=start_date, end_date=end_date, force_refresh=False)
        if df is not None and not df.empty and len(df) >= 100:
            df_sig = calculate_strategy_signals(df, strategy_name, market_risk_on=market_risk_on, use_filter=True)
            stock_dfs[tk] = df_sig
            all_dates.update(df_sig.index)
            
    if not stock_dfs:
        return None, None, "유효한 데이터가 확보되지 않았습니다."
        
    # 날짜 정렬된 리스트로 변환
    timeline = sorted(list(all_dates))
    
    # 포트폴리오 가치 추적용 데이터
    portfolio_value = initial_capital
    cash = initial_capital
    
    # 현재 보유 중인 포지션 정보 기록
    # 구조: {ticker: {"shares": 주식수, "entry_price": 진입가, "stop_loss": 손절가}}
    holdings = {}
    
    portfolio_history = []
    trade_log = []
    
    # 2. 통합 타임라인 시뮬레이션 루프
    for step, current_date in enumerate(timeline):
        # 당일 평가 잔고 계산을 위해 보유 종목의 당일 종가를 합산
        holdings_value = 0.0
        active_tickers = list(holdings.keys())
        
        # 보유 종목 중 당일 종가가 존재하지 않으면 직전일 가격을 유지하는 백업 메커니즘
        for tk in active_tickers:
            tk_df = stock_dfs[tk]
            if current_date in tk_df.index:
                curr_row = tk_df.loc[current_date]
                curr_close = curr_row['Adj Close']
                holdings_value += holdings[tk]["shares"] * curr_close
            else:
                # 당일 거래 정지 등의 경우 진입가 혹은 기존 가격으로 합산
                holdings_value += holdings[tk]["shares"] * holdings[tk].get("last_close", holdings[tk]["entry_price"])
                
        portfolio_value = cash + holdings_value
        
        # --- A. 보유 종목 리스크 및 청산 신호 점검 ---
        to_liquidate = []
        for tk in list(holdings.keys()):
            tk_df = stock_dfs[tk]
            if current_date not in tk_df.index:
                continue
                
            curr_row = tk_df.loc[current_date]
            curr_low = curr_row['Low']
            curr_close = curr_row['Adj Close']
            
            # 종목의 직전 영업일 신호 가져오기
            prev_rows = tk_df.loc[:current_date]
            if len(prev_rows) < 2:
                continue
            prev_signal = prev_rows.iloc[-2]['Signal']
            
            # 가. 손절선 돌파 체크 (당일 최저가가 손절가 밑으로 이탈 시)
            stop_price = holdings[tk]["stop_loss"]
            if curr_low < stop_price:
                # 손절가 가격으로 매도 처리 (편도 수수료 적용)
                exit_price = stop_price
                sell_val = holdings[tk]["shares"] * exit_price * (1.0 - fee_one_way)
                cash += sell_val
                
                trade_log.append({
                    "날짜": current_date,
                    "티커": tk,
                    "종목명": ticker_names[tk],
                    "종류": "손절청산",
                    "가격": exit_price,
                    "수량": holdings[tk]["shares"],
                    "실현손익": sell_val - (holdings[tk]["shares"] * holdings[tk]["entry_price"] * (1.0 + fee_one_way))
                })
                to_liquidate.append(tk)
                
            # 나. 전략적 청산 신호(-1) 점검
            elif prev_signal == -1:
                # 다음 영업일(오늘) 시가로 청산
                exit_price = curr_row['Open']
                sell_val = holdings[tk]["shares"] * exit_price * (1.0 - fee_one_way)
                cash += sell_val
                
                trade_log.append({
                    "날짜": current_date,
                    "티커": tk,
                    "종목명": ticker_names[tk],
                    "종류": "전략청산",
                    "가격": exit_price,
                    "수량": holdings[tk]["shares"],
                    "실현손익": sell_val - (holdings[tk]["shares"] * holdings[tk]["entry_price"] * (1.0 + fee_one_way))
                })
                to_liquidate.append(tk)
                
            # 다. 부분 매도 신호(-0.5) 처리
            elif prev_signal == -0.5:
                # 보유량의 50% 분할 매도
                shares_to_sell = holdings[tk]["shares"] / 2.0
                exit_price = curr_row['Open']
                sell_val = shares_to_sell * exit_price * (1.0 - fee_one_way)
                cash += sell_val
                holdings[tk]["shares"] -= shares_to_sell
                
                trade_log.append({
                    "날짜": current_date,
                    "티커": tk,
                    "종목명": ticker_names[tk],
                    "종류": "부분매도(50%)",
                    "가격": exit_price,
                    "수량": shares_to_sell,
                    "실현손익": sell_val - (shares_to_sell * holdings[tk]["entry_price"] * (1.0 + fee_one_way))
                })
                
            else:
                # 가격 유지용 임시 기록
                holdings[tk]["last_close"] = curr_close
                
        # 청산 종목 제거
        for tk in to_liquidate:
            holdings.pop(tk, None)
            
        # --- B. 주기적 리밸런싱 또는 신규 매수 시도 ---
        # 매주 금요일(weekly) 혹은 매월 마지막일(monthly) 등 리밸런싱 날짜 판정
        is_rebalance_day = False
        if rebalance_period == "weekly" and current_date.weekday() == 4: # 금요일
            is_rebalance_day = True
        elif rebalance_period == "monthly":
            # 당일이 해당 월의 마지막 영업일인지 판정
            if step < len(timeline) - 1:
                next_date = timeline[step + 1]
                if next_date.month != current_date.month:
                    is_rebalance_day = True
            else:
                is_rebalance_day = True
        elif rebalance_period == "daily":
            is_rebalance_day = True
            
        # 신규 매수 후보 발굴 (전 영업일 Signal == 1 종목)
        buy_candidates = []
        for tk, tk_df in stock_dfs.items():
            if tk in holdings:
                continue # 이미 보유 중이면 추가 매수 안 함
            if current_date not in tk_df.index:
                continue
                
            prev_rows = tk_df.loc[:current_date]
            if len(prev_rows) < 2:
                continue
            prev_signal = prev_rows.iloc[-2]['Signal']
            
            if prev_signal == 1:
                # 매수 타겟으로 추가
                buy_candidates.append(tk)
                
        # 신규 자산 매수 진입 시뮬레이션
        if buy_candidates and len(holdings) < max_holdings:
            for tk in buy_candidates:
                if len(holdings) >= max_holdings:
                    break
                    
                tk_df = stock_dfs[tk]
                curr_row = tk_df.loc[current_date]
                entry_price = curr_row['Open'] # 오늘 시가 진입
                atr = curr_row['ATR14']
                
                # 1) 리스크 기반 포지션 사이징 계산
                # 1회 매매로 허용하는 최대 손실액 = 현재 포트폴리오 가치 * 리스크 비율(예: 1%)
                max_loss_amount = portfolio_value * risk_ratio
                
                # 1주당 손실액 = 진입가 - 손절가 (손절가는 진입가 대비 2 * ATR 아래)
                stop_loss = entry_price - (atr * 2.0)
                loss_per_share = entry_price - stop_loss
                
                if loss_per_share <= 0:
                    continue # ATR이 비정상적으로 작은 경우 스킵
                    
                # 권장 진입 주식 수
                raw_shares = max_loss_amount / loss_per_share
                
                # 2) 최대 비중 제한(max_weight, 기본 20%) 반영
                # 종목에 할당할 수 있는 최대 금액
                max_alloc_val = portfolio_value * max_weight
                max_shares = max_alloc_val / (entry_price * (1.0 + fee_one_way))
                
                # 최종 매수 수량은 두 값 중 최솟값으로 정함
                shares_to_buy = min(raw_shares, max_shares)
                
                # 실제 매수 비용
                buy_cost = shares_to_buy * entry_price * (1.0 + fee_one_way)
                
                if buy_cost > 0 and cash >= buy_cost:
                    cash -= buy_cost
                    holdings[tk] = {
                        "shares": shares_to_buy,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "last_close": curr_row['Adj Close']
                    }
                    
                    trade_log.append({
                        "날짜": current_date,
                        "티커": tk,
                        "종목명": ticker_names[tk],
                        "종류": "포트폴리오매수",
                        "가격": entry_price,
                        "수량": shares_to_buy,
                        "실현손익": 0.0
                    })
                    
        # 일별 자산 가치 기록 저장
        portfolio_history.append({
            "Date": current_date,
            "Cash": cash,
            "Holdings_Val": holdings_value,
            "Portfolio_Val": portfolio_value
        })
        
    # 3. 성과 지표 가공 및 종목별 기여도 연산
    df_port = pd.DataFrame(portfolio_history)
    df_port.set_index('Date', inplace=True)
    df_port.rename(columns={"Portfolio_Val": "Equity"}, inplace=True)
    
    df_trades = pd.DataFrame(trade_log)
    
    # 공통 성능 지표 분석 적용
    from src.backtester import analyze_performance
    metrics = analyze_performance(df_port, df_trades, initial_capital)
    
    # 종목별 누적 실현손익 기여도 분석
    contribution = {}
    if not df_trades.empty:
        for tk in ticker_list:
            tk_trades = df_trades[df_trades['티커'] == tk]
            total_profit = tk_trades['실현손익'].sum()
            contribution[ticker_names[tk]] = total_profit
            
    metrics['Contribution'] = contribution
    
    return metrics, df_port, df_trades
