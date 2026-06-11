# -*- coding: utf-8 -*-
"""
3_전략최적화.py - 복수 전략 일괄 백테스트 및 파라미터 최적화
Train/Test 데이터 분할 검증을 수행하고, 최고 CAGR 전략 및 
실전 투자용 위험조정 우수 전략(Score 기반)을 자동으로 도출하여 시각화합니다.
"""

import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import get_stock_data, get_market_status
from src.optimizer import optimize_strategy, find_best_overall_strategy

st.set_page_config(page_title="전략 최적화 및 검증", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .winner-card { background: rgba(52, 199, 89, 0.1); border-radius: 8px; padding: 20px; border: 2px solid #34C759; margin-bottom: 20px; }
    .winner-title { font-size: 1.3rem; font-weight: bold; color: #1E3B2F; margin-bottom: 10px; }
    .warn-card { background: rgba(255, 59, 48, 0.1); border-radius: 8px; padding: 20px; border: 2px solid #FF3B30; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>🛠️ 전략 파라미터 최적화 및 과최적화 검증</div>", unsafe_allow_html=True)
st.write("학습(Train 70%)과 검증(Test 30%) 구간을 분리하여 각 전략의 최적 파라미터를 그리드 서치하고 실전 투입 적합성을 평가합니다.")

# 1. 사이드바 제어 패널
st.sidebar.header("⚙️ 최적화 옵션 설정")
market = st.sidebar.radio("시장 선택", ["미국 시장 (US)", "한국 시장 (KR)"])
market_code = "US" if "미국" in market else "KR"

if market_code == "US":
    ticker = st.sidebar.text_input("티커 입력", "AAPL").upper().strip()
else:
    ticker = st.sidebar.text_input("종목코드 입력", "005930").strip()

today = datetime.date.today()
default_start = today - datetime.timedelta(days=365*6) # 데이터 분할을 위해 6년 추천
start_date = st.sidebar.date_input("시작 날짜", default_start)
end_date = st.sidebar.date_input("종료 날짜", today)

optimize_mode = st.sidebar.radio(
    "탐색 강도 (Mode)",
    ["Quick Mode (빠른 탐색 - 기본 조합)", "Full Mode (전체 그리드 서치 - 계산시간 소요)"],
    index=0
)
opt_mode_str = "quick" if "Quick" in optimize_mode else "full"

run_opt_btn = st.sidebar.button("🔍 전략 최적화 탐색 시작")

# 2. 실행 영역
if run_opt_btn:
    if not ticker:
        st.error("종목코드(티커)를 입력해 주세요.")
    elif start_date >= end_date:
        st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
    else:
        with st.spinner(f"{ticker} 종목의 모든 기술적 전략 파라미터를 탐색하고 있습니다. 잠시만 기다려 주세요..."):
            # 1) 주가 데이터 및 시장 필터 준비
            fetch_start = (start_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
            df_raw = get_stock_data(ticker, market=market_code, start_date=fetch_start, end_date=end_date.strftime('%Y-%m-%d'))
            
            if df_raw is None or df_raw.empty or len(df_raw) < 250:
                st.error("데이터 양이 부족합니다. 최적화를 위해서는 최소 1년(250 영업일) 이상의 기간이 필수적입니다.")
            else:
                # 시장 데이터 로딩 및 인덱스 정밀 계산
                m_status = get_market_status()
                spy_start = fetch_start
                if market_code == "US":
                    idx_df = get_stock_data("SPY", "US", spy_start, end_date.strftime('%Y-%m-%d'))
                    idx_df['MA200'] = idx_df['Adj Close'].rolling(window=200).mean()
                    risk_on_series = idx_df['Adj Close'] > idx_df['MA200']
                else:
                    try:
                        idx_df = fdr.DataReader("KS11", spy_start, end_date.strftime('%Y-%m-%d'))
                        idx_df['MA120'] = idx_df['Close'].rolling(window=120).mean()
                        risk_on_series = idx_df['Close'] > idx_df['MA120']
                    except:
                        risk_on_series = pd.Series(True, index=df_raw.index)
                
                # 기간 필터 적용
                df_raw = df_raw.loc[start_date.strftime('%Y-%m-%d'):]
                
                # 2) 전략별 최적화 실행
                best_return, best_practical = find_best_overall_strategy(
                    df_raw, 
                    mode=opt_mode_str, 
                    fee_roundtrip=0.0020 if market_code == "US" else 0.0035,
                    market_risk_on=risk_on_series
                )
                
                if best_return is None:
                    st.error("조건을 충족하는 최적화 결과를 도출하지 못했습니다 (모든 전략 거래수 부족 등).")
                else:
                    # 3) 최고 수익률 전략 박스 표출
                    st.markdown("<div class='winner-card'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='winner-title'>🏆 1위: 최고 수익률 전략 (CAGR 극대화)</div>", unsafe_allow_html=True)
                    st.write(f"**전략 명칭:** {best_return['strategy_name']}")
                    st.write(f"**최적 파라미터 조합:** `{best_return['best_params']}`")
                    st.write(f"**Train CAGR (학습):** {best_return['train_metrics'].get('CAGR',0)*100:.2f}% | **Test CAGR (검증):** {best_return['test_metrics'].get('CAGR',0)*100:.2f}%")
                    st.write(f"**학습 구간 MDD:** {best_return['train_metrics'].get('MDD',0)*100:.2f}% | **거래 횟수:** {best_return['train_metrics'].get('Number of Trades',0)}회")
                    
                    if best_return['train_metrics'].get('MDD', 0) < -0.70:
                        st.warning("⚠️ 경고: 학습 구간 최대 낙폭(MDD)이 -70%보다 큽니다. 과도한 자산 하락 위험이 존재하므로 주의하세요.")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # 4) 실전형 최고 전략 박스 표출
                    st.markdown("<div class='winner-card' style='border-color: #007AFF; background: rgba(0, 122, 255, 0.05);'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='winner-title' style='color: #0056B3;'>🛡️ 2위: 실전형 위험조정 최고 전략 (안정성 최우선)</div>", unsafe_allow_html=True)
                    
                    p_strat_data = best_practical['strategy_data']
                    st.write(f"**전략 명칭:** {p_strat_data['strategy_name']}")
                    st.write(f"**최적 파라미터 조합:** `{p_strat_data['best_params']}`")
                    st.write(f"**종합 실전 스코어:** {best_practical['score']:.3f}")
                    st.write(f"**Train CAGR (학습):** {p_strat_data['train_metrics'].get('CAGR',0)*100:.2f}% | **Test CAGR (검증):** {p_strat_data['test_metrics'].get('CAGR',0)*100:.2f}%")
                    st.write(f"**학습 구간 MDD:** {p_strat_data['train_metrics'].get('MDD',0)*100:.2f}% | **샤프 지수:** {p_strat_data['train_metrics'].get('Sharpe Ratio',0):.2f}")
                    
                    if not best_practical['is_suitable']:
                        st.markdown("<div class='warn-card' style='padding: 10px; margin-top: 10px;'>❌ **실전 투입 부적합 경고**: 본 종목에 대한 최적 전략들이 MDD -35% 초과, 샤프 0.5 미만, 프로핏팩터 1.2 미만 등 실전 기준을 미달했습니다. 실전 투자에 유의하세요.</div>", unsafe_allow_html=True)
                    else:
                        st.success("✅ 본 전략은 MDD, 샤프 지수 및 거래 횟수 등 모든 실전 투입 기준 조건을 충족하여 권장됩니다.")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # 5) 과최적화 리스크 진단 카드
                    st.subheader("⚠️ 과최적화(Overfitting) 리스크 판단")
                    is_overfitted = best_return['overfitting_warning'] or p_strat_data['overfitting_warning']
                    
                    if is_overfitted:
                        st.markdown("<div class='warn-card'>", unsafe_allow_html=True)
                        st.markdown("### 🚨 과최적화 위험 감지!")
                        st.write("학습 데이터셋(Train)과 검증 데이터셋(Test) 구간의 연평균 수익률 격차가 20%p 이상 벌어지거나 검증 구간 성과가 저조합니다. 과거 백테스트 곡선에 파라미터가 지나치게 끼워맞춰졌을 가능성이 커, 향후 실전 투자 시 손실이 발생할 수 있습니다.")
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.info("✅ 과최적화 리스크 낮음: 학습 구간과 검증 구간의 성능 격차가 오차 범위 이내이며 고른 성과 분포를 보입니다.")
                        
                    # 6) 두 데이터셋 간 성과 바 차트 비교
                    st.subheader("📊 학습(Train) vs 검증(Test) 성과 비교 시각화")
                    categories = ['우승 전략 CAGR', '우승 전략 MDD', '실전 전략 CAGR', '실전 전략 MDD']
                    
                    train_vals = [
                        best_return['train_metrics'].get('CAGR',0) * 100,
                        best_return['train_metrics'].get('MDD',0) * 100,
                        p_strat_data['train_metrics'].get('CAGR',0) * 100,
                        p_strat_data['train_metrics'].get('MDD',0) * 100
                    ]
                    test_vals = [
                        best_return['test_metrics'].get('CAGR',0) * 100,
                        best_return['test_metrics'].get('MDD',0) * 100,
                        p_strat_data['test_metrics'].get('CAGR',0) * 100,
                        p_strat_data['test_metrics'].get('MDD',0) * 100
                    ]
                    
                    fig = go.Figure(data=[
                        go.Bar(name='Train (학습 구간 70%)', x=categories, y=train_vals, marker_color='#34C759'),
                        go.Bar(name='Test (검증 구간 30%)', x=categories, y=test_vals, marker_color='#FF9500')
                    ])
                    fig.update_layout(barmode='group', yaxis_title='성능 수치 (%)', template='plotly_white', height=400)
                    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("왼쪽 사이드바에서 최적화 탐색 모드를 지정하고 [🔍 전략 최적화 탐색 시작] 단추를 누르면 다중 백테스트 연산을 시작합니다.")
