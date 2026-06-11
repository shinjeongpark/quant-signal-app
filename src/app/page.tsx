// src/app/page.tsx
// Ultimate Leader Stock Scanner의 메인 다크모드 대시보드 페이지입니다.
// "use client" 지시어로 클라이언트 사이드 상태(선택 종목, 데이터 로딩 등)를 관리합니다.
// 4대 지수 현황판, 상위 20개 RS 히트맵, 셋업 유형별 카드 배치 및 상세 모달을 한 화면에 조립했습니다.

"use client";

import React, { useEffect, useState } from 'react';
import MarketWarning from '@/components/MarketWarning';
import StockCard, { StockData } from '@/components/StockCard';
import StockDetail from '@/components/StockDetail';

interface MarketStatus {
  spy_above_200ma: boolean;
  qqq_above_200ma: boolean;
  kospi_above_200ma: boolean;
  kosdaq_above_200ma: boolean;
  spy_close: number;
  qqq_close: number;
  kospi_close: number;
  kosdaq_close: number;
}

interface ApiResponse {
  marketStatus: MarketStatus;
  stocks: StockData[];
}

export default function DashboardPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<StockData | null>(null);

  useEffect(() => {
    // Supabase DB와 연계된 스캔 API 호출
    fetch('/api/stocks')
      .then(res => res.json())
      .then((resData: ApiResponse) => {
        setData(resData);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError("데이터 로드 중 에러가 발생했습니다.");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#131722] text-gray-300 flex flex-col justify-center items-center gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
        <p className="text-sm tracking-wider font-bold">주도주 및 시장 데이터를 동기화하는 중...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#131722] text-red-400 flex justify-center items-center font-bold">
        {error || "데이터 로드 실패"}
      </div>
    );
  }

  const { marketStatus, stocks } = data;

  // 1. 셋업 유형별 데이터 분류
  const aTypeStocks = stocks.filter(s => s.setup_type === 'A형 눌림' && s.grade !== 'C');
  const bTypeStocks = stocks.filter(s => s.setup_type === 'B형 VCP' && s.grade !== 'C');
  const overheatedStocks = stocks.filter(s => s.disparity_200 >= 160.0); // 과열 기준 이격도 160% 이상
  const topRsStocks = stocks.slice(0, 20); // 상대강도 상위 20개 (히트맵용)

  // 2. 시장별 독립적 Risk-Off 상태 판정
  const isUsMarketRiskOff = !marketStatus.spy_above_200ma && !marketStatus.qqq_above_200ma;
  const isKrMarketRiskOff = !marketStatus.kospi_above_200ma && !marketStatus.kosdaq_above_200ma;

  return (
    <main className="min-h-screen bg-[#131722] text-gray-200 p-6 md:p-10 font-sans">
      <div className="max-w-7xl mx-auto flex flex-col gap-8">
        
        {/* 타이틀 및 헤더 */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-6">
          <div>
            <h1 className="text-3xl font-black text-white tracking-tight">
              📊 ULTIMATE LEADER STOCK SCANNER
            </h1>
            <p className="text-xs text-gray-400 mt-2">
              핵심 주도주 스캔 및 기술적 A/B형 타점 분석 시스템 (Supabase + TradingView 연계)
            </p>
          </div>
          <div className="mt-4 md:mt-0 text-right text-xs text-gray-500">
            데이터 갱신 주기: 미국 4시간 | 한국 1시간 자동 동기화
          </div>
        </div>

        {/* 1. 최상단 독립 시장 경고 배너 */}
        <MarketWarning 
          spyAbove200={marketStatus.spy_above_200ma} 
          qqqAbove200={marketStatus.qqq_above_200ma} 
          kospiAbove200={marketStatus.kospi_above_200ma} 
          kosdaqAbove200={marketStatus.kosdaq_above_200ma} 
        />

        {/* 2. 4대 지수 시장 상태 패널 */}
        <section>
          <h2 className="text-lg font-bold text-white mb-4">🌐 글로벌 4대 지수 현황 패널</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* SPY */}
            <div className="bg-[#1c2030] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <span className="text-xs text-gray-400">🇺🇸 S&P 500 (SPY)</span>
              <div className="flex justify-between items-baseline mt-2">
                <span className="text-lg font-bold text-white">${marketStatus.spy_close}</span>
                <span className={`text-xs font-bold ${marketStatus.spy_above_200ma ? 'text-green-400' : 'text-red-400'}`}>
                  {marketStatus.spy_above_200ma ? 'Risk-On (200선↑)' : 'Risk-Off (200선↓)'}
                </span>
              </div>
            </div>
            {/* QQQ */}
            <div className="bg-[#1c2030] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <span className="text-xs text-gray-400">🇺🇸 NASDAQ 100 (QQQ)</span>
              <div className="flex justify-between items-baseline mt-2">
                <span className="text-lg font-bold text-white">${marketStatus.qqq_close}</span>
                <span className={`text-xs font-bold ${marketStatus.qqq_above_200ma ? 'text-green-400' : 'text-red-400'}`}>
                  {marketStatus.qqq_above_200ma ? 'Risk-On (200선↑)' : 'Risk-Off (200선↓)'}
                </span>
              </div>
            </div>
            {/* KOSPI */}
            <div className="bg-[#1c2030] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <span className="text-xs text-gray-400">🇰🇷 KOSPI (^KS11)</span>
              <div className="flex justify-between items-baseline mt-2">
                <span className="text-lg font-bold text-white">{marketStatus.kospi_close}</span>
                <span className={`text-xs font-bold ${marketStatus.kospi_above_200ma ? 'text-green-400' : 'text-red-400'}`}>
                  {marketStatus.kospi_above_200ma ? 'Risk-On (200선↑)' : 'Risk-Off (200선↓)'}
                </span>
              </div>
            </div>
            {/* KOSDAQ */}
            <div className="bg-[#1c2030] p-4 rounded-xl border border-gray-800 flex flex-col justify-between">
              <span className="text-xs text-gray-400">🇰🇷 KOSDAQ (^KQ11)</span>
              <div className="flex justify-between items-baseline mt-2">
                <span className="text-lg font-bold text-white">{marketStatus.kosdaq_close}</span>
                <span className={`text-xs font-bold ${marketStatus.kosdaq_above_200ma ? 'text-green-400' : 'text-red-400'}`}>
                  {marketStatus.kosdaq_above_200ma ? 'Risk-On (200선↑)' : 'Risk-Off (200선↓)'}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* 3. RS 상대강도 히트맵 */}
        <section>
          <h2 className="text-lg font-bold text-white mb-4">🔥 상대강도(RS) 주도주 히트맵 (상위 20개)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-10 gap-3">
            {topRsStocks.map((stock) => {
              const rsPctVal = stock.rs_score * 100;
              const isPositive = rsPctVal >= 0;
              return (
                <div 
                  key={stock.ticker}
                  onClick={() => setSelectedStock(stock)}
                  className="bg-[#1c2030] border border-gray-800/80 rounded-lg p-3 hover:bg-gray-800 transition-all cursor-pointer text-center flex flex-col justify-center h-[75px]"
                >
                  <span className="text-xs font-bold text-white">{stock.ticker}</span>
                  <span className={`text-[11px] mt-1 font-semibold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                    {isPositive ? '▲' : '▼'} {Math.abs(rsPctVal).toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* 4대 지수 외 셋업 그리드 배치 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* 오늘의 A형 눌림목 (왼쪽 2/3 영역 배치) */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            <div>
              <h2 className="text-lg font-bold text-white mb-4">🟢 오늘의 A형 셋업 (20일선 눌림)</h2>
              {aTypeStocks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {aTypeStocks.map((stock) => (
                    <StockCard 
                      key={stock.ticker}
                      stock={stock}
                      isMarketRiskOff={stock.market === 'US' ? isUsMarketRiskOff : isKrMarketRiskOff}
                      onClick={() => setSelectedStock(stock)}
                    />
                  ))}
                </div>
              ) : (
                <div className="bg-[#1c2030] border border-gray-800 text-gray-500 rounded-xl p-8 text-center text-sm font-semibold">
                  오늘 감지된 A형 눌림목 셋업 종목이 없습니다.
                </div>
              )}
            </div>

            {/* 오늘의 B형 VCP 돌파 */}
            <div>
              <h2 className="text-lg font-bold text-white mb-4">🚀 오늘의 B형 셋업 (VCP 수축 돌파)</h2>
              {bTypeStocks.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {bTypeStocks.map((stock) => (
                    <StockCard 
                      key={stock.ticker}
                      stock={stock}
                      isMarketRiskOff={stock.market === 'US' ? isUsMarketRiskOff : isKrMarketRiskOff}
                      onClick={() => setSelectedStock(stock)}
                    />
                  ))}
                </div>
              ) : (
                <div className="bg-[#1c2030] border border-gray-800 text-gray-500 rounded-xl p-8 text-center text-sm font-semibold">
                  오늘 감지된 B형 VCP 수축 돌파 셋업 종목이 없습니다.
                </div>
              )}
            </div>
          </div>

          {/* 우측 과열 종목 목록 (오른쪽 1/3 배치) */}
          <div className="bg-[#1c2030] p-6 rounded-xl border border-gray-800 self-start">
            <h2 className="text-lg font-bold text-red-400 mb-4 flex items-center gap-2">
              🚨 과열 주의보 (이격도 160%↑)
            </h2>
            {overheatedStocks.length > 0 ? (
              <div className="space-y-3.5">
                {overheatedStocks.map((stock) => (
                  <div 
                    key={stock.ticker}
                    onClick={() => setSelectedStock(stock)}
                    className="flex justify-between items-center bg-[#131722] hover:bg-gray-800 p-3 rounded-lg border border-gray-800/60 cursor-pointer transition-all"
                  >
                    <div>
                      <span className="font-bold text-white text-sm tracking-wider block">{stock.ticker}</span>
                      <span className="text-[10px] text-gray-500">{stock.name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-red-400 text-xs font-bold block">{stock.disparity_200}%</span>
                      <span className="text-[9px] text-gray-600">200일선 이격</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 text-center py-6 font-semibold">
                현재 200일선 이격도 160%를 초과하는 극단적 과열 종목이 없습니다.
              </p>
            )}
          </div>

        </div>

      </div>

      {/* 종목 상세 정보 모달 팝업 */}
      {selectedStock && (
        <StockDetail 
          stock={selectedStock}
          spyAbove200={marketStatus.spy_above_200ma}
          qqqAbove200={marketStatus.qqq_above_200ma}
          kospiAbove200={marketStatus.kospi_above_200ma}
          kosdaqAbove200={marketStatus.kosdaq_above_200ma}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </main>
  );
}
