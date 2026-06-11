# -*- coding: utf-8 -*-
"""
4_종목스캐너.py - 종목 발굴 및 기술적 신호 일괄 스캔 페이지
미국 또는 한국 시장의 유니버스를 선택하여 모든 종목의
종합점수, 추세/모멘텀/거래량 지수, 신호, 매수 트리거 및 손절가를 포착합니다.
"""

import streamlit as st
import pandas as pd
import time
from src.data_loader import get_market_status
from src.utils import US_UNIVERSES, KR_UNIVERSES
from src.strategies import get_strategy_list
from src.signal_engine import generate_signals_for_universe

st.set_page_config(page_title="종목 스캐너", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .scan-status { padding: 10px; border-radius: 8px; font-weight: bold; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>🔍 실시간 퀀트 종목 스캐너</div>", unsafe_allow_html=True)
st.write("선택한 시장 유니버스의 전 종목을 동시에 스캔하여 현재 기술적 매수 적기 종목과 최적 타점을 리포트합니다.")

# 1. 제어 판넬
col_ctrl1, col_ctrl2 = st.columns(2)

with col_ctrl1:
    market = st.radio("분석할 시장 선택", ["미국 시장 (US)", "한국 시장 (KR)"])
    market_code = "US" if "미국" in market else "KR"
    
    # 전략 선택
    strategies = get_strategy_list()
    selected_strategy = st.selectbox("스캔에 적용할 전략 알고리즘", strategies)

with col_ctrl2:
    # 유니버스 선택
    if market_code == "US":
        universe_opt = st.selectbox("스캔 대상 유니버스", ["전체 미국 기본주 (ETF + 대형주)", "기본 ETF만", "기본 대형주만", "직접 티커 입력"])
        if universe_opt == "기본 ETF만":
            universe = US_UNIVERSES["기본 ETF"]
        elif universe_opt == "기본 대형주만":
            universe = US_UNIVERSES["기본 대형주"]
        elif universe_opt == "직접 티커 입력":
            user_tickers = st.text_input("쉼표(,)로 구분하여 티커들을 입력하세요 (예: AAPL,MSFT,QQQ)", "AAPL,MSFT,TSLA").upper()
            universe = {t.strip(): t.strip() for t in user_tickers.split(",") if t.strip()}
        else:
            # 전체 병합
            universe = {**US_UNIVERSES["기본 ETF"], **US_UNIVERSES["기본 대형주"]}
    else:
        universe_opt = st.selectbox("스캔 대상 유니버스", ["전체 한국 기본주 (코스피 + 코스닥)", "KOSPI 주요 종목만", "KOSDAQ 주요 종목만", "직접 코드 입력"])
        if universe_opt == "KOSPI 주요 종목만":
            universe = KR_UNIVERSES["KOSPI 주요 종목"]
        elif universe_opt == "KOSDAQ 주요 종목만":
            universe = KR_UNIVERSES["KOSDAQ 주요 종목"]
        elif universe_opt == "직접 코드 입력":
            user_codes = st.text_input("쉼표(,)로 구분하여 종목코드를 입력하세요 (예: 005930,000660)", "005930,000660")
            universe = {c.strip(): c.strip() for c in user_codes.split(",") if c.strip()}
        else:
            # 전체 병합
            universe = {**KR_UNIVERSES["KOSPI 주요 종목"], **KR_UNIVERSES["KOSDAQ 주요 종목"]}

# 스캔 실행 버튼
run_scan = st.button("🚀 종목 스캔 탐색 시작")

# 2. 스캔 실행 및 상태바 처리
if run_scan:
    if not universe:
        st.error("스캔할 종목 리스트가 비어있습니다.")
    else:
        # 진행 상태 초기화
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 시장 상태 확인
        m_status = get_market_status()
        market_risk_on = m_status["US_Overall"] if market_code == "US" else m_status["KR_Overall"]
        
        # 종목 루프 돌며 순차 계산
        results = []
        tickers_to_scan = list(universe.keys())
        total_tickers = len(tickers_to_scan)
        
        status_text.write(f"🔄 스캔을 준비하고 있습니다... 총 {total_tickers}개 종목")
        
        # 스캔 성능을 위한 처리
        start_time = time.time()
        
        for idx, tk in enumerate(tickers_to_scan):
            # 진행률 업데이트
            pct = int((idx + 1) / total_tickers * 100)
            progress_bar.progress(pct)
            status_text.write(f"⏳ 스캔 중: {universe[tk]} ({tk}) [{idx+1}/{total_tickers}]")
            
            # 단일 종목 연산 실행
            # 신호 계산용 dict 전달
            sub_dict = {tk: universe[tk]}
            try:
                res_df = generate_signals_for_universe(
                    sub_dict, 
                    market=market_code, 
                    strategy_name=selected_strategy, 
                    market_risk_on=market_risk_on
                )
                if res_df is not None and not res_df.empty:
                    results.append(res_df)
            except Exception as e:
                print(f"[스캐너 오류] {tk}: {e}")
                
        # 최종 진행 정보 정리
        progress_bar.progress(100)
        elapsed = time.time() - start_time
        status_text.success(f"✅ 스캔 완료! 소요 시간: {elapsed:.2f}초")
        
        if results:
            df_final = pd.concat(results, ignore_index=True)
            df_final.sort_values(by="종합점수", ascending=False, inplace=True)
            
            # 세션에 임시 저장 (필터링 및 다운로드 대응)
            st.session_state['scan_result_df'] = df_final
        else:
            st.warning("분석 가능한 유효 데이터가 없습니다.")

# 3. 결과 표시 및 필터링
if 'scan_result_df' in st.session_state:
    df_res = st.session_state['scan_result_df'].copy()
    
    st.markdown("---")
    st.subheader("📋 스캔 결과 데이터 테이블")
    
    # 필터링 라디오 버튼
    sig_filter = st.radio(
        "신호 필터",
        ["전체보기", "BUY (매수 진입 가능)", "WATCH (돌파 감시)", "HOLD (기존 보유 유지)", "SELL (리스크 탈출)"],
        horizontal=True
    )
    
    if "BUY" in sig_filter:
        df_disp = df_res[df_res["신호"] == "BUY"]
    elif "WATCH" in sig_filter:
        df_disp = df_res[df_res["신호"] == "WATCH"]
    elif "HOLD" in sig_filter:
        df_disp = df_res[df_res["신호"] == "HOLD"]
    elif "SELL" in sig_filter:
        df_disp = df_res[df_res["신호"] == "SELL"]
    else:
        df_disp = df_res
        
    # 출력 컬럼 정리
    disp_cols = [
        "시장", "티커", "종목명", "현재가", "신호", "종합점수", "추세점수", "모멘텀점수", 
        "거래량점수", "변동성점수", "매수 트리거 가격", "손절가", "1차 목표가", "2차 목표가", "손익비", "ATR", "RSI14"
    ]
    
    st.dataframe(df_disp[disp_cols], use_container_width=True)
    
    # CSV 다운로드 기능
    csv = df_disp[disp_cols].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 스캔 결과 CSV 파일 다운로드",
        data=csv,
        file_name=f"quant_scan_result_{datetime.date.today().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )
