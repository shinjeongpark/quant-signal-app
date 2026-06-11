# -*- coding: utf-8 -*-
"""
2_전략백테스트.py - 개별 종목 대상 전략 백테스트 실행 및 성과 분석
단일 종목과 원하는 전략을 선정하여 과거 성과 시뮬레이션을 돌려보고
CAGR, Sharpe Ratio, 월별 수익률 히트맵 등을 검증합니다.
"""

import streamlit as st
import datetime
import pandas as pd
import plotly.graph_objects as go
from src.data_loader import get_stock_data, get_market_status
from src.strategies import calculate_strategy_signals, get_strategy_list
from src.backtester import run_backtest

st.set_page_config(page_title="전략 백테스트", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .metric-box { background: #F3F4F6; border-radius: 8px; padding: 12px; border: 1px solid #E5E7EB; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: bold; color: #111827; }
    .metric-label { font-size: 0.85rem; color: #4B5563; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>📈 개별 종목 퀀트 전략 백테스트</div>", unsafe_allow_html=True)

# 1. 사이드바 - 파라미터 제어 판넬
st.sidebar.header("🛠️ 백테스트 설정")

market = st.sidebar.radio("시장 선택", ["미국 시장 (US)", "한국 시장 (KR)"])
market_code = "US" if "미국" in market else "KR"

# 티커 입력 헬퍼 가이드
if market_code == "US":
    default_ticker = "AAPL"
    ticker = st.sidebar.text_input("티커 입력 (예: AAPL, TSLA, NVDA)", default_ticker).upper().strip()
else:
    default_ticker = "005930"
    ticker = st.sidebar.text_input("종목코드 입력 (예: 005930, 000660)", default_ticker).strip()

# 기간 설정
today = datetime.date.today()
default_start = today - datetime.timedelta(days=365*5) # 기본 5년 백테스트
start_date = st.sidebar.date_input("시작 날짜", default_start)
end_date = st.sidebar.date_input("종료 날짜", today)

# 전략 선택
strategies = get_strategy_list()
selected_strategy = st.sidebar.selectbox("테스트할 전략 선택", strategies)

# 거래비용 및 진입 시점 옵션
default_fee = 0.0020 if market_code == "US" else 0.0035
fee_roundtrip = st.sidebar.number_input("왕복 거래비용 (수수료+슬리피지) 비율", min_value=0.0, max_value=0.05, value=default_fee, step=0.0005, format="%.4f")

entry_on_next_open = st.sidebar.checkbox("다음 거래일 시가(Open)에 진입 (체크 해제 시 종가 진입)", value=True)
use_market_filter = st.sidebar.checkbox("시장 상태 필터(Risk-On/Off) 적용", value=True)

# 백테스트 실행 버튼
run_btn = st.sidebar.button("🚀 백테스트 실행")

# 2. 결과 출력 영역
if run_btn:
    if not ticker:
        st.error("종목코드(티커)를 입력해 주세요.")
    elif start_date >= end_date:
        st.error("시작 날짜는 종료 날짜보다 이전이어야 합니다.")
    else:
        with st.spinner(f"{ticker} 데이터를 다운로드하고 백테스트를 실행하는 중..."):
            # 1) 주가 데이터 및 이평선 지표 로드
            # 200일 이평선 연산을 보장하기 위해 시작 날짜보다 대략 1년 정도 앞선 날짜부터 데이터 로드
            fetch_start = (start_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
            df_raw = get_stock_data(ticker, market=market_code, start_date=fetch_start, end_date=end_date.strftime('%Y-%m-%d'))
            
            if df_raw is None or df_raw.empty or len(df_raw) < 200:
                st.error("데이터 수집에 실패했거나 데이터 양이 너무 부족합니다 (최소 200 영업일 필요). 종목코드를 다시 확인해 주세요.")
            else:
                # 시장 정보 산출
                m_status = get_market_status()
                m_risk_on_val = m_status["US_Overall"] if market_code == "US" else m_status["KR_Overall"]
                # 간단히 일별 시장 리스크 시리즈 매핑
                # (정밀한 백테스트를 위해 전체 날짜 범위에 대해 시장 지수 이평선을 생성하여 맵핑하는 방식을 임시로 Series로 제공)
                # 데이터 로더의 지수 분석 함수 사용
                spy_start = fetch_start
                if market_code == "US":
                    idx_df = get_stock_data("SPY", "US", spy_start, end_date.strftime('%Y-%m-%d'))
                    idx_df['MA200'] = idx_df['Adj Close'].rolling(window=200).mean()
                    risk_on_series = idx_df['Adj Close'] > idx_df['MA200']
                else:
                    # KOSPI
                    try:
                        idx_df = fdr.DataReader("KS11", spy_start, end_date.strftime('%Y-%m-%d'))
                        idx_df['MA120'] = idx_df['Close'].rolling(window=120).mean()
                        risk_on_series = idx_df['Close'] > idx_df['MA120']
                    except:
                        # KOSPI 로드 실패 시 무조건 Risk-On 가정 폴백
                        risk_on_series = pd.Series(True, index=df_raw.index)
                
                # 2) 전략 신호 계산
                df_with_signals = calculate_strategy_signals(
                    df_raw, selected_strategy, 
                    market_risk_on=risk_on_series, 
                    use_filter=use_market_filter
                )
                
                # 사용자가 입력한 시작 날짜 구간만 최종 필터링
                df_with_signals = df_with_signals.loc[start_date.strftime('%Y-%m-%d'):]
                
                if df_with_signals.empty or len(df_with_signals) < 10:
                    st.error("선택한 분석 기간 내에 주가 데이터가 존재하지 않습니다.")
                else:
                    # 3) 백테스트 구동
                    metrics, df_equity, df_trades = run_backtest(
                        df_with_signals, 
                        fee_roundtrip=fee_roundtrip, 
                        entry_on_next_open=entry_on_next_open
                    )
                    
                    st.success("백테스트 완료!")
                    
                    # 4) 성과 평가지표 요약 표시 (4열 카드 레이아웃)
                    st.subheader("📊 백테스트 주요 지표 요약")
                    
                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    with col_m1:
                        cagr_val = metrics.get('CAGR', 0.0)
                        st.markdown(f"""<div class='metric-box'>
                            <div class='metric-value' style='color:{'red' if cagr_val > 0 else 'blue'}'>{cagr_val*100:.2f}%</div>
                            <div class='metric-label'>연평균 복리 수익률 (CAGR)</div>
                        </div>""", unsafe_allow_html=True)
                    with col_m2:
                        mdd_val = metrics.get('MDD', 0.0)
                        st.markdown(f"""<div class='metric-box'>
                            <div class='metric-value' style='color:blue'>{mdd_val*100:.2f}%</div>
                            <div class='metric-label'>최대 낙폭 (MDD)</div>
                        </div>""", unsafe_allow_html=True)
                    with col_m3:
                        sharpe_val = metrics.get('Sharpe Ratio', 0.0)
                        st.markdown(f"""<div class='metric-box'>
                            <div class='metric-value'>{sharpe_val:.2f}</div>
                            <div class='metric-label'>샤프 지수 (Sharpe Ratio)</div>
                        </div>""", unsafe_allow_html=True)
                    with col_m4:
                        wr_val = metrics.get('Win Rate', 0.0)
                        st.markdown(f"""<div class='metric-box'>
                            <div class='metric-value'>{wr_val*100:.1f}%</div>
                            <div class='metric-label'>거래 승률 (Win Rate)</div>
                        </div>""", unsafe_allow_html=True)
                        
                    # 추가 상세 지표 표로 렌더링
                    st.markdown("<br>", unsafe_allow_html=True)
                    det_data = {
                        "성과 평가 지표": [
                            "누적 수익률 (Total Return)", "연평균 성장률 (CAGR)", "최대 낙폭 (MDD)", 
                            "샤프 지수 (Sharpe Ratio)", "소르티노 지수 (Sortino Ratio)", "칼마 지수 (Calmar Ratio)",
                            "프로핏 팩터 (Profit Factor)", "총 거래 횟수", "승률 (Win Rate)", "평균 이익 거래 수익률", 
                            "평균 손실 거래 수익률", "손익비 (Payoff Ratio)", "자산 회전율 (Turnover)", "최고 월 수익률", "최저 월 수익률"
                        ],
                        "수치": [
                            f"{metrics.get('Total Return', 0)*100:.2f}%",
                            f"{metrics.get('CAGR', 0)*100:.2f}%",
                            f"{metrics.get('MDD', 0)*100:.2f}%",
                            f"{metrics.get('Sharpe Ratio', 0):.2f}",
                            f"{metrics.get('Sortino Ratio', 0):.2f}",
                            f"{metrics.get('Calmar Ratio', 0):.2f}",
                            f"{metrics.get('Profit Factor', 0):.2f}",
                            f"{metrics.get('Number of Trades', 0)}회",
                            f"{metrics.get('Win Rate', 0)*100:.2f}%",
                            f"{metrics.get('Average Win', 0)*100:.2f}%",
                            f"{metrics.get('Average Loss', 0)*100:.2f}%",
                            f"{metrics.get('Payoff Ratio', 0):.2f}",
                            f"{metrics.get('Turnover', 0):.2f}",
                            f"{metrics.get('Best Month', 0)*100:.2f}%",
                            f"{metrics.get('Worst Month', 0)*100:.2f}%"
                        ]
                    }
                    df_det = pd.DataFrame(det_data)
                    st.table(df_det)
                    
                    # 5) 자산 곡선 및 낙폭 차트 시각화
                    st.subheader("📈 자산 평가액 추이 및 낙폭 (Drawdown)")
                    
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(x=df_equity.index, y=df_equity['Equity'], name="포트폴리오 자산", line=dict(color='#34C759', width=2)))
                    fig_eq.update_layout(title="일별 자산 곡선 (Equity Curve)", height=350, template='plotly_white')
                    st.plotly_chart(fig_eq, use_container_width=True)
                    
                    fig_dd = go.Figure()
                    fig_dd.add_trace(go.Scatter(x=df_equity.index, y=df_equity['Drawdown'] * 100, name="낙폭(%)", fill='tozeroy', line=dict(color='#FF3B30', width=1.5)))
                    fig_dd.update_layout(title="일별 낙폭 추이 (%)", height=250, template='plotly_white')
                    st.plotly_chart(fig_dd, use_container_width=True)
                    
                    # 6) 월별 수익률 Heatmap 시각화
                    st.subheader("📅 월별 수익률 테이블 (Heatmap)")
                    m_heatmap = metrics.get('Monthly Heatmap')
                    if m_heatmap is not None and not m_heatmap.empty:
                        # 보기 편하게 백분율 문자열 변환
                        m_heatmap_pct = m_heatmap * 100
                        # 월 헤더 변경 (1 -> 1월)
                        m_heatmap_pct.columns = [f"{col}월" for col in m_heatmap_pct.columns]
                        st.dataframe(m_heatmap_pct.style.format("{:.2f}%").background_gradient(cmap='RdYlGn', axis=None), use_container_width=True)
                    else:
                        st.write("월별 수익률 데이터를 산출할 수 없습니다.")
                        
                    # 7) 상세 거래 대장 노출
                    st.subheader("📋 세부 매매 거래 대장")
                    if df_trades is not None and not df_trades.empty:
                        # 깔끔하게 가공해서 노출
                        df_trades_disp = df_trades.copy()
                        if '수익률' in df_trades_disp.columns:
                            df_trades_disp['수익률'] = df_trades_disp['수익률'].map(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "")
                        if '실현손익' in df_trades_disp.columns:
                            df_trades_disp['실현손익'] = df_trades_disp['실현손익'].map(lambda x: f"{x:,.0f}원" if pd.notna(x) else "")
                        if '거래금액' in df_trades_disp.columns:
                            df_trades_disp['거래금액'] = df_trades_disp['거래금액'].map(lambda x: f"{x:,.0f}원" if pd.notna(x) else "")
                        if '잔고' in df_trades_disp.columns:
                            df_trades_disp['잔고'] = df_trades_disp['잔고'].map(lambda x: f"{x:,.0f}원" if pd.notna(x) else "")
                            
                        st.dataframe(df_trades_disp, use_container_width=True)
                    else:
                        st.info("기간 중 체결된 거래가 존재하지 않습니다.")
else:
    st.info("왼쪽 패널의 설정을 확인한 뒤 [🚀 백테스트 실행] 버튼을 눌러주세요.")
