# -*- coding: utf-8 -*-
"""
data_loader.py - 주식 데이터 수집 및 캐싱 모듈
미국장(yfinance), 한국장(pykrx / FinanceDataReader) 데이터를 효율적으로 수집하고,
로컬 SQLite 데이터베이스를 사용하여 불필요한 네트워크 호출을 방지합니다.
"""

import os
import sqlite3
import datetime
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr

# pykrx는 윈도우 환경 등에서 간혹 네트워크 오류가 날 수 있으므로 예외 처리를 철저히 합니다.
try:
    from pykrx import stock as krx
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

from src.utils import ensure_directory

# 로컬 캐시 데이터베이스 파일 경로 지정
DB_DIR = os.path.join("data", "cache")
DB_PATH = os.path.join(DB_DIR, "stock_cache.db")

def get_db_connection():
    """
    SQLite 데이터베이스 연결 객체를 생성하고 반환합니다.
    캐시 디렉토리가 없으면 먼저 생성합니다.
    """
    ensure_directory(DB_DIR)
    conn = sqlite3.connect(DB_PATH)
    return conn

def is_cache_valid(ticker, market, start_date, end_date):
    """
    로컬 캐시 데이터가 유효한지 검사합니다.
    1. 해당 티커의 테이블이 존재해야 함.
    2. 캐시된 데이터의 시작일이 요청일보다 작거나 같고, 종료일이 요청일보다 크거나 같아야 함.
    """
    table_name = f"{market}_{ticker}".replace("^", "INDEX_") # 지수 기호(^SPX 등) 에러 방지
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 테이블 존재 여부 확인
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            conn.close()
            return False
        
        # 캐시 데이터의 날짜 범위 확인
        query = f"SELECT MIN(Date), MAX(Date) FROM {table_name}"
        cursor.execute(query)
        min_date_str, max_date_str = cursor.fetchone()
        conn.close()
        
        if min_date_str and max_date_str:
            # 문자열 날짜를 datetime.date 객체로 변환
            min_date = pd.to_datetime(min_date_str).date()
            max_date = pd.to_datetime(max_date_str).date()
            
            req_start = pd.to_datetime(start_date).date()
            req_end = pd.to_datetime(end_date).date()
            
            # 오늘 날짜
            today = datetime.date.today()
            # 만약 요청한 종료일이 오늘이나 미래라면, 캐시의 마지막 날짜가 어제(영업일 감안) 또는 오늘이어야 함
            if req_end >= today:
                # 최근 영업일 갱신을 확인하기 위해, 캐시의 마지막 데이터가 오늘 혹은 어제 이상인지 체크
                # 주말인 경우 금요일 데이터가 마지막이므로 3일 이내인지 체크하는 것이 일반적
                days_diff = (today - max_date).days
                if days_diff <= 3 and min_date <= req_start:
                    return True
                else:
                    return False
            
            # 과거 특정 기간을 요청한 경우 캐시 영역에 모두 포함되는지 확인
            return min_date <= req_start and max_date >= req_end
            
    except Exception as e:
        print(f"[캐시 확인 오류] {ticker}: {e}")
        if conn:
            conn.close()
        return False
    
    return False

def load_from_cache(ticker, market):
    """
    로컬 SQLite 캐시 데이터베이스에서 종목 데이터를 불러옵니다.
    """
    table_name = f"{market}_{ticker}".replace("^", "INDEX_")
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        
        # Date 컬럼을 datetime 형식으로 변환하고 인덱스로 설정
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df.sort_index(inplace=True)
        return df
    except Exception as e:
        print(f"[캐시 로드 실패] {ticker}: {e}")
        conn.close()
        return None

def save_to_cache(ticker, market, df):
    """
    수집한 데이터를 로컬 SQLite 캐시에 저장(또는 덮어쓰기)합니다.
    """
    if df is None or df.empty:
        return
    
    table_name = f"{market}_{ticker}".replace("^", "INDEX_")
    conn = get_db_connection()
    try:
        # 데이터프레임 복사 후 인덱스를 컬럼으로 리셋하여 저장
        df_to_save = df.copy()
        df_to_save.reset_index(inplace=True)
        
        # SQLite는 datetime 타입을 텍스트 형식으로 저장하므로 문자열로 변경
        df_to_save['Date'] = df_to_save['Date'].dt.strftime('%Y-%m-%d')
        
        # 테이블이 있으면 기존 데이터를 지우고 새로 입력(replace)
        df_to_save.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.commit()
        print(f"[캐시 저장 성공] {market}_{ticker} ({len(df)}행)")
    except Exception as e:
        print(f"[캐시 저장 실패] {ticker}: {e}")
    finally:
        conn.close()

