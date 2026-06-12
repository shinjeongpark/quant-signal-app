# -*- coding: utf-8 -*-
"""
scanner.py - GitHub Actions에서 2시간마다 주기적 구동되는 핵심 퀀트 스캐너 엔진
미국(S&P500, NASDAQ100) 및 한국(KOSPI200, KOSDAQ150) 전 종목을 크롤링하여
시장 필터 점검, Minervini RS 점수 산정, VCP 수축 조건(거래량 동시 감소 및 97% 상단), 
A형 눌림 판정, 셋업 등급 부여를 거쳐 Supabase PostgreSQL에 동기화합니다.
"""

import os
import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
from supabase import create_client
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Supabase 접속을 위한 환경 변수 확인
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[경고] Supabase 환경변수(URL, KEY)가 설정되지 않았습니다. 로컬 테스트 모드로 구동합니다.")

def get_supabase_client():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

# ==========================================
# 1. 대상 종목 유니버스 수집 (중복 제거)
# ==========================================
def fetch_us_symbols():
    """
    S&P 500 및 NASDAQ 100의 전체 종목 리스트를 동적으로 수집하고 중복을 제거합니다.
    Wikipedia 페이지에서 크롤링하여 유통 주식 목록을 고속 확보합니다.
    """
    symbols = {}
    try:
        # S&P 500 크롤링
        sp500_table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S&P_500_companies')
        sp500_df = sp500_table[0]
        for _, row in sp500_df.iterrows():
            ticker = str(row['Symbol']).replace('.', '-')
            symbols[ticker] = {
                "name": row['Security'],
                "sector": row['GICS Sector'],
                "market": "US"
            }
            
        # NASDAQ 100 크롤링
        ndx_table = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100')
        # 보통 3~4번째 테이블에 위치
        ndx_df = ndx_table[4] if len(ndx_table) > 4 else ndx_table[3]
        ticker_col = 'Ticker' if 'Ticker' in ndx_df.columns else 'Symbol'
        name_col = 'Company' if 'Company' in ndx_df.columns else 'Name'
        for _, row in ndx_df.iterrows():
            ticker = str(row[ticker_col]).replace('.', '-')
            if ticker not in symbols:
                symbols[ticker] = {
                    "name": row[name_col],
                    "sector": "Technology/Growth",
                    "market": "US"
                }
    except Exception as e:
        print(f"[미국 심볼 수집 실패, 기본 백업 사용] {e}")
        # 크롤링 실패 시 백업용 대표 주도주
        backup = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "AMD", "NFLX", "LLY"]
        for tk in backup:
            symbols[tk] = {"name": tk, "sector": "Growth", "market": "US"}
            
    return symbols

def fetch_kr_symbols():
    """
    FinanceDataReader를 사용해 KOSPI200 및 KOSDAQ150 대표 종목 리스트를 추출하고 중복을 제거합니다.
    시가총액 상위 기준으로 필터링하여 실시간 주도주 후보를 확보합니다.
    """
    symbols = {}
    try:
        # KOSPI 종목 리스트 로드 후 시총 순 정렬 (FDR 활용)
        kospi_df = fdr.StockListing('KOSPI')
        # 시가총액 컬럼(MarCap) 기준 상위 200개 추출
        if 'MarCap' in kospi_df.columns:
            kospi_top = kospi_df.sort_values(by='MarCap', ascending=False).head(200)
        else:
            kospi_top = kospi_df.head(200)
            
        for _, row in kospi_top.iterrows():
            code = str(row['Code'])
            symbols[code] = {
                "name": row['Name'],
                "sector": row.get('Sector', 'KOSPI 우량주'),
                "market": "KR"
            }
            
        # KOSDAQ 종목 리스트 로드 후 시총 순 상위 150개 추출
        kosdaq_df = fdr.StockListing('KOSDAQ')
        if 'MarCap' in kosdaq_df.columns:
            kosdaq_top = kosdaq_df.sort_values(by='MarCap', ascending=False).head(150)
        else:
            kosdaq_top = kosdaq_df.head(150)
            
        for _, row in kosdaq_top.iterrows():
            code = str(row['Code'])
            if code not in symbols:
                symbols[code] = {
                    "name": row['Name'],
                    "sector": row.get('Sector', 'KOSDAQ 우량주'),
                    "market": "KR"
                }
    except Exception as e:
        print(f"[한국 심볼 수집 실패, 백업 사용] {e}")
        # 실패 시 예비 코드
        backup = ["005930", "000660", "005380", "207940", "005490", "247540", "086520", "028300"]
        for code in backup:
            symbols[code] = {"name": code, "sector": "KR Stock", "market": "KR"}
            
    return symbols

