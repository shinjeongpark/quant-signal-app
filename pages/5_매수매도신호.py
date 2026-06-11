# -*- coding: utf-8 -*-
"""
5_매수매도신호.py - 상세 매매 신호 및 타점 산출 페이지
특정 종목에 대해 투자금 및 리스크 감내율을 반영한 포지션 크기를 제안하며,
Plotly 캔들스틱 차트상에 타겟선과 마커를 렌더링하고 자연어 해석을 제공합니다.
"""

import streamlit as st
import datetime
import pandas as pd
from src.data_loader import get_stock_data, get_market_status
from src.strategies import calculate_strategy_signals, get_strategy_list
from src.signal_engine import calculate_detailed_scores, generate_natural_language_explanation
from src.charting import create_interactive_chart

st.set_page_config(page_title="매수매도 신호 포착", layout="wide")

st.markdown("""
<style>
    .title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 1rem; }
    .signal-box { font-size: 2rem; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
    .sig-buy { background: #D1FAE5; color: #065F46; border: 1px solid #34C759; }
    .sig-watch { background: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }
    .sig-sell { background: #FEE2E2; color: #991B1B; border: 1px solid #EF4444; }
    .sig-neutral { background: #F3F4F6; color: #374151; border: 1px solid #9CA3AF; }
    .calc-card { background: #F9FAFB; border-radius: 8px; padding: 20px; border: 1px solid #E5E7EB; }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>🎯 실시간 매수/매도 타점 및 포지션 설계</div>", unsafe_allow_html=True)
st.write("개별 종목의 구체적인 진입가, 손절가, 목표가와 자산 배분 기준의 주문 수량을 정교하게 제안합니다.")

# 1. 입력 설정 영역 (좌/우 2열 배치)
col_set1, col_set2 = st.columns(2)

with col_set1:
    market = st.radio("분석 대상 시장", ["미국 시장 (US)", "한국 시장 (KR)"])
    market_code = "US" if "미국" in market else "KR"
    
    if market_code == "US":
        ticker = st.text_input("티커 입력 (예: AAPL)", "AAPL").upper().strip()
    else:
        ticker = st.text_input("종목코드 입력 (예: 005930)", "005930").strip()
        
    strategies = get_strategy_list()
    selected_strategy = st.selectbox("적용할 매매 전략", strategies)

with col_set2:
    # 포지션 자금 모델 설정
    st.write("💰 **자금 관리 모델 설정**")
    total_capital = st.number_input("총 투자 자산 규모", min_value=100000, max_value=10000000000, value=10000000, step=1000000, format="%d")
    risk_ratio_input = st.slider("1회 거래 허용 손실률 (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    risk_ratio = risk_ratio_input / 100.0
    
    max_weight_input = st.slider("단일 종목 최대 투자 비중 제한 (%)", min_value=5, max_value=100, value=20, step=5)
    max_weight = max_weight_input / 100.0

run_analysis = st.button("🔍 종목 상세 분석 및 타점 계산")

# 2. 분석 실행 및 결과 가공
if run_analysis:
    if not ticker:
        st.error("종목코드/티커를 바르게 입력하세요.")
    else:
        with st.spinner(f"{ticker} 분석 결과를 도출하고 있습니다..."):
            # 6년 데이터 조회
            today_str = datetime.date.today().strftime('%Y-%m-%d')
            fetch_start = (datetime.date.today() - datetime.timedelta(days=365*6)).strftime('%Y-%m-%d')
            df_raw = get_stock_data(ticker, market=market_code, start_date=fetch_start, end_date=today_str)
            
            if df_raw is None or df_raw.empty or len(df_raw) < 200:
                st.error("데이터 조회가 불가능하거나 축적 데이터 분량이 적습니다. 코드를 다시 확인하세요.")
            else:
                # 시장 데이터 분석
                m_status = get_market_status()
                m_risk_on_val = m_status["US_Overall"] if market_code == "US" else m_status["KR_Overall"]
                
                # 시장 필터 시계열 매핑
                if market_code == "US":
                    idx_df = get_stock_data("SPY", "US", fetch_start, today_str)
                    idx_df['MA200'] = idx_df['Adj Close'].rolling(window=200).mean()
                    risk_on_series = idx_df['Adj Close'] > idx_df['MA200']
                else:
                    try:
                        idx_df = fdr.DataReader("KS11", fetch_start, today_str)
                        idx_df['MA120'] = idx_df['Close'].rolling(window=120).mean()
                        risk_on_series = idx_df['Close'] > idx_df['MA120']
                    except:
                        risk_on_series = pd.Series(True, index=df_raw.index)
                
                # 전략 신호 계산
                df_sig = calculate_strategy_signals(df_raw, selected_strategy, market_risk_on=risk_on_series, use_filter=True)
                
                last_row = df_sig.iloc[-1]
                close = last_row.get('Adj Close', last_row.get('Close', 0))
                atr = last_row.get('ATR14', close * 0.02)
                
                # 종합점수 산정
                scores = calculate_detailed_scores(df_sig, m_risk_on_val)
                tot_score = scores['total_score']
                
                # 신호 판정
                recent_signals = df_sig['Signal'].iloc[-3:]
                has_buy_sig = 1 in recent_signals.values
                has_sell_sig = -1 in recent_signals.values
                
                if has_buy_sig and tot_score >= 75:
                    sig_type = "BUY"
                    sig_class = "sig-buy"
                elif tot_score >= 75:
                    sig_type = "WATCH"
                    sig_class = "sig-watch"
                elif has_sell_sig:
                    sig_type = "SELL"
                    sig_class = "sig-sell"
                elif last_row.get('Position', 0) > 0:
                    sig_type = "HOLD"
                    sig_class = "sig-watch"
                else:
                    sig_type = "NO_ACTION"
                    sig_class = "sig-neutral"
                    
                # 3. 화면 렌더링 시작
                # 가. 신호 판정 박스
                st.markdown(f"<div class='signal-box {sig_class}'>판정 신호: {sig_type} (종합 점수: {tot_score}점)</div>", unsafe_allow_html=True)
                
                # 나. 자연어 해설
                st.markdown("### 💬 기술적 종합 상태 브리핑")
                desc_text = generate_natural_language_explanation(ticker, ticker, df_sig, tot_score, sig_type)
                st.info(desc_text)
                
                # 다. 가격 타점 요약 & 포지션 사이징 카드 (2열 배치)
                col_price, col_size = st.columns(2)
                
                # 타점 연산
                trigger_price = last_row.get('High_20', close)
                stop_loss = close - (atr * 2.0)
                target_1 = close + (atr * 2.0)
                target_2 = close + (atr * 4.0)
                
                risk = close - stop_loss
                reward = target_1 - close
                rr_ratio = reward / risk if risk > 0 else 0.0
                
                currency_unit = "$" if market_code == "US" else "원"
                
                with col_price:
                    st.markdown("<div class='calc-card'>", unsafe_allow_html=True)
                    st.markdown("#### 🎯 전략적 기술 가격 타점")
                    st.write(f"- **현재가:** {close:,.2f} {currency_unit}")
                    st.write(f"- **매수 트리거 가격 (돌파 기준):** {trigger_price:,.2f} {currency_unit}")
                    st.write(f"- **권장 진입 기준가:** {close:,.2f} {currency_unit} 이하")
                    st.write(f"- **초기 손절가 (Stop Loss):** {stop_loss:,.2f} {currency_unit} (현재가 대비 -{((close-stop_loss)/close)*100:.1f}%)")
                    st.write(f"- **1차 목표가 (Target 1):** {target_1:,.2f} {currency_unit} (수익비: +{((target_1-close)/close)*100:.1f}%)")
                    st.write(f"- **2차 목표가 (Target 2):** {target_2:,.2f} {currency_unit}")
                    st.write(f"- **기대 손익비 (RR Ratio):** {rr_ratio:.2f}")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                with col_size:
                    st.markdown("<div class='calc-card'>", unsafe_allow_html=True)
                    st.markdown("#### ⚖️ 권장 포지션 수량 및 비중 설계")
                    
                    # 1주당 손실액
                    loss_per_share = close - stop_loss
                    # 1회 매매당 자산 감내 손실 규모
                    risk_capital = total_capital * risk_ratio
                    
                    # 권장 수량 (자산 손실 비율 기준)
                    raw_shares = risk_capital / loss_per_share if loss_per_share > 0 else 0
                    
                    # 최대 비중(20%) 제한 기준 수량
                    max_alloc = total_capital * max_weight
                    max_shares = max_alloc / close
                    
                    # 최종 결정 수량
                    final_shares = min(raw_shares, max_shares)
                    invested_amount = final_shares * close
                    actual_weight = (invested_amount / total_capital) * 100.0
                    
                    st.write(f"- **허용 최대 손실액:** {risk_capital:,.0f} 원")
                    st.write(f"- **1주당 예상 리스크 액:** {loss_per_share:,.2f} {currency_unit}")
                    st.write(f"- **자산 손실률 기준 주수:** {raw_shares:.1f} 주")
                    st.write(f"- **최대 비중({max_weight_input}%) 제한 주수:** {max_shares:.1f} 주")
                    st.write(f"👉 **최종 권장 매수 수량:** **{final_shares:.1f} 주**")
                    st.write(f"👉 **예상 총 매수 금액:** **{invested_amount:,.0f} 원**")
                    st.write(f"👉 **포트폴리오 내 권장 비중:** **{actual_weight:.2f}%**")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                # 라. Plotly 기술 차트
                st.markdown("---")
                st.subheader("📊 차트 시각화 (캔들스틱 + 보조지표)")
                # 최근 150거래일만 슬라이싱해서 렌더링 (차트 시독성)
                chart_df = df_sig.iloc[-150:]
                fig = create_interactive_chart(chart_df, ticker_name=f"{ticker} ({selected_strategy})")
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("조건을 정의하고 [🔍 종목 상세 분석 및 타점 계산] 버튼을 누르시면 보고서를 렌더링합니다.")
