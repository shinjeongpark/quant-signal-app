# -*- coding: utf-8 -*-
"""
backtester.py - 단일 종목 백테스트 실행 및 성과 분석 모듈
전략 신호를 기반으로 과거 데이터를 통한 가상 매매를 시뮬레이션하고,
CAGR, MDD, 샤프 지수 등 퀀트 성과 지표를 계산합니다.
"""

import pandas as pd
import numpy as np

def run_backtest(df_with_signals, initial_capital=10000000, fee_roundtrip=0.002, entry_on_next_open=True):
    """
    단일 종목 전략 백테스트를 수행합니다.
    
    [입력 파라미터]
    - df_with_signals: 가격 데이터 및 'Signal' 컬럼이 포함된 DataFrame
    - initial_capital: 초기 자본금 (원화 또는 달러)
    - fee_roundtrip: 왕복 거래비용 (수수료, 세금, 슬리피지 합산 비율, 예: 미국 0.2% -> 0.002, 한국 0.35% -> 0.0035)
    - entry_on_next_open: True면 다음날 시가(Open) 진입, False면 다음날 종가(Close) 진입
    
    [반환 객체]
    - results: 성과 지표 딕셔너리
    - equity_curve: 일별 누적 자산 가치 변화 DataFrame
    - trade_log: 체결 내역 DataFrame
    """
    df = df_with_signals.copy()
    n = len(df)
    
    # 편도 거래비용 계산 (진입 시 반, 청산 시 반 적용)
    fee_one_way = fee_roundtrip / 2.0
    
    # 일별 자산 추적용 리스트
    dates = df.index
    cash = initial_capital
    shares = 0.0
    equity = initial_capital
    
    equity_curve = []
    trade_log = []
    
    # 포지션 추적 상태 변수
    in_position = False
    entry_price = 0.0
    entry_date = None
    
    # 백테스트 메인 시뮬레이션 루프
    # Look-ahead bias(미래 참조 편향)를 없애기 위해 당일의 신호('Signal')를 바탕으로 
    # 실제 주문 실행은 다음 영업일(i)에 진행합니다.
    for i in range(n):
        date = dates[i]
        curr_open = df['Open'].iloc[i]
        curr_close = df['Adj Close'].iloc[i]
        
        # 이전 영업일이 존재하는 경우에만 전일 신호를 체크
        if i > 0:
            prev_signal = df['Signal'].iloc[i-1]
            prev_close = df['Adj Close'].iloc[i-1]
            
            # 진입/청산 가격 결정 (시가 진입 vs 종가 진입)
            execution_price = curr_open if entry_on_next_open else curr_close
            
            # 가. 매수 진입 실행 (전일 매수 신호가 뜨고 포지션이 없는 경우)
            if prev_signal == 1 and not in_position:
                # 거래 비용 반영하여 살 수 있는 주식 수 계산
                # 실제 매수가 = 매수 체결 가격 * (1 + 수수료율)
                buy_price = execution_price * (1.0 + fee_one_way)
                shares = cash / buy_price
                cash = 0.0 # 전액 매수 (Long Only, 현금 소진)
                in_position = True
                entry_price = execution_price
                entry_date = date
                
                trade_log.append({
                    "종류": "BUY",
                    "날짜": date,
                    "가격": execution_price,
                    "실제적용가격": buy_price,
                    "수량": shares,
                    "거래금액": shares * execution_price,
                    "잔고": cash
                })
                
            # 나. 매도 청산 실행 (전일 청산 신호가 뜨고 포지션이 있는 경우)
            elif prev_signal == -1 and in_position:
                # 실제 매도가 = 매도 체결 가격 * (1 - 수수료율)
                sell_price = execution_price * (1.0 - fee_one_way)
                cash = shares * sell_price
                
                # 투자 수익률 계산
                profit_pct = (execution_price / entry_price) - 1.0
                realized_profit = cash - (shares * entry_price * (1.0 + fee_one_way))
                
                trade_log.append({
                    "종류": "SELL",
                    "날짜": date,
                    "가격": execution_price,
                    "실제적용가격": sell_price,
                    "수량": shares,
                    "거래금액": shares * execution_price,
                    "잔고": cash,
                    "수익률": profit_pct,
                    "실현손익": realized_profit
                })
                
                shares = 0.0
                in_position = False
                entry_price = 0.0
                entry_date = None
                
            # 다. 부분 매도 실행 (50% 매도 신호 처리)
            elif prev_signal == -0.5 and in_position and shares > 0:
                # 보유 주식의 절반만 매도 청산
                shares_to_sell = shares / 2.0
                sell_price = execution_price * (1.0 - fee_one_way)
                recovered_cash = shares_to_sell * sell_price
                cash += recovered_cash
                shares -= shares_to_sell
                
                profit_pct = (execution_price / entry_price) - 1.0
                
                trade_log.append({
                    "종류": "HALF_SELL",
                    "날짜": date,
                    "가격": execution_price,
                    "실제적용가격": sell_price,
                    "수량": shares_to_sell,
                    "거래금액": shares_to_sell * execution_price,
                    "잔고": cash,
                    "수익률": profit_pct,
                    "실현손익": recovered_cash - (shares_to_sell * entry_price * (1.0 + fee_one_way))
                })
        
        # 당일 자산 평가금액(Equity) 계산
        # 당일 종가를 기준으로 보유 주식의 평가 금액과 현금의 합입니다.
        current_val = shares * curr_close + cash
        equity_curve.append({
            "Date": date,
            "Cash": cash,
            "Holdings": shares * curr_close,
            "Equity": current_val
        })
        
    # 데이터프레임으로 변환
    df_equity = pd.DataFrame(equity_curve)
    df_equity.set_index('Date', inplace=True)
    
    df_trades = pd.DataFrame(trade_log)
    
    # 성과 지표 분석 실행
    metrics = analyze_performance(df_equity, df_trades, initial_capital)
    
    return metrics, df_equity, df_trades