# ==========================================
# 2. 시장 필터 연산 (200일선 상회 여부)
# ==========================================
def calculate_market_status():
    """
    미국 지수(SPY, QQQ) 및 한국 지수(KOSPI, KOSDAQ)의 200일선 정합성을 판단합니다.
    """
    print("[시장 상태 분석 개시] 지수 데이터 수집 중...")
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=400)).strftime('%Y-%m-%d')
    
    status = {
        "spy_above_200ma": True, "qqq_above_200ma": True,
        "kospi_above_200ma": True, "kosdaq_above_200ma": True,
        "spy_close": 0.0, "qqq_close": 0.0,
        "kospi_close": 0.0, "kosdaq_close": 0.0
    }
    
    # 미국 SPY, QQQ
    try:
        spy = yf.download("SPY", start=start_date, end=today, progress=False)
        if not spy.empty:
            close = spy['Adj Close'].iloc[-1]
            ma200 = spy['Adj Close'].rolling(window=200).mean().iloc[-1]
            status["spy_close"] = float(close)
            status["spy_above_200ma"] = bool(close > ma200)
            
        qqq = yf.download("QQQ", start=start_date, end=today, progress=False)
        if not qqq.empty:
            close = qqq['Adj Close'].iloc[-1]
            ma200 = qqq['Adj Close'].rolling(window=200).mean().iloc[-1]
            status["qqq_close"] = float(close)
            status["qqq_above_200ma"] = bool(close > ma200)
    except Exception as e:
        print(f"[미국 지수 수집 실패] {e}")

    # 한국 KOSPI, KOSDAQ (FDR 및 Naver Finance 활용)
    try:
        kospi = fdr.DataReader("KS11", start_date, today)
        if not kospi.empty:
            close = kospi['Close'].iloc[-1]
            ma200 = kospi['Close'].rolling(window=200).mean().iloc[-1]
            status["kospi_close"] = float(close)
            status["kospi_above_200ma"] = bool(close > ma200)
            
        kosdaq = fdr.DataReader("KQ11", start_date, today)
        if not kosdaq.empty:
            close = kosdaq['Close'].iloc[-1]
            ma200 = kosdaq['Close'].rolling(window=200).mean().iloc[-1]
            status["kosdaq_close"] = float(close)
            status["kosdaq_above_200ma"] = bool(close > ma200)
    except Exception as e:
        print(f"[한국 지수 수집 실패] {e}")
        
    return status

# ==========================================
# 3. 주식 분석 및 셋업 추출 핵심 함수
# ==========================================
def calculate_minervini_rs_score(df, market_benchmark_df):
    """
    Minervini 스타일 다중 기간 가중 상대강도 점수를 산출합니다.
    RS = 0.40*(3M) + 0.30*(6M) + 0.20*(12M) + 0.10*(1M)
    """
    if len(df) < 252 or len(market_benchmark_df) < 252:
        return 0.0
        
    # 종가 데이터
    close_stock = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
    close_bench = market_benchmark_df['Adj Close'] if 'Adj Close' in market_benchmark_df.columns else market_benchmark_df['Close']
    
    # 벤치마크 인덱스 맞춰 정렬
    common_dates = close_stock.index.intersection(close_bench.index)
    if len(common_dates) < 200:
        return 0.0
        
    stock_p = close_stock.loc[common_dates]
    bench_p = close_bench.loc[common_dates]
    
    # 기간별 수익률 계산 (영업일 기준: 1M=21, 3M=63, 6M=126, 12M=252)
    def get_returns(prices):
        r1m = (prices.iloc[-1] / prices.iloc[-21]) - 1 if len(prices) >= 21 else 0
        r3m = (prices.iloc[-1] / prices.iloc[-63]) - 1 if len(prices) >= 63 else 0
        r6m = (prices.iloc[-1] / prices.iloc[-126]) - 1 if len(prices) >= 126 else 0
        r12m = (prices.iloc[-1] / prices.iloc[-252]) - 1 if len(prices) >= 252 else 0
        return r1m, r3m, r6m, r12m
        
    s1, s3, s6, s12 = get_returns(stock_p)
    b1, b3, b6, b12 = get_returns(bench_p)
    
    # 벤치마크 대비 초과 수익률
    diff1 = s1 - b1
    diff3 = s3 - b3
    diff6 = s6 - b6
    diff12 = s12 - b12
    
    # 가중 합산 스코어 도출
    rs_score = (0.40 * diff3) + (0.30 * diff6) + (0.20 * diff12) + (0.10 * diff1)
    return float(rs_score)

