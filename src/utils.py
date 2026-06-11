# -*- coding: utf-8 -*-
"""
utils.py - 공통 유틸리티 및 종목 유니버스 정의 모듈
이 모듈은 미국 주식 및 한국 주식의 기본 유니버스 데이터를 정의하고,
종목명 검색 및 데이터 로딩 중 발생할 수 있는 공통 헬퍼 기능을 제공합니다.
초보자도 쉽게 이해할 수 있도록 한글 주석을 상세히 작성했습니다.
"""

import os
import pandas as pd

# 1. 미국 주식 시장 기본 유니버스 정의
# 대표 ETF 및 시가총액 상위 대형주 티커(Ticker) 목록입니다.
US_UNIVERSES = {
    "기본 ETF": {
        "SPY": "S&P 500 ETF (시장 대표)",
        "QQQ": "Nasdaq 100 ETF (기술주 중심)",
        "IWM": "Russell 2000 ETF (소형주 중심)",
        "DIA": "Dow Jones ETF (우량주 중심)",
        "XLK": "Technology Sector ETF (기술)",
        "XLF": "Financial Sector ETF (금융)",
        "XLE": "Energy Sector ETF (에너지)",
        "XLV": "Healthcare Sector ETF (헬스케어)",
        "XLY": "Consumer Discretionary ETF (소비재)"
    },
    "기본 대형주": {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "NVDA": "NVIDIA Corporation",
        "AMZN": "Amazon.com Inc.",
        "GOOGL": "Alphabet Inc. (Class A)",
        "META": "Meta Platforms Inc.",
        "TSLA": "Tesla Inc.",
        "AVGO": "Broadcom Inc.",
        "AMD": "Advanced Micro Devices",
        "NFLX": "Netflix Inc."
    }
}

# 2. 한국 주식 시장 기본 유니버스 정의
# 코스피(KOSPI) 및 코스닥(KOSDAQ)의 대표적인 대형 우량주들입니다.
# pykrx나 FinanceDataReader를 통해 실시간으로 전체 목록을 가져올 수도 있지만,
# 빠른 선택을 돕기 위해 기본 목록을 하드코딩해 둡니다.
KR_UNIVERSES = {
    "KOSPI 주요 종목": {
        "005930": "삼성전자",
        "000660": "SK하이닉스",
        "005380": "현대차",
        "207940": "삼성바이오로직스",
        "005490": "POSCO홀딩스",
        "051910": "LG화학",
        "035420": "NAVER",
        "006400": "삼성SDI",
        "000270": "기아",
        "035720": "카카오"
    },
    "KOSDAQ 주요 종목": {
        "247540": "에코프로비엠",
        "086520": "에코프로",
        "091990": "셀트리온헬스케어",
        "066970": "엘앤에프",
        "293490": "카카오게임즈",
        "393890": "더블유게임즈",
        "214150": "클래시스",
        "035900": "JYP Ent.",
        "198440": "레인보우로보틱스",
        "028300": "HLB"
    }
}

def get_us_tickers():
    """
    미국 주식 기본 유니버스의 티커 목록을 반환합니다.
    """
    tickers = []
    for category, items in US_UNIVERSES.items():
        tickers.extend(items.keys())
    return list(set(tickers))

def get_kr_tickers():
    """
    한국 주식 기본 유니버스의 종목코드 목록을 반환합니다.
    """
    tickers = []
    for category, items in KR_UNIVERSES.items():
        tickers.extend(items.keys())
    return list(set(tickers))

def ensure_directory(path):
    """
    지정된 경로의 디렉토리가 존재하는지 확인하고, 없으면 생성합니다.
    데이터 캐시나 결과물 저장 폴더 등을 만들 때 사용합니다.
    """
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"[알림] 디렉토리가 생성되었습니다: {path}")

def format_percentage(value):
    """
    숫자를 퍼센트 형식(%)의 문자열로 변환합니다. 예: 0.1234 -> "12.34%"
    """
    if pd.isna(value):
        return "N/A"
    return f"{value * 100:.2f}%"

def format_amount(value, currency="USD"):
    """
    금액을 읽기 쉬운 통화 형태 포맷으로 출력합니다.
    한국 원화(KRW)와 미국 달러(USD)를 구분하여 처리합니다.
    """
    if pd.isna(value):
        return "N/A"
    if currency == "KRW":
        return f"{int(value):,}원"
    return f"${value:,.2f}"