def clear_cache():
    """
    로컬 캐시 데이터베이스를 삭제하여 모든 데이터를 초기화합니다.
    """
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[알림] 캐시 데이터베이스가 성공적으로 삭제되었습니다.")
            return True
        except Exception as e:
            print(f"[캐시 초기화 실패] {e}")
            return False
    return True

def fetch_us_data(ticker, start_date, end_date):
    """
    yfinance를 사용하여 미국 주식 데이터를 수집합니다.
    """
    try:
        # yfinance 다운로드 실행
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty:
            return None
        
        # yfinance v0.2.x 이상에서는 MultiIndex로 리턴될 때가 있어 단일 인덱스로 정리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 열 이름을 표준화 (Open, High, Low, Close, Adj Close, Volume)
        # 만약 Adj Close가 없으면 Close를 사용
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            if col not in df.columns:
                print(f"[에러] 필수 컬럼 {col}이(가) 다운로드 데이터에 존재하지 않습니다.")
                return None
        
        if 'Adj Close' not in df.columns:
            df['Adj Close'] = df['Close']
            
        # 필요한 컬럼만 추출하여 정렬
        df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
        df.index.name = 'Date'
        return df
    except Exception as e:
        print(f"[미국 데이터 다운로드 에러] {ticker}: {e}")
        return None

def fetch_kr_data(ticker, start_date, end_date):
    """
    한국 주식 데이터를 수집합니다. pykrx를 우선 사용하며, 실패 시 FinanceDataReader로 폴백합니다.
    """
    # 1. pykrx를 통한 다운로드 시도
    if PYKRX_AVAILABLE:
        try:
            # pykrx는 날짜 포맷을 'YYYYMMDD'로 요구함
            start_str = pd.to_datetime(start_date).strftime('%Y%m%d')
            end_str = pd.to_datetime(end_date).strftime('%Y%m%d')
            
            # pykrx로 주식 일자별 OHLCV 가져오기
            df = krx.get_market_ohlcv_by_date(start_str, end_str, ticker)
            if df is not None and not df.empty:
                # pykrx의 컬럼명: 시가, 고가, 저가, 종가, 거래량
                df = df.rename(columns={
                    '시가': 'Open',
                    '고가': 'High',
                    '저가': 'Low',
                    '종가': 'Close',
                    '거래량': 'Volume'
                })
                # 한국 주식은 배당이나 분할 등이 이미 수정종가로 반영되어 나오는 경우가 많음. 
                # pykrx는 기본 수정주가를 반영하여 종가를 제공합니다.
                df['Adj Close'] = df['Close']
                df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
                df.index.name = 'Date'
                # 인덱스의 타입이 datetime인지 확인
                df.index = pd.to_datetime(df.index)
                return df
        except Exception as e:
            print(f"[pykrx 다운로드 실패, FDR로 전환] {ticker}: {e}")
            
    # 2. FinanceDataReader를 통한 다운로드 (폴백 또는 pykrx 미설치 시)
    try:
        # FDR은 날짜 포맷 'YYYY-MM-DD'
        df = fdr.DataReader(ticker, start_date, end_date)
        if df is not None and not df.empty:
            df = df.rename(columns={
                'Open': 'Open',
                'High': 'High',
                'Low': 'Low',
                'Close': 'Close',
                'Volume': 'Volume'
            })
            if 'Adj Close' not in df.columns:
                df['Adj Close'] = df['Close']
            df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
            df.index.name = 'Date'
            df.index = pd.to_datetime(df.index)
            return df
    except Exception as e:
        print(f"[FinanceDataReader 다운로드 에러] {ticker}: {e}")
        
    return None

def get_stock_data(ticker, market="US", start_date="2018-01-01", end_date=None, force_refresh=False):
    """
    종목 데이터를 가져오는 통합 메인 함수입니다.
    캐시 유효성을 체크하고, 필요 시 네트워크를 통해 신규 데이터를 받아와 캐싱합니다.
    """
    if end_date is None:
        end_date = datetime.date.today().strftime('%Y-%m-%d')
        
    # 1. 캐시 강제 갱신이 아니고 캐시가 유효하다면 캐시에서 즉시 반환
    if not force_refresh and is_cache_valid(ticker, market, start_date, end_date):
        print(f"[캐시 히트] {market}_{ticker} 데이터를 로컬 데이터베이스에서 로드합니다.")
        df = load_from_cache(ticker, market)
        if df is not None and not df.empty:
            # 캐시 데이터 중 사용자가 요청한 날짜 범위만 필터링하여 반환
            return df.loc[start_date:end_date]
            
    # 2. 캐시가 없거나 무효하다면 새로 다운로드 실행
    print(f"[캐시 미스/갱신] {market}_{ticker} 데이터를 인터넷에서 수집합니다...")
    if market == "US":
        df = fetch_us_data(ticker, start_date, end_date)
    elif market == "KR":
        df = fetch_kr_data(ticker, start_date, end_date)
    else:
        raise ValueError(f"지원하지 않는 시장 유형입니다: {market}")
        
    if df is not None and not df.empty:
        # 다운로드 성공 시 캐시에 저장
        save_to_cache(ticker, market, df)
        return df.loc[start_date:end_date]
    else:
        # 다운로드 실패 시 캐시에 예전 데이터라도 있는지 시도해서 반환
        print(f"[경고] {ticker} 데이터 다운로드 실패. 캐시에서 임시로 데이터를 조회합니다.")
        df_cached = load_from_cache(ticker, market)
        if df_cached is not None and not df_cached.empty:
            return df_cached.loc[start_date:end_date]
        return None