def check_setup_patterns(df):
    """
    A형(20일선 눌림목) 및 B형(VCP 수축 돌파) 셋업 조건과 보조 지표를 탐색합니다.
    """
    setup = "없음"
    stop_loss = 0.0
    metadata = {}
    
    close = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    # 지표 연산
    ma20 = close.rolling(window=20).mean().iloc[-1]
    ma200 = close.rolling(window=200).mean().iloc[-1]
    
    curr_close = close.iloc[-1]
    curr_volume = volume.iloc[-1]
    vol_ma20 = volume.rolling(window=20).mean().iloc[-1]
    
    # 1. 200일 이격도 및 52주 신고가 거리
    disparity_200 = (curr_close / ma200) * 100 if ma200 > 0 else 100.0
    high_52w = high.rolling(window=252).max().iloc[-1]
    high_52w_dist = ((high_52w - curr_close) / high_52w) * 100 if high_52w > 0 else 0.0
    
    # 2. CLV (Close Location Value) 연산
    clv_val = 0.5
    denom = high.iloc[-1] - low.iloc[-1]
    if denom > 0:
        clv_val = ((curr_close - low.iloc[-1]) - (high.iloc[-1] - curr_close)) / denom
    clv_val = float(round((clv_val + 1) / 2, 2)) # 0~1 범위로 조정
    
    # 3. ATR 기반 변동성 강도
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.rolling(window=14).mean().iloc[-1]
    
    atr_pct = (atr14 / curr_close) * 100 if curr_close > 0 else 0.0
    if atr_pct < 2.0:
        volatility_level = "낮음"
    elif atr_pct < 4.5:
        volatility_level = "보통"
    else:
        volatility_level = "높음"
        
    # --- A형 눌림 감지 ---
    # 상승추세 & 20일선 근처 조정 & 최근 거래량 감소 & 20일선 지지
    is_uptrend = curr_close > ma200
    near_ma20 = ma20 * 0.98 <= curr_close <= ma20 * 1.03
    
    # 최근 3일 거래량 감소 (3일 전 대비 혹은 순차 감소 확인)
    vol_dry_up = curr_volume < vol_ma20 and volume.iloc[-1] < volume.iloc[-2]
    above_ma20 = curr_close > ma20
    
    if is_uptrend and near_ma20 and vol_dry_up and above_ma20:
        setup = "A형 눌림"
        stop_loss = float(ma20 * 0.97) # 20일선 3% 하단 손절선
        metadata = {
            "volume_dry_up": True,
            "atr_pct": round(atr_pct, 2),
            "ma20_distance": round(((curr_close - ma20)/ma20)*100, 2)
        }
        
    # --- B형 VCP 돌파 감지 ---
    # 1) 가격 변동폭 수축 마디 확인 (최근 40일 범위를 나누어 고가/저가 수축 검사)
    # 2) 수축 마디마다 평균 거래량이 동반 감소하는지 검증
    # 3) 현재 종가가 최근 20일 고가(박스 상단)의 97% 이상 위치
    high_20 = high.rolling(window=20).max().iloc[-1]
    at_box_top = curr_close >= high_20 * 0.97
    
    # 40일 전~21일 전 마디 vs 최근 20일 마디 변동성 비교
    range_prev = (high.iloc[-40:-20].max() - low.iloc[-40:-20].min()) / close.iloc[-40:-20].mean()
    range_curr = (high.iloc[-20:].max() - low.iloc[-20:].min()) / close.iloc[-20:].mean()
    price_compression = range_curr < range_prev * 0.8 # 변동성이 이전 대비 20% 이상 압축되었는지
    
    # 거래량 수축 마디 비교
    vol_prev = volume.iloc[-40:-20].mean()
    vol_curr = volume.iloc[-20:].mean()
    vol_compression = vol_curr < vol_prev * 0.85 # 거래량이 이전 대비 15% 이상 수축되었는지
    
    if is_uptrend and price_compression and vol_compression and at_box_top:
        # A형과 겹칠 경우 VCP가 더 강력하므로 덮어씀
        setup = "B형 VCP"
        # 최근 10일 최저가를 손절선으로 지정 (박스권 하단)
        stop_loss = float(low.iloc[-10:].min())
        metadata = {
            "vcp_steps": [round(range_prev*100, 1), round(range_curr*100, 1)],
            "vol_reduction_pct": round((1 - (vol_curr/vol_prev))*100, 1),
            "box_top_dist": round(((high_20 - curr_close)/high_20)*100, 2)
        }

    # volatility_level 지표는 DB에 별도 컬럼이 없으므로 metadata JSON 내에 적재하여 프론트엔드가 참조하도록 처리
    metadata["volatility_level"] = volatility_level

    return {
        "setup_type": setup,
        "stop_loss": stop_loss,
        "clv": clv_val,
        "atr": float(atr14),
        "disparity_200": float(round(disparity_200, 2)),
        "high_52w_dist": float(round(high_52w_dist, 2)),
        "metadata": metadata
    }