def analyze_performance(df_equity, df_trades, initial_capital):
    """
    백테스트 자산 곡선 및 매매 대장을 바탕으로 다양한 퀀트 성과 분석 지표를 계산합니다.
    """
    metrics = {}
    
    if df_equity.empty:
        return metrics
        
    final_equity = df_equity['Equity'].iloc[-1]
    
    # 1. Total Return (누적 수익률)
    total_return = (final_equity / initial_capital) - 1.0
    metrics['Total Return'] = total_return
    
    # 백테스트 기간 계산 (연 단위)
    start_date = df_equity.index[0]
    end_date = df_equity.index[-1]
    days = (end_date - start_date).days
    years = days / 365.25
    metrics['Years'] = years
    
    # 2. CAGR (연평균 복리 성장률)
    if years > 0 and final_equity > 0:
        cagr = (final_equity / initial_capital) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0
    metrics['CAGR'] = cagr
    
    # 일별 수익률 계산
    df_equity['Daily_Return'] = df_equity['Equity'].pct_change().fillna(0)
    
    # 3. MDD (최대 낙폭)
    roll_max = df_equity['Equity'].cummax()
    drawdown = (df_equity['Equity'] - roll_max) / roll_max
    df_equity['Drawdown'] = drawdown
    mdd = drawdown.min()
    metrics['MDD'] = mdd
    
    # 4. Sharpe Ratio (샤프 지수)
    # 일일 수익률 표준편차를 구하고, 연간 기준(252일)으로 환산합니다. (무위험수익률은 0으로 가정)
    daily_std = df_equity['Daily_Return'].std()
    if daily_std > 0:
        # 연간 평균 일일 수익률 / 연간 일일 수익률 표준편차
        sharpe = (df_equity['Daily_Return'].mean() / daily_std) * np.sqrt(252)
    else:
        sharpe = 0.0
    metrics['Sharpe Ratio'] = sharpe
    
    # 5. Sortino Ratio (소르티노 지수)
    # 하방 변동성(음의 수익률의 표준편차)만 사용하여 샤프 지수의 단점을 보완합니다.
    downside_returns = df_equity['Daily_Return'][df_equity['Daily_Return'] < 0]
    downside_std = downside_returns.std()
    if downside_std > 0:
        sortino = (df_equity['Daily_Return'].mean() / downside_std) * np.sqrt(252)
    else:
        sortino = 0.0
    metrics['Sortino Ratio'] = sortino
    
    # 6. Calmar Ratio (칼마 지수)
    # CAGR을 MDD(절댓값)로 나눈 비율로, 리스크 대비 수익 효율성을 측정합니다.
    if abs(mdd) > 0:
        calmar = cagr / abs(mdd)
    else:
        calmar = 0.0
    metrics['Calmar Ratio'] = calmar
    
    # 7. 매매 지표 산출 (거래 내역이 존재할 때)
    num_trades = len(df_trades[df_trades['종류'].isin(['SELL', 'HALF_SELL'])])
    metrics['Number of Trades'] = num_trades
    
    if num_trades > 0:
        # 매도 거래만 필터링하여 각 거래의 수익률 분석
        sell_trades = df_trades[df_trades['종류'].isin(['SELL', 'HALF_SELL'])]
        returns = sell_trades['수익률'].dropna()
        profits = sell_trades['실현손익'].dropna()
        
        # 승률 (수익 거래 수 / 전체 매도 거래 수)
        win_trades = returns[returns > 0]
        win_rate = len(win_trades) / len(returns) if len(returns) > 0 else 0.0
        metrics['Win Rate'] = win_rate
        
        # Profit Factor (총 이익금 / 총 손실금)
        total_profit = profits[profits > 0].sum()
        total_loss = abs(profits[profits < 0].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)
        metrics['Profit Factor'] = profit_factor
        
        # 평균 이익 및 평균 손실 수익률
        avg_win = returns[returns > 0].mean() if len(returns[returns > 0]) > 0 else 0.0
        avg_loss = returns[returns < 0].mean() if len(returns[returns < 0]) > 0 else 0.0
        metrics['Average Win'] = avg_win
        metrics['Average Loss'] = avg_loss
        
        # Payoff Ratio (손익비 = 평균 이익 수익률 / 평균 손실 수익률 절댓값)
        payoff_ratio = avg_win / abs(avg_loss) if abs(avg_loss) > 0 else avg_win
        metrics['Payoff Ratio'] = payoff_ratio
    else:
        metrics['Win Rate'] = 0.0
        metrics['Profit Factor'] = 0.0
        metrics['Average Win'] = 0.0
        metrics['Average Loss'] = 0.0
        metrics['Payoff Ratio'] = 0.0
        
    # 8. Exposure (시장 노출도)
    # 전체 기간 중 주식을 보유(Holdings > 0)한 날의 비율
    exposure_days = len(df_equity[df_equity['Holdings'] > 0])
    metrics['Exposure'] = exposure_days / len(df_equity) if len(df_equity) > 0 else 0.0
    
    # 9. Turnover (자산 회전율)
    # 총 매수 거래 대금의 합 / 초기 자본금
    buy_trades = df_trades[df_trades['종류'] == 'BUY']
    total_buy_val = buy_trades['거래금액'].sum()
    metrics['Turnover'] = total_buy_val / initial_capital
    
    # 10. 월별 수익률 및 연도별 수익률 통계
    df_equity['Year'] = df_equity.index.year
    df_equity['Month'] = df_equity.index.month
    
    # 월말 자산 가치 추출
    monthly_equity = df_equity['Equity'].resample('ME').last()
    monthly_returns = monthly_equity.pct_change().fillna(0)
    
    metrics['Best Month'] = monthly_returns.max()
    metrics['Worst Month'] = monthly_returns.min()
    
    # 월별 수익률 Pivot Table 작성 (행: 연도, 열: 월)
    df_m_returns = pd.DataFrame({
        'Year': monthly_equity.index.year,
        'Month': monthly_equity.index.month,
        'Return': monthly_returns
    })
    
    # 피벗 테이블 생성
    monthly_heatmap = df_m_returns.pivot_table(index='Year', columns='Month', values='Return', aggfunc='mean').fillna(0)
    metrics['Monthly Heatmap'] = monthly_heatmap
    
    # 연도별 수익률 (연도 첫날 대비 연도 마지막날 자산 가치 변화)
    yearly_equity = df_equity['Equity'].resample('YE').last()
    # 첫 자산 추가를 위한 변환
    yearly_returns = yearly_equity.pct_change()
    # 첫 해의 수익률 처리
    first_year = yearly_equity.index[0].year
    first_year_start = df_equity['Equity'].iloc[0]
    first_year_end = yearly_equity.iloc[0]
    yearly_returns.iloc[0] = (first_year_end / first_year_start) - 1.0
    
    df_y_returns = pd.DataFrame({
        'Return': yearly_returns
    }, index=yearly_equity.index.year)
    metrics['Yearly Returns'] = df_y_returns
    
    return metrics
