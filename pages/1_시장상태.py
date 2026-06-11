# -*- coding: utf-8 -*-
"""
1_시장상태.py - 글로벌 시장 분석 및 주가 지수 흐름 시각화
주요 지수(SPY, QQQ, KOSPI, KOSDAQ)의 차트와 추세를 그려주며
시스템 필터가 작동하는 시장 위험 상태를 사용자에게 제공합니다.
"""

import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
import FinanceDataReader as fdr
from src.data_loader import get_market_status, get_stock_data

st.set_page_config(page_title="시장 상태 분석", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .card { background: #FFFFFF; border-radius: 8px; padding: 15px; border: 1px solid #E5E7EB; margin-bottom: 20px; }
    .risk-badge-on { background: #D1FAE5; color: #065F46; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
    .risk-badge-off { background: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 12px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>📈 글로벌 주식 시장 상태 및 지수 분석</div>", unsafe_allow_html=True)
st.write("시스템이 백테스트 및 실시간 종목 스캔 시 사용하는 시장 필터 기준 지수들의 차트와 이평 정배열 상태를 점검합니다.")

# 1. 지수 데이터 수집 및 상태 조회
with st.spinner("최신 지수 데이터를 로드하는 중..."):
    status = get_market_status()

# 2. 미국/한국 통합 요약 카드
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🇺🇸 미국 시장 요약")
    us_status = "<span class='risk-badge-on'>Risk-On (상승세)</span>" if status["US_Overall"] else "<span class='risk-badge-off'>Risk-Off (약세/대피)</span>"
    st.markdown(f"**현재 종합 상태:** {us_status}", unsafe_allow_html=True)
    st.write(f"- **SPY (S&P 500):** {status['SPY_Close']:,} (200일선: {status['SPY_MA200']:,}) -> {'상회 🟢' if status['US_SPY_Risk'] else '하회 🔴'}")
    st.write(f"- **QQQ (나스닥 100):** {status['QQQ_Close']:,} (200일선: {status['QQQ_MA200']:,}) -> {'상회 🟢' if status['US_QQQ_Risk'] else '하회 🔴'}")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🇰🇷 한국 시장 요약")
    kr_status = "<span class='risk-badge-on'>Risk-On (상승세)</span>" if status["KR_Overall"] else "<span class='risk-badge-off'>Risk-Off (약세/대피)</span>"
    st.markdown(f"**현재 종합 상태:** {kr_status}", unsafe_allow_html=True)
    st.write(f"- **KOSPI 지수:** {status['KOSPI_Close']:,} (120일선: {status['KOSPI_MA120']:,}) -> {'상회 🟢' if status['KR_KOSPI_Risk'] else '하회 🔴'}")
    st.write(f"- **KOSDAQ 지수:** {status['KOSDAQ_Close']:,} (120일선: {status['KOSDAQ_MA120']:,}) -> {'상회 🟢' if status['KR_KOSDAQ_Risk'] else '하회 🔴'}")
    st.markdown("</div>", unsafe_allow_html=True)

# 3. 상세 지수 차트 시각화
st.markdown("---")
st.subheader("📊 주요 지수 및 이동평균선 차트")

selected_market = st.radio("시장을 선택하세요", ["미국 시장 (SPY / QQQ)", "한국 시장 (KOSPI / KOSDAQ)"])

today = datetime.date.today()
start_date = (today - datetime.timedelta(days=365*2)).strftime('%Y-%m-%d') # 최근 2개년 차트
end_date = today.strftime('%Y-%m-%d')

if "미국" in selected_market:
    # SPY & QQQ
    col_spy, col_qqq = st.columns(2)
    
    with col_spy:
        st.write("#### SPY (S&P 500 ETF)")
        df_spy = get_stock_data("SPY", "US", start_date, end_date)
        if df_spy is not None and not df_spy.empty:
            df_spy['MA200'] = df_spy['Adj Close'].rolling(window=200).mean()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_spy.index, y=df_spy['Adj Close'], name="SPY 종가", line=dict(color='#007AFF', width=2)))
            fig.add_trace(go.Scatter(x=df_spy.index, y=df_spy['MA200'], name="MA200 (장기추세선)", line=dict(color='gray', width=1.5, dash='dash')))
            fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)
            
    with col_qqq:
        st.write("#### QQQ (Nasdaq 100 ETF)")
        df_qqq = get_stock_data("QQQ", "US", start_date, end_date)
        if df_qqq is not None and not df_qqq.empty:
            df_qqq['MA200'] = df_qqq['Adj Close'].rolling(window=200).mean()
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_qqq.index, y=df_qqq['Adj Close'], name="QQQ 종가", line=dict(color='#5856D6', width=2)))
            fig.add_trace(go.Scatter(x=df_qqq.index, y=df_qqq['MA200'], name="MA200 (장기추세선)", line=dict(color='gray', width=1.5, dash='dash')))
            fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)

else:
    # KOSPI & KOSDAQ
    col_kospi, col_kosdaq = st.columns(2)
    
    with col_kospi:
        st.write("#### KOSPI 지수")
        try:
            df_kospi = fdr.DataReader("KS11", start_date, end_date)
            if df_kospi is not None and not df_kospi.empty:
                df_kospi['MA120'] = df_kospi['Close'].rolling(window=120).mean()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_kospi.index, y=df_kospi['Close'], name="KOSPI 종가", line=dict(color='#FF3B30', width=2)))
                fig.add_trace(go.Scatter(x=df_kospi.index, y=df_kospi['MA120'], name="MA120", line=dict(color='gray', width=1.5, dash='dash')))
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"KOSPI 지수 데이터를 불러오지 못했습니다: {e}")
            
    with col_kosdaq:
        st.write("#### KOSDAQ 지수")
        try:
            df_kosdaq = fdr.DataReader("KQ11", start_date, end_date)
            if df_kosdaq is not None and not df_kosdaq.empty:
                df_kosdaq['MA120'] = df_kosdaq['Close'].rolling(window=120).mean()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_kosdaq.index, y=df_kosdaq['Close'], name="KOSDAQ 종가", line=dict(color='#FF9500', width=2)))
                fig.add_trace(go.Scatter(x=df_kosdaq.index, y=df_kosdaq['MA120'], name="MA120", line=dict(color='gray', width=1.5, dash='dash')))
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"KOSDAQ 지수 데이터를 불러오지 못했습니다: {e}")

# 면책 조항 하단 고정 표시
st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8rem;'>본 서비스는 투자 참고용이며 투자 자문이 아닙니다. 모든 투자 판단과 책임은 사용자 본인에게 있습니다.</div>", unsafe_allow_html=True)
