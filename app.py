# -*- coding: utf-8 -*-
"""
app.py - 메인 대시보드 화면
미국과 한국 주식 시장의 Risk-On/Off 필터 상태를 한눈에 보여주고,
오늘의 추천 매수 후보 상위 종목 및 서비스 면책 조항을 표시합니다.
"""

import streamlit as st
import datetime
import pandas as pd

# 모듈 경로를 인식할 수 있도록 보장
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import get_market_status, clear_cache
from src.utils import US_UNIVERSES, KR_UNIVERSES
from src.signal_engine import generate_signals_for_universe

# 1. Streamlit 기본 레이아웃 구성
st.set_page_config(
    page_title="Antigravity 퀀트 신호 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 프리미엄 느낌을 주는 커스텀 CSS 스타일 정의 (Glassmorphism 및 세련된 테두리 디자인)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #E5E7EB;
        text-align: center;
        margin-bottom: 15px;
    }
    .risk-on {
        color: #10B981;
        font-weight: bold;
        font-size: 1.5rem;
    }
    .risk-off {
        color: #EF4444;
        font-weight: bold;
        font-size: 1.5rem;
    }
    .footer-text {
        font-size: 0.85rem;
        color: #6B7280;
        text-align: center;
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid #E5E7EB;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>📈 기술적 퀀트 투자 신호 포털 MVP</div>", unsafe_allow_html=True)

# 3. 사이드바 구성 및 캐시 관리
st.sidebar.header("⚙️ 시스템 관리")
if st.sidebar.button("🧹 로컬 캐시 초기화"):
    success = clear_cache()
    if success:
        st.sidebar.success("캐시 데이터베이스를 삭제했습니다.")
    else:
        st.sidebar.error("캐시 초기화 중 오류가 발생했습니다.")

# 4. 시장 상태 (Risk-On / Risk-Off) 판정 영역
st.subheader("🌐 실시간 글로벌 시장 상태 (Market Filter)")

# 데이터 로딩 상태 바 표시
with st.spinner("지수 및 시장 위험 지표를 계산 중입니다..."):
    market_status = get_market_status()

# 2열 레이아웃으로 미국장 / 한국장 노출
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='status-card'>", unsafe_allow_html=True)
    st.markdown("### 🇺🇸 미국 주식 시장")
    
    spy_status = "🟢 Risk-On (매수 가능)" if market_status["US_SPY_Risk"] else "🔴 Risk-Off (신규 매수 자제)"
    qqq_status = "🟢 Risk-On (성장주 강세)" if market_status["US_QQQ_Risk"] else "🔴 Risk-Off (성장주 약세)"
    overall_us = "🚀 Risk-On (상승 트렌드)" if market_status["US_Overall"] else "⚠️ Risk-Off (대피 구간)"
    
    st.write(f"**SPY 상태 (종가 vs MA200):** {status_color(market_status['US_SPY_Risk'])}")
    st.write(f"**QQQ 상태 (종가 vs MA200):** {status_color(market_status['US_QQQ_Risk'])}")
    st.markdown(f"**통합 미국 시장 상태:** <span class='{'risk-on' if market_status['US_Overall'] else 'risk-off'}'>{overall_us}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='status-card'>", unsafe_allow_html=True)
    st.markdown("### 🇰🇷 한국 주식 시장")
    
    overall_kr = "🚀 Risk-On (상승 트렌드)" if market_status["KR_Overall"] else "⚠️ Risk-Off (대피 구간)"
    
    st.write(f"**KOSPI 상태 (종가 vs MA120):** {status_color(market_status['KR_KOSPI_Risk'])}")
    st.write(f"**KOSDAQ 상태 (종가 vs MA120):** {status_color(market_status['KR_KOSDAQ_Risk'])}")
    st.markdown(f"**통합 한국 시장 상태:** <span class='{'risk-on' if market_status['KR_Overall'] else 'risk-off'}'>{overall_kr}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# 헬퍼 함수 정의
def status_color(is_on):
    return "🟢 Risk-On" if is_on else "🔴 Risk-Off"

# 5. 메인 대시보드 내용: 오늘의 매수 추천 후보
st.markdown("---")
st.subheader("🔥 오늘의 최우수 매수 관심 종목 Top 10")
st.info("이 리스트는 기본 대형주 및 ETF 유니버스 내에서 '전략 A: 추세 모멘텀 눌림목' 전략 기준, 기술적 종합점수가 높은 순으로 자동 산출되었습니다. 상세 타점은 좌측 메뉴의 '종목스캐너' 또는 '매수매도신호' 탭에서 확인하실 수 있습니다.")

# 미국 대형주 5개 + 한국 대형주 5개 샘플링하여 스캔
sample_us = {"AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "구글"}
sample_kr = {"005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", "035420": "NAVER", "035720": "카카오"}

with st.spinner("종목의 기술적 지표와 종합 점수를 계산하는 중... (캐싱이 적용되어 반복 호출 시 빨라집니다)"):
    df_us_signals = generate_signals_for_universe(sample_us, market="US", strategy_name="전략 A: 추세 모멘텀 눌림목", market_risk_on=market_status["US_Overall"])
    df_kr_signals = generate_signals_for_universe(sample_kr, market="KR", strategy_name="전략 A: 추세 모멘텀 눌림목", market_risk_on=market_status["KR_Overall"])

# 두 데이터 프레임 병합
combined_list = []
if df_us_signals is not None and not df_us_signals.empty:
    combined_list.append(df_us_signals)
if df_kr_signals is not None and not df_kr_signals.empty:
    combined_list.append(df_kr_signals)

if combined_list:
    df_all = pd.concat(combined_list, ignore_index=True)
    df_all.sort_values(by="종합점수", ascending=False, inplace=True)
    
    # 주요 칼럼 정돈하여 표출
    disp_cols = ["시장", "티커", "종목명", "현재가", "신호", "종합점수", "RSI14", "손절가", "1차 목표가"]
    st.dataframe(df_all[disp_cols].head(10), use_container_width=True)
else:
    st.warning("스캔 대상 데이터를 불러오는 데 실패했습니다.")

# 6. 최근 백테스트 최고 수익률 전략 정보
st.markdown("---")
st.subheader("🏆 백테스트 가이드 및 최고 성과 전략 요약")
st.markdown("""
왼쪽 사이드바의 **[3_전략최적화]** 메뉴를 이용하면 특정 종목에 적합한 우수 알고리즘을 찾아낼 수 있습니다.
- **최고 수익률 전략**: 단순 연평균 수익률(CAGR)을 극대화한 포뮬러입니다.
- **실전형 최고 전략**: 높은 수익률뿐만 아니라, MDD(최대 손실률)를 -35% 이하로 제어하고 샤프지수가 높은 안정적인 운용 적합형 전략입니다.
""")

# 7. 서비스 면책 조항 하단 표시 (요구사항 필수 반영)
st.markdown(
    "<div class='footer-text'>"
    "⚠️ 본 서비스는 투자 참고용이며 투자 자문이 아닙니다. 모든 투자 판단과 책임은 사용자 본인에게 있습니다. "
    "백테스트 결과는 과거 데이터를 기반으로 한 시뮬레이션 결과일 뿐 미래 수익을 보장하지 않습니다."
    "</div>", 
    unsafe_allow_html=True
)
