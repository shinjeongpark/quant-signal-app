# -*- coding: utf-8 -*-
"""
optimizer.py - 전략 파라미터 최적화 및 평가 모듈
그리드 서치를 통해 전략별 최적의 파라미터를 탐색하고,
학습(Train)/검증(Test) 데이터를 분할하여 과최적화를 검증합니다.
"""

import pandas as pd
import numpy as np
import itertools
from src.strategies import calculate_strategy_signals, get_strategy_list
from src.backtester import run_backtest

# 최적화용 파라미터 후보군 정의
GRID_PARAMS_FULL = {
    "ma_short": [10, 20],
    "ma_medium": [50, 60],
    "ma_long": [120, 200],
    "rsi_lower": [30, 35, 40],
    "rsi_upper": [55, 60, 65, 70],
    "atr_mult": [1.5, 2.0, 2.5, 3.0],
    "vol_mult": [1.0, 1.3, 1.5, 2.0],
    "k": [0.3, 0.4, 0.5, 0.6]
}

# 계산 시간 단축을 위한 Quick Mode 파라미터 조합
GRID_PARAMS_QUICK = {
    "ma_short": [20],
    "ma_medium": [50],
    "ma_long": [200],
    "rsi_lower": [35],
    "rsi_upper": [55, 65],
    "atr_mult": [2.0, 2.5],
    "vol_mult": [1.3],
    "k": [0.5, 0.6]
}

def split_train_test(df, train_ratio=0.7):
    """
    시계열 데이터프레임을 학습(Train)과 검증(Test) 구간으로 분할합니다.
    시계열 데이터의 특성을 고려하여 섞지 않고 날짜 순으로 자릅니다.
    """
    if df is None or df.empty:
        return None, None
    
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    return train_df, test_df

def optimize_strategy(df, strategy_name, mode="quick", train_ratio=0.7, fee_roundtrip=0.002, entry_on_next_open=True, market_risk_on=None):
    """
    단일 종목과 특정 전략에 대해 그리드 서치 최적화를 수행합니다.
    Train 구간에서 최고의 CAGR을 기록한 파라미터를 찾은 뒤, Test 구간에 적용하여 결과를 비교합니다.
    """
    # 1. Train/Test 데이터 분할
    train_df, test_df = split_train_test(df, train_ratio)
    if train_df is None or test_df is None or len(train_df) < 50 or len(test_df) < 20:
        return {
            "error": "데이터가 부족하여 최적화를 진행할 수 없습니다. (최소 70 영업일 이상 필요)"
        }
    
    # 2. 모드에 따른 파라미터 조합 생성
    grid_source = GRID_PARAMS_QUICK if mode == "quick" else GRID_PARAMS_FULL
    
    # 변동성 돌파 전략(전략 E)인지에 따라 탐색할 핵심 파라미터를 선별
    is_volatility_breakout = "변동성 돌파" in strategy_name
    
    if is_volatility_breakout:
        keys = ["k"]
    else:
        # 일반 기술적 지표 최적화 키
        keys = ["ma_short", "ma_medium", "ma_long", "rsi_lower", "rsi_upper", "atr_mult", "vol_mult"]
        
    values = [grid_source[k] for k in keys]
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    best_cagr = -999.0
    best_params = None
    best_train_metrics = None
    
    all_results = []
    
    # 3. Train 데이터셋 그리드 서치 루프
    # 모든 조합을 테스트하여 최고의 성과를 기록한 파라미터를 추출
    for params in combinations:
        # 전략 신호 계산
        df_sig = calculate_strategy_signals(train_df, strategy_name, params, market_risk_on, use_filter=True)
        # 백테스트 실행
        metrics, _, _ = run_backtest(df_sig, fee_roundtrip=fee_roundtrip, entry_on_next_open=entry_on_next_open)
        
        cagr = metrics.get('CAGR', -1.0)
        all_results.append({
            "params": params,
            "metrics": metrics
        })
        
        # CAGR 기준 최고 성과 파라미터 갱신
        if cagr > best_cagr:
            best_cagr = cagr
            best_params = params
            best_train_metrics = metrics
            
    if best_params is None:
        return {"error": "적절한 최적화 결과를 얻지 못했습니다."}
        
    # 4. 검증(Test) 구간에 최적 파라미터 대입
    test_df_sig = calculate_strategy_signals(test_df, strategy_name, best_params, market_risk_on, use_filter=True)
    best_test_metrics, test_equity, test_trades = run_backtest(test_df_sig, fee_roundtrip=fee_roundtrip, entry_on_next_open=entry_on_next_open)
    
    # 5. 과최적화 여부 검증
    # 학습 구간의 CAGR과 검증 구간의 CAGR 차이가 20%p 이상 나거나, 검증 구간이 마이너스 성과를 기록하면 경고
    overfitting_warning = False
    cagr_diff = best_train_metrics.get('CAGR', 0) - best_test_metrics.get('CAGR', 0)
    if cagr_diff > 0.20 or (best_train_metrics.get('CAGR', 0) > 0 and best_test_metrics.get('CAGR', 0) < -0.05):
        overfitting_warning = True
        
    return {
        "strategy_name": strategy_name,
        "best_params": best_params,
        "train_metrics": best_train_metrics,
        "test_metrics": best_test_metrics,
        "overfitting_warning": overfitting_warning,
        "cagr_diff": cagr_diff,
        "all_combinations_count": len(combinations)
    }

