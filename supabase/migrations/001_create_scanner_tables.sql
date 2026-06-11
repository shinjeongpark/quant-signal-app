-- supabase/migrations/001_create_scanner_tables.sql
-- Ultimate Leader Stock Scanner 서비스에서 사용하는 데이터 테이블 구조 정의 스키마입니다.
-- 중복 저장을 방지하는 고유 제약 및 향후 지표 확장을 위한 JSONB 컬럼을 탑재하고 있습니다.

-- 1. 개별 종목 분석 및 스캔 결과 저장 테이블
CREATE TABLE IF NOT EXISTS scanned_stocks (
    ticker VARCHAR(50) PRIMARY KEY,                                      -- 티커 또는 종목코드 (기본키로 자동 중복 제거)
    name VARCHAR(255) NOT NULL,                                          -- 종목명
    market VARCHAR(50) NOT NULL,                                         -- 시장 구분 ('US' / 'KR')
    sector VARCHAR(255),                                                 -- 업종/섹터
    setup_type VARCHAR(100) NOT NULL,                                    -- 검출된 셋업 유형 ('A형 눌림', 'B형 VCP', '없음')
    rs_score NUMERIC(10, 4) NOT NULL,                                    -- Minervini 스타일 다중 기간 상대강도 점수
    volume_ratio NUMERIC(10, 4) NOT NULL,                                -- 오늘 거래량 / 20일 평균 거래량 비율
    stop_loss NUMERIC(20, 2),                                            -- 권장 손절 기준 가격
    grade VARCHAR(10) NOT NULL,                                          -- 셋업 최종 등급 ('A+', 'A', 'B', 'C')
    clv NUMERIC(10, 4),                                                  -- Close Location Value (0~1 범위 수치)
    atr NUMERIC(20, 2),                                                  -- ATR14 변동폭 값
    disparity_200 NUMERIC(10, 4),                                        -- 200일 이평선 이격도 (%)
    high_52w_dist NUMERIC(10, 4),                                        -- 52주 최고가 대비 하락 거리 (%)
    metadata JSONB,                                                      -- 추가 보조 분석 데이터 및 VCP 세부 마디 저장용 유연한 JSON 컬럼
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) -- 최종 동기화 시간
);

-- 2. 4대 주요 벤치마크 지수의 200일 이평선 상태 및 종가 기록 테이블
CREATE TABLE IF NOT EXISTS market_status (
    id INT PRIMARY KEY DEFAULT 1,                                        -- 단일 레코드만 유지하기 위해 ID를 1로 강제 제한
    spy_above_200ma BOOLEAN DEFAULT TRUE,                               -- SPY가 200일선 위에 위치하는지 여부
    qqq_above_200ma BOOLEAN DEFAULT TRUE,                               -- QQQ가 200일선 위에 위치하는지 여부
    kospi_above_200ma BOOLEAN DEFAULT TRUE,                             -- KOSPI가 200일선 위에 위치하는지 여부
    kosdaq_above_200ma BOOLEAN DEFAULT TRUE,                            -- KOSDAQ이 200일선 위에 위치하는지 여부
    spy_close NUMERIC(10, 2),                                            -- SPY 최신 종가
    qqq_close NUMERIC(10, 2),                                            -- QQQ 최신 종가
    kospi_close NUMERIC(10, 2),                                          -- KOSPI 최신 종가
    kosdaq_close NUMERIC(10, 2),                                         -- KOSDAQ 최신 종가
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    CONSTRAINT singleton_row CHECK (id = 1)                              -- 한 행만 유지하도록 체크 조항 추가
);