def get_market_status():
    """
    미국 지수(SPY, QQQ) 및 한국 지수(KOSPI, KOSDAQ)를 분석하여
    시장이 과열/하락장(Risk-Off)인지 상승장(Risk-On)인지 분석해 반환합니다.
    - 미국장: SPY > MA200 이면 SPY Risk-On, QQQ > MA200 이면 QQQ Risk-On (둘 다 오프면 전체 Risk-Off)
    - 한국장: KOSPI > MA120 이면 KOSPI Risk-On, KOSDAQ > MA120 이면 KOSDAQ Risk-On (둘 다 오프면 전체 Risk-Off)
    """
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    status = {
        "US_SPY_Risk": True,
        "US_QQQ_Risk": True,
        "US_Overall": True,
        "KR_KOSPI_Risk": True,
        "KR_KOSDAQ_Risk": True,
        "KR_Overall": True,
        "SPY_Close": 0.0, "SPY_MA200": 0.0,
        "QQQ_Close": 0.0, "QQQ_MA200": 0.0,
        "KOSPI_Close": 0.0, "KOSPI_MA120": 0.0,
        "KOSDAQ_Close": 0.0, "KOSDAQ_MA120": 0.0
    }
    
    # 1. 미국 시장 지수 상태 계산
    try:
        spy_df = get_stock_data("SPY", "US", start_date, end_date)
        if spy_df is not None and not spy_df.empty:
            spy_df['MA200'] = spy_df['Adj Close'].rolling(window=200).mean()
            last_spy = spy_df.iloc[-1]
            status["SPY_Close"] = round(last_spy['Adj Close'], 2)
            status["SPY_MA200"] = round(last_spy['MA200'], 2)
            status["US_SPY_Risk"] = last_spy['Adj Close'] > last_spy['MA200']
            
        qqq_df = get_stock_data("QQQ", "US", start_date, end_date)
        if qqq_df is not None and not qqq_df.empty:
            qqq_df['MA200'] = qqq_df['Adj Close'].rolling(window=200).mean()
            last_qqq = qqq_df.iloc[-1]
            status["QQQ_Close"] = round(last_qqq['Adj Close'], 2)
            status["QQQ_MA200"] = round(last_qqq['MA200'], 2)
            status["US_QQQ_Risk"] = last_qqq['Adj Close'] > last_qqq['MA200']
            
        status["US_Overall"] = status["US_SPY_Risk"] or status["US_QQQ_Risk"]
    except Exception as e:
        print(f"[미국 지수 분석 실패] {e}")
        
    # 2. 한국 시장 지수 상태 계산
    try:
        # FDR은 KS11, KQ11 기호 사용
        kospi_df = fdr.DataReader("KS11", start_date, end_date)
        if kospi_df is not None and not kospi_df.empty:
            kospi_df['MA120'] = kospi_df['Close'].rolling(window=120).mean()
            last_kospi = kospi_df.iloc[-1]
            status["KOSPI_Close"] = round(last_kospi['Close'], 2)
            status["KOSPI_MA120"] = round(last_kospi['MA120'], 2)
            status["KR_KOSPI_Risk"] = last_kospi['Close'] > last_kospi['MA120']
            
        kosdaq_df = fdr.DataReader("KQ11", start_date, end_date)
        if kosdaq_df is not None and not kosdaq_df.empty:
            kosdaq_df['MA120'] = kosdaq_df['Close'].rolling(window=120).mean()
            last_kosdaq = kosdaq_df.iloc[-1]
            status["KOSDAQ_Close"] = round(last_kosdaq['Close'], 2)
            status["KOSDAQ_MA120"] = round(last_kosdaq['MA120'], 2)
            status["KR_KOSDAQ_Risk"] = last_kosdaq['Close'] > last_kosdaq['MA120']
            
        status["KR_Overall"] = status["KR_KOSPI_Risk"] or status["KR_KOSDAQ_Risk"]
    except Exception as e:
        print(f"[한국 지수 분석 실패] {e}")
        
    return status

