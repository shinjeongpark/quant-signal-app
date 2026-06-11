# -*- coding: utf-8 -*-
"""
6_포트폴리오시뮬레이션.py - 다중 종목 포트폴리오 백테스트 실행 및 리스크 관리
허용 리스크율과 최대 보유 종목 수, 주기적 리밸런싱 주기를 대입하여
전체 포트폴리오 자산 곡선과 종목별 수익 기여도를 측정합니다.
"""

import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import get_market_status, get_stock_data
from src.strategies import get_strategy_list
from src.portfolio import run_portfolio_backtest
from src.utils import US_UNIVERSES, KR_UNIVERSES

st.set_page_config(page_title="포트폴리오 시뮬레이션", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .metric-card { background: #FFFFFF; border-radius: 8px; padding: 15px; border: 1px solid #E5E7EB; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>💼 다중 종목 포트폴리오 시뮬레이터</div>", unsafe_allow_html=True)
st.write("여러 종목에 분산 투자할 때, 리스크 비중 설계(1% 룰) 및 리밸런싱 주기에 따른 포트폴리오 전체의 과거 성장 궤적을 확인합니다.")

# 1. 사이드바 제어판
st.sidebar.header("🛠️ 시뮬레이션 환경 변수")
market = st.sidebar.radio("시장 선택", ["미국 시장 (US)", "한국 시장 (KR)"])
market_code = "US" if "미국" in market else "KR"

# 종목 리스트 입력
if market_code == "US":
    default_tickers = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA"
    tickers_str = st.sidebar.text_area("스캔/시뮬레이션 종목 입력 (쉼표 구분)", default_tickers).upper().strip()
    ticker_dict = {t.strip(): US_UNIVERSES["기본 대형주"].get(t.strip(), t.strip()) for t in tickers_str.split(",") if t.strip()}
else:
    default_tickers = "005930,000660,005380,035420,035720"
    tickers_str = st.sidebar.text_area("시뮬레이션 종목코드 입력 (쉼표 구분)", default_tickers).strip()
    ticker_dict = {t.strip(): KR_UNIVERSES["KOSPI 주요 종목"].get(t.strip(), t.strip()) for t in tickers_str.split(",") if t.strip()}

# 기간
today = datetime.date.today()
default_start = today - datetime.timedelta(days=365*4)
start_date = st.sidebar.date_input("시작 날짜", default_start)
end_date = st.sidebar.date_input("종료 날짜", today)

# 전략
strategies = get_strategy_list()
selected_strategy = st.sidebar.selectbox("포트폴리오 전략", strategies)

# 자금 매개변수
st.sidebar.markdown("---")
st.sidebar.write("**💰 포트폴리오 자산 규칙**")
initial_capital = st.sidebar.number_input("초기 투자금 (원/달러)", min_value=1000000, max_value=10000000000, value=50000000, step=5000000)
risk_ratio_pct = st.sidebar.slider("1회 거래당 허용 리스크 비율 (%)", min_value=0.2, max_value=5.0, value=1.0, step=0.1)
risk_ratio = risk_ratio_pct / 100.0

max_holdings = st.sidebar.number_input("동시 보유 최대 종목 수", min_value=1, max_value=20, value=5)
max_weight_pct = st.sidebar.slider("종목당 최대 비중 제한 (%)", min_value=5, max_value=100, value=20, step=5)
max_weight = max_weight_pct / 100.0

rebalance_period = st.sidebar.selectbox("리밸런싱 주기", ["weekly", "monthly", "daily"])

run_port_btn = st.sidebar.button("🚀 포트폴리오 백테스트 실행")

# 2. 실행 영역
if run_port_btn:
    if not ticker_dict:
        st.error("종목 코드가 유효하지 않습니다.")
    elif start_date >= end_date:
        st.error("시작 날짜는 종료 날짜보다 빨라야 합니다.")
    else:
        with st.spinner("포트폴리오 분산 투자 백테스트 시뮬레이션을 작동 중입니다..."):
            # 시장 데이터 조회
            m_status = get_market_status()
            spy_start = (start_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
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
                    risk_on_series = None
            
            # 포트폴리오 구동
            metrics, df_port, df_trades = run_portfolio_backtest(
                tickers=ticker_dict,
                market=market_code,
                strategy_name=selected_strategy,
                initial_capital=initial_capital,
                risk_ratio=risk_ratio,
                max_holdings=max_holdings,
                max_weight=max_weight,
                rebalance_period=rebalance_period,
                fee_roundtrip=0.0020 if market_code == "US" else 0.0035,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                market_risk_on=risk_on_series
            )
            
            if metrics is None or df_port.empty:
                st.error("시뮬레이션 구동 실패: 종목 데이터 조회 실패 혹은 거래 횟수가 전혀 발생하지 않았습니다.")
            else:
                st.success("포트폴리오 백테스트 성공 완료!")
                
                # 가. 메인 요약
                st.subheader("📊 포트폴리오 투자 분석 요약")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    cagr_val = metrics.get('CAGR', 0.0)
                    st.markdown(f"<div class='metric-card'><h4>연평균 수익률(CAGR)</h4><h2 style='color:{'red' if cagr_val > 0 else 'blue'}'>{cagr_val*100:.2f}%</h2></div>", unsafe_allow_html=True)
                with col2:
                    mdd_val = metrics.get('MDD', 0.0)
                    st.markdown(f"<div class='metric-card'><h4>포트폴리오 MDD</h4><h2 style='color:blue'>{mdd_val*100:.2f}%</h2></div>", unsafe_allow_html=True)
                with col3:
                    st.markdown(f"<div class='metric-card'><h4>샤프 지수</h4><h2>{metrics.get('Sharpe Ratio', 0.0):.2f}</h2></div>", unsafe_allow_html=True)
                with col4:
                    st.markdown(f"<div class='metric-card'><h4>총 거래 체결 횟수</h4><h2>{metrics.get('Number of Trades', 0)}회</h2></div>", unsafe_allow_html=True)
                    
                # 나. 자산 변화 곡선 차트
                st.markdown("<br>", unsafe_allow_html=True)
                fig_port = go.Figure()
                fig_port.add_trace(go.Scatter(x=df_port.index, y=df_port['Equity'], name="포트폴리오 평가가치", line=dict(color='#007AFF', width=2)))
                fig_port.update_layout(title="포트폴리오 자산 곡선 (Daily Equity Curve)", height=350, template='plotly_white')
                st.plotly_chart(fig_port, use_container_width=True)
                
                # 다. 종목별 성과 누적 손익 기여도 (Contribution) 바 차트
                st.subheader("🔥 종목별 포트폴리오 수익 기여도 (Cumulative Contribution)")
                cont_dict = metrics.get('Contribution', {})
                if cont_dict:
                    df_cont = pd.DataFrame(list(cont_dict.items()), columns=['종목명', '실현손익_기여액'])
                    # 손익 기여도 정렬
                    df_cont.sort_values(by="실현손익_기여액", ascending=False, inplace=True)
                    
                    # 칼라 매핑 (수익은 빨강/초록, 손실은 파랑)
                    colors_cont = ['#34C759' if val >= 0 else '#FF3B30' for val in df_cont['실현손익_기여액']]
                    
                    fig_bar = go.Figure()
                    fig_bar.add_trace(go.Bar(
                        x=df_cont['종목명'], y=df_cont['실현손익_기여액'],
                        marker_color=colors_cont
                    ))
                    fig_bar.update_layout(yaxis_title="실현손익 누적액 (통화 기준)", template='plotly_white', height=350)
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("기간 중 청산된 매매 내역이 없어 종목별 기여도 그래프를 표시할 수 없습니다.")
                    
                # 라. 상세 매매 로그
                st.subheader("📋 포트폴리오 세부 거래 내역 대장")
                if df_trades is not None and not df_trades.empty:
                    df_tr_disp = df_trades.copy()
                    if '수량' in df_tr_disp.columns:
                        df_tr_disp['수량'] = df_tr_disp['수량'].map(lambda x: f"{x:.2f}")
                    if '가격' in df_tr_disp.columns:
                        df_tr_disp['가격'] = df_tr_disp['가격'].map(lambda x: f"{x:,.2f}")
                    if '실현손익' in df_tr_disp.columns:
                        df_tr_disp['실현손익'] = df_tr_disp['실현손익'].map(lambda x: f"{x:,.0f}원")
                    st.dataframe(df_tr_disp, use_container_width=True)
                else:
                    st.info("체결된 거래가 없습니다.")
else:
    st.info("시뮬레이션 환경 변수를 지정하고 [🚀 포트폴리오 백테스트 실행] 단추를 누르면 분석을 시도합니다.")
