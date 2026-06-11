# -*- coding: utf-8 -*-
"""
charting.py - 대화형 주가지수 및 기술적 지표 시각화 모듈
Plotly를 사용하여 캔들스틱 차트, 거래량, 이평선, RSI 보조지표,
그리고 매수/매도 타점 및 손절/목표 라인을 미려하게 그립니다.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def create_interactive_chart(df_with_signals, ticker_name="종목"):
    """
    Plotly로 메인 캔들차트, 거래량, 주요 이평선, 매매 마커, RSI를 포함하는 
    인터랙티브 subplots 차트를 생성합니다.
    
    [차트 구성]
    - Row 1: 캔들스틱 + MA20/50/120/200 + 손절가선/목표가선 + 매매 신호 마커 (높이 65%)
    - Row 2: 거래량 차트 (높이 15%)
    - Row 3: RSI14 보조차트 (높이 20%)
    """
    df = df_with_signals.copy()
    
    # x축을 문자열 날짜로 변환하여 주말 공백을 제거하는 깔끔한 차트를 만듭니다.
    df['Date_Str'] = df.index.strftime('%Y-%m-%d')
    
    # 3단 서브플롯 생성 (x축 공유)
    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.60, 0.15, 0.25]
    )
    
    # 1. 캔들스틱 플롯 추가 (Row 1)
    fig.add_trace(
        go.Candlestick(
            x=df['Date_Str'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Adj Close'],
            name="주가(Candle)",
            increasing_line_color='#FF3B30',  # 상승 캔들 빨간색 (한국 정서 반영)
            decreasing_line_color='#007AFF',  # 하락 캔들 파란색
            showlegend=True
        ),
        row=1, col=1
    )
    
    # 2. 이동평균선(MA) 추가 (Row 1)
    colors = {
        'MA20': '#FF9500',   # 주황색
        'MA50': '#34C759',   # 초록색
        'MA120': '#AF52DE',  # 보라색
        'MA200': '#8E8E93'   # 회색
    }
    
    for ma in ['MA20', 'MA50', 'MA120', 'MA200']:
        if ma in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['Date_Str'], y=df[ma],
                    mode='lines',
                    line=dict(width=1.5, color=colors[ma]),
                    name=ma
                ),
                row=1, col=1
            )
            
    # 3. ATR Trailing Stop 라인 추가 (Row 1)
    if 'Trailing_Stop' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date_Str'], y=df['Trailing_Stop'],
                mode='lines',
                line=dict(width=1.5, color='#FFCC00', dash='dot'),
                name="트레일링 스탑"
            ),
            row=1, col=1
        )
        
    # 4. 최근 매수/매도 타점 수평선 추가 (마지막 날 기준 존재 시)
    last_row = df.iloc[-1]
    last_close = last_row.get('Adj Close', 0)
    
    if 'Stop_Loss' in df.columns and not pd.isna(last_row['Stop_Loss']):
        # 손절가 라인 그리기
        fig.add_shape(
            type="line",
            x0=df['Date_Str'].iloc[-30] if len(df) >= 30 else df['Date_Str'].iloc[0],
            y0=last_row['Stop_Loss'],
            x1=df['Date_Str'].iloc[-1],
            y1=last_row['Stop_Loss'],
            line=dict(color="#FF3B30", width=2, dash="dash"),
            row=1, col=1
        )
        # 1차 목표가 라인
        if 'Target_1' in df.columns and not pd.isna(last_row['Target_1']):
            fig.add_shape(
                type="line",
                x0=df['Date_Str'].iloc[-30] if len(df) >= 30 else df['Date_Str'].iloc[0],
                y0=last_row['Target_1'],
                x1=df['Date_Str'].iloc[-1],
                y1=last_row['Target_1'],
                line=dict(color="#34C759", width=2, dash="dash"),
                row=1, col=1
            )
            
    # 5. 매수/매도 진입 마커 추가 (Row 1)
    # Signal == 1 : 매수 마커 (초록색 삼각형 위쪽)
    buy_signals = df[df['Signal'] == 1]
    if not buy_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=buy_signals['Date_Str'],
                y=buy_signals['Low'] * 0.98,
                mode='markers',
                marker=dict(symbol='triangle-up', size=12, color='#34C759', line=dict(width=1, color='black')),
                name="매수 진입 신호"
            ),
            row=1, col=1
        )
        
    # Signal == -1 : 전량 매도 마커 (파란색 또는 빨간색 역삼각형 아래쪽)
    sell_signals = df[df['Signal'] == -1]
    if not sell_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=sell_signals['Date_Str'],
                y=sell_signals['High'] * 1.02,
                mode='markers',
                marker=dict(symbol='triangle-down', size=12, color='#5856D6', line=dict(width=1, color='black')),
                name="전량 청산 신호"
            ),
            row=1, col=1
        )
        
    # Signal == -0.5 : 부분 매도 마커 (노란색 역삼각형 아래쪽)
    half_sell_signals = df[df['Signal'] == -0.5]
    if not half_sell_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=half_sell_signals['Date_Str'],
                y=half_sell_signals['High'] * 1.02,
                mode='markers',
                marker=dict(symbol='triangle-down', size=10, color='#FFCC00', line=dict(width=1, color='black')),
                name="절반 매도 신호"
            ),
            row=1, col=1
        )
        
    # 6. 거래량 차트 추가 (Row 2)
    # 종가 등락에 맞게 거래량 바 색상을 매핑합니다.
    colors_volume = np.where(df['Adj Close'].pct_change() >= 0, '#FF3B30', '#007AFF')
    colors_volume[0] = '#FF3B30' # 첫 번째 데이터 기본값
    
    fig.add_trace(
        go.Bar(
            x=df['Date_Str'], y=df['Volume'],
            marker_color=colors_volume.tolist(),
            name="거래량",
            showlegend=False
        ),
        row=2, col=1
    )
    
    # 7. RSI14 보조지표 추가 (Row 3)
    if 'RSI14' in df.columns:
        # RSI 선
        fig.add_trace(
            go.Scatter(
                x=df['Date_Str'], y=df['RSI14'],
                mode='lines',
                line=dict(width=1.5, color='#AF52DE'),
                name="RSI14"
            ),
            row=3, col=1
        )
        # 과매열선 70, 과매도선 30 기준 수평 점선
        fig.add_shape(type="line", x0=df['Date_Str'].iloc[0], y0=70, x1=df['Date_Str'].iloc[-1], y1=70,
                      line=dict(color="red", width=1, dash="dash"), row=3, col=1)
        fig.add_shape(type="line", x0=df['Date_Str'].iloc[0], y0=30, x1=df['Date_Str'].iloc[-1], y1=30,
                      line=dict(color="green", width=1, dash="dash"), row=3, col=1)
        # 50선 기준선
        fig.add_shape(type="line", x0=df['Date_Str'].iloc[0], y0=50, x1=df['Date_Str'].iloc[-1], y1=50,
                      line=dict(color="gray", width=0.5, dash="dash"), row=3, col=1)
                      
    # 레이아웃 꾸미기 (어두운 세련된 테마 적용 및 차트 최적화)
    fig.update_layout(
        title=f"<b>{ticker_name} 기술적 분석 차트</b>",
        title_font_size=18,
        height=700,
        margin=dict(l=30, r=30, t=50, b=30),
        xaxis_rangeslider_visible=False, # 하단 기본 슬라이더 숨김 (RSI 공유 목적)
        template='plotly_white', # 깔끔한 흰색 템플릿 사용
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # 축 포맷팅
    fig.update_yaxes(title_text="가격", row=1, col=1, tickformat=",d")
    fig.update_yaxes(title_text="거래량", row=2, col=1, tickformat=",d")
    fig.update_yaxes(title_text="RSI14", row=3, col=1, range=[0, 100])
    fig.update_xaxes(type='category', row=3, col=1, nbinsx=15) # x축 날짜 라벨 겹침 방지
    
    return fig