# ==========================================
# 4. 스캔 메인 컨트롤러 및 등급 산정
# ==========================================
def run_scan_and_save():
    """
    미국 및 한국 유니버스의 전 종목을 수집하여 지표를 연산하고, 
    시장별 상대강도 백분위 랭크를 매겨 Supabase에 업로드합니다.
    """
    print("[스캔 시작]", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    supabase_client = get_supabase_client()
    
    # 1. 지수 정보 계산 및 저장
    m_status = calculate_market_status()
    if supabase_client:
        try:
            supabase_client.table("market_status").upsert({"id": 1, **m_status}).execute()
            print("[시장 필터 DB 저장 완료]")
        except Exception as e:
            print(f"[시장 필터 DB 저장 에러] {e}")

    # 2. 미국 및 한국 주식 목록 수집
    us_universe = fetch_us_symbols()
    kr_universe = fetch_kr_symbols()
    
    # 지수 벤치마크 미리 확보 (최근 1.5년치)
    today = datetime.date.today().strftime('%Y-%m-%d')
    start_date = (datetime.date.today() - datetime.timedelta(days=500)).strftime('%Y-%m-%d')
    
    print("벤치마크 지수 데이터 로드 중...")
    spy_df = yf.download("SPY", start=start_date, end=today, progress=False)
    qqq_df = yf.download("QQQ", start=start_date, end=today, progress=False)
    try:
        kospi_df = fdr.DataReader("KS11", start_date, today)
    except:
        kospi_df = pd.DataFrame()

    # 3. 미국 종목 분석 루프
    us_data_list = []
    print(f"미국 종목 분석 중... (대상: {len(us_universe)}개)")
    
    # API 과부하 방지를 위해 yfinance 배치 다운로드 활용
    tickers = list(us_universe.keys())
    # 50개씩 나눠 다운로드
    chunk_size = 50
    for chunk_idx in range(0, len(tickers), chunk_size):
        chunk = tickers[chunk_idx:chunk_idx+chunk_size]
        try:
            # 배치 다운로드 실행
            batch_df = yf.download(chunk, start=start_date, end=today, group_by='ticker', progress=False)
            
            for tk in chunk:
                # 개별 종목 데이터 추출
                if tk in batch_df.columns.get_level_values(0):
                    df_tk = batch_df[tk].dropna()
                else:
                    # 단일 종목으로 다운로드된 경우
                    if len(chunk) == 1:
                        df_tk = batch_df.dropna()
                    else:
                        continue
                        
                if len(df_tk) < 252:
                    continue
                
                # QQQ와 SPY 중 더 나은 RS 선택
                rs_spy = calculate_minervini_rs_score(df_tk, spy_df)
                rs_qqq = calculate_minervini_rs_score(df_tk, qqq_df)
                max_rs = max(rs_spy, rs_qqq)
                
                # 셋업 분석
                setup_res = check_setup_patterns(df_tk)
                
                # 거래량 증가율
                vol = df_tk['Volume'].iloc[-1]
                vol_ma20 = df_tk['Volume'].rolling(window=20).mean().iloc[-1]
                vol_ratio = float(vol / vol_ma20) if vol_ma20 > 0 else 1.0
                
                us_data_list.append({
                    "ticker": tk,
                    "name": us_universe[tk]["name"],
                    "market": "US",
                    "sector": us_universe[tk]["sector"],
                    "rs_score": max_rs,
                    "volume_ratio": vol_ratio,
                    **setup_res
                })
        except Exception as e:
            print(f"[미국 청크 분석 오류] {e}")

    # 4. 한국 종목 분석 루프
    kr_data_list = []
    print(f"한국 종목 분석 중... (대상: {len(kr_universe)}개)")
    
    for code in kr_universe.keys():
        try:
            # FDR 개별 주가 데이터 조회
            df_code = fdr.DataReader(code, start_date, today)
            if df_code is None or len(df_code) < 252:
                continue
                
            rs_kospi = calculate_minervini_rs_score(df_code, kospi_df)
            
            setup_res = check_setup_patterns(df_code)
            
            vol = df_code['Volume'].iloc[-1]
            vol_ma20 = df_code['Volume'].rolling(window=20).mean().iloc[-1]
            vol_ratio = float(vol / vol_ma20) if vol_ma20 > 0 else 1.0
            
            kr_data_list.append({
                "ticker": code,
                "name": kr_universe[code]["name"],
                "market": "KR",
                "sector": kr_universe[code]["sector"],
                "rs_score": rs_kospi,
                "volume_ratio": vol_ratio,
                **setup_res
            })
        except Exception as e:
            print(f"[한국 종목 분석 오류] {code}: {e}")

    # 5. 상대강도(RS Score) 백분위 랭크 계산 및 등급 부여
    # 시장(US/KR) 단위로 묶어서 백분위 점수 매겨 등급 책정
    def assign_grades_and_filter(data_list, market_filter_on):
        if not data_list:
            return []
            
        df = pd.DataFrame(data_list)
        # RS Score 기준 내림차순 랭킹 부여 (최대값 = 1.0, 최솟값 = 0.0)
        df['rs_pct'] = df['rs_score'].rank(pct=True)
        
        final_list = []
        for _, row in df.iterrows():
            pct = row['rs_pct']
            setup = row['setup_type']
            vol_ratio = row['volume_ratio']
            
            # 셋업 등급 판정
            # A+: 시장 필터 통과 & RS 상위 10% & 거래량 증가(1.5배) & 셋업 통과
            # A: RS 상위 20% & 거래량 증가(1.5배) & 셋업 통과
            # B: 셋업 충족하나 조건 일부 미달 (거래량 부족 등)
            # C: 관찰만
            grade = 'C'
            if setup != '없음':
                if market_filter_on and pct >= 0.90 and vol_ratio >= 1.5:
                    grade = 'A+'
                elif pct >= 0.80 and vol_ratio >= 1.5:
                    grade = 'A'
                else:
                    grade = 'B'
                    
            row_dict = row.to_dict()
            row_dict['grade'] = grade
            # 판정된 등급을 기반으로 최종 list 추가
            final_list.append(row_dict)
            
        return final_list

    # 시장별 독립 필터 활성화 여부
    us_filter_on = m_status["spy_above_200ma"] or m_status["qqq_above_200ma"]
    kr_filter_on = m_status["kospi_above_200ma"] or m_status["kosdaq_above_200ma"]
    
    us_graded = assign_grades_and_filter(us_data_list, us_filter_on)
    kr_graded = assign_grades_and_filter(kr_data_list, kr_filter_on)
    
    total_graded_stocks = us_graded + kr_graded
    
    # 6. Supabase DB Upsert
    if supabase_client and total_graded_stocks:
        print(f"Supabase로 스캔 데이터 적재 중... 총 {len(total_graded_stocks)}개 행")
        try:
            # 50개 단위로 쪼개서 업서트 전송
            for i in range(0, len(total_graded_stocks), 50):
                chunk = total_graded_stocks[i:i+50]
                # pandas dataframe의 float64 등 특수 타입을 네이티브 파이썬 타입으로 정돈
                clean_chunk = []
                for item in chunk:
                    clean_item = {}
                    for k, v in item.items():
                        if k == 'rs_pct':
                            continue # DB 테이블에 없는 임시 계산열 무시
                        if isinstance(v, (np.integer, np.int64)):
                            clean_item[k] = int(v)
                        elif isinstance(v, (np.floating, np.float64)):
                            clean_item[k] = float(v) if not np.isnan(v) else None
                        else:
                            clean_item[k] = v
                    clean_chunk.append(clean_item)
                    
                supabase_client.table("scanned_stocks").upsert(clean_chunk).execute()
            print("[스캐너 DB 동기화 완료]")
        except Exception as e:
            print(f"[Supabase 업서트 에러] {e}")
    else:
        # 데이터 출력 디버깅
        print(f"분석 완료 종목수: {len(total_graded_stocks)}")

if __name__ == "__main__":
    run_scan_and_save()