def find_best_overall_strategy(df, mode="quick", fee_roundtrip=0.002, market_risk_on=None):
    """
    전체 전략 목록 중 1) 최고 수익률 우승 전략과 2) 실전형 최고 전략을 선정합니다.
    """
    strategies = get_strategy_list()
    results = []
    
    for strat in strategies:
        try:
            opt_res = optimize_strategy(df, strat, mode=mode, train_ratio=0.7, fee_roundtrip=fee_roundtrip, market_risk_on=market_risk_on)
            if "error" not in opt_res:
                results.append(opt_res)
        except Exception as e:
            print(f"[최적화 진행 에러] {strat}: {e}")
            
    if not results:
        return None, None
        
    # --- 1) 최고 수익률 전략 선정 ---
    # 조건: CAGR이 가장 높을 것, 거래 횟수 20회 이상(Train 기준), 백테스트 총 기간 2년 이상일 때 신뢰
    best_return_strat = None
    max_cagr = -999.0
    
    for res in results:
        train_m = res['train_metrics']
        trades = train_m.get('Number of Trades', 0)
        cagr = train_m.get('CAGR', -1.0)
        
        # 전체 백테스트 기간 유효성
        if trades >= 20:
            if cagr > max_cagr:
                max_cagr = cagr
                best_return_strat = res
                
    # --- 2) 실전형 최고 전략 선정 ---
    # Score = CAGR * 0.45 + Sharpe * 0.20 + Calmar * 0.20 + ProfitFactor * 0.10 - abs(MDD) * 0.05
    # 조건: 거래 횟수 20회 이상, MDD >= -35%, Profit Factor >= 1.2, Sharpe >= 0.5
    best_practical_strat = None
    best_score = -999.0
    
    for res in results:
        train_m = res['train_metrics']
        trades = train_m.get('Number of Trades', 0)
        cagr = train_m.get('CAGR', 0.0)
        sharpe = train_m.get('Sharpe Ratio', 0.0)
        calmar = train_m.get('Calmar Ratio', 0.0)
        pf = train_m.get('Profit Factor', 1.0)
        mdd = train_m.get('MDD', 0.0)
        
        # 조건 통과 여부 검사
        cond_trades = trades >= 20
        cond_mdd = mdd >= -0.35
        cond_pf = pf >= 1.2
        cond_sharpe = sharpe >= 0.5
        
        score = (cagr * 0.45) + (sharpe * 0.20) + (calmar * 0.20) + (pf * 0.10) - (abs(mdd) * 0.05)
        
        if cond_trades and cond_mdd and cond_pf and cond_sharpe:
            if score > best_score:
                best_score = score
                best_practical_strat = {
                    "strategy_data": res,
                    "score": score,
                    "is_suitable": True
                }
                
    # 만약 조건을 완전히 충족하는 전략이 없는 경우,
    # 조건 제약을 완화하여 Score가 가장 높은 전략을 추출하고 "실전 투자 부적합" 경고 태그를 부착하여 반환합니다.
    if best_practical_strat is None and results:
        temp_best_res = None
        temp_max_score = -999.0
        for res in results:
            train_m = res['train_metrics']
            cagr = train_m.get('CAGR', 0.0)
            sharpe = train_m.get('Sharpe Ratio', 0.0)
            calmar = train_m.get('Calmar Ratio', 0.0)
            pf = train_m.get('Profit Factor', 1.0)
            mdd = train_m.get('MDD', 0.0)
            
            score = (cagr * 0.45) + (sharpe * 0.20) + (calmar * 0.20) + (pf * 0.10) - (abs(mdd) * 0.05)
            if score > temp_max_score:
                temp_max_score = score
                temp_best_res = res
                
        if temp_best_res:
            best_practical_strat = {
                "strategy_data": temp_best_res,
                "score": temp_max_score,
                "is_suitable": False # 실전 부적합 경고 표시 타겟
            }
            
    return best_return_strat, best_practical_strat
