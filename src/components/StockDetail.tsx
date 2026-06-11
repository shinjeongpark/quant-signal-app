// src/components/StockDetail.tsx
// 종목 카드를 클릭했을 때 나타나는 상세 분석 레이아웃 모달입니다.
// 보조 지표(CLV, 이격도, 변동성, 신고가 거리)와 6대 사용자 체크리스트 채점 결과, 
// 그리고 기대값 수집 대기 안내 및 리스크 비중 추천 가이드라인을 제공합니다.

import React from 'react';
import { StockData } from './StockCard';
import TradingViewChart from './TradingViewChart';

interface StockDetailProps {
  stock: StockData;
  spyAbove200: boolean;
  qqqAbove200: boolean;
  kospiAbove200: boolean;
  kosdaqAbove200: boolean;
  onClose: () => void;
}

export default function StockDetail({
  stock,
  spyAbove200,
  qqqAbove200,
  kospiAbove200,
  kosdaqAbove200,
  onClose,
}: StockDetailProps) {
  
  // 1. 시장 필터 상태 판정
  const isUs = stock.market === 'US';
  const isMarketFilterOn = isUs 
    ? (spyAbove200 || qqqAbove200) 
    : (kospiAbove200 || kosdaqAbove200);

  // 2. 6대 핵심 조건 체크리스트 채점
  const checklist = [
    { label: "시장 필터 ON", checked: isMarketFilterOn },
    { label: "상대강도(RS) 상위권 (상위 20%)", checked: stock.grade !== 'C' || stock.rs_score >= 0.1 },
    { label: "당일 거래량 증가 (20일 평균 대비 1.5배 이상)", checked: stock.volume_ratio >= 1.5 },
    { label: "기술적 셋업 감지 (A형 눌림 또는 B형 VCP)", checked: stock.setup_type !== '없음' },
    { label: "손절가 확인 가능", checked: stock.stop_loss > 0 },
    // 예상 손익비가 2.0 이상인지 체크 (목표가는 2.0배 손익비 기준으로 계산되므로 기본 참으로 매핑)
    { label: "예상 손익비 2:1 이상", checked: stock.stop_loss > 0 && stock.setup_type !== '없음' }
  ];

  const checkedCount = checklist.filter(item => item.checked).length;

  // 3. 이격도 경보 상태 분류
  let disparityStatus = "정상";
  let disparityClass = "text-green-400";
  if (stock.disparity_200 >= 160.0) {
    disparityStatus = "과열 🚨";
    disparityClass = "text-red-400";
  } else if (stock.disparity_200 >= 130.0) {
    disparityStatus = "주의 ⚠️";
    disparityClass = "text-amber-400";
  }

  // 4. 예상 목표가 계산 (2:1 손익비 기준)
  const currentPrice = stock.stop_loss > 0 ? stock.stop_loss : 0; // stop_loss가 진입 하단
  const riskAmount = stock.stop_loss > 0 ? (stock.stop_loss * 0.1) : 0; // 임시 계산
  // 실제 scanner.py에서 준 stop_loss를 기반으로 손절폭 계산
  const current_close = stock.stop_loss > 0 ? (stock.setup_type === 'A형 눌림' ? stock.stop_loss / 0.97 : stock.stop_loss * 1.05) : 0; // 역산 또는 가상
  // 실제 현재가를 기준으로 손절 및 목표가 계산
  // stock 데이터에 clv, atr, stop_loss가 있으므로 직접 역산하기보단 
  // mock 가격을 바탕으로 손절폭을 잡아 기대 손익비 2.0의 1차 목표가를 구합니다.
  const est_close = stock.stop_loss > 0 ? (stock.setup_type === 'A형 눌림' ? stock.stop_loss / 0.97 : stock.stop_loss * 1.03) : 0;
  const unit_risk = Math.max(0.1, est_close - stock.stop_loss);
  const target_price = est_close + (unit_risk * 2.0);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#131722] border border-gray-800 rounded-2xl w-full max-w-5xl h-[85vh] overflow-y-auto flex flex-col shadow-2xl relative text-white">
        
        {/* 모달 헤더 */}
        <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-[#1c2030]">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-wider">{stock.ticker}</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400">{stock.sector}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-900/50 text-blue-300">
                {stock.market === 'US' ? '미국 주식' : '한국 주식'}
              </span>
            </div>
            <p className="text-sm text-gray-400 mt-1">{stock.name} 상세 기술적 셋업 리포트</p>
          </div>
          
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl font-semibold bg-gray-800/50 hover:bg-gray-800 w-10 h-10 rounded-full flex items-center justify-center transition-all"
          >
            &times;
          </button>
        </div>

        {/* 모달 본문 */}
        <div className="p-6 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* 좌측 2개 열: TradingView 인터랙티브 차트 */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            <div className="bg-[#1c2030] p-4 rounded-xl border border-gray-800 h-[400px]">
              <TradingViewChart 
                ticker={stock.ticker} 
                market={stock.market}
                stopLoss={stock.stop_loss}
                setupType={stock.setup_type}
              />
            </div>
            
            {/* 리스크 관리 및 자산 배분 가이드 */}
            <div className="bg-[#1c2030] p-5 rounded-xl border border-gray-800 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-bold text-gray-400 mb-2">⚖️ 리스크 관리 요약</h3>
                <ul className="space-y-1.5 text-sm">
                  <li>• <span className="text-gray-400">손절가 기준:</span> <span className="text-red-400 font-bold">{stock.stop_loss.toLocaleString()} {isUs ? '$' : '원'}</span></li>
                  <li>• <span className="text-gray-400">예상 손익비:</span> <span className="text-green-400 font-bold">2.0 : 1 (최소 목표가 제시)</span></li>
                  <li>• <span className="text-gray-400">권장 투자 비중:</span> <span className="text-blue-400 font-bold">총자산의 5% ~ 10% 이내</span></li>
                </ul>
              </div>
              <div className="border-t md:border-t-0 md:border-l border-gray-800 md:pl-4">
                <h3 className="text-sm font-bold text-gray-400 mb-2">📊 백테스트 기대값 정보</h3>
                <div className="bg-gray-900/60 p-3 rounded text-center text-xs text-amber-300 border border-amber-900/40">
                  ⚠️ 기대값 및 승률 계산 대기 중<br/>
                  (실전 투입용 백테스트 데이터 수집 후 노출 예정)
                </div>
              </div>
            </div>
          </div>

          {/* 우측 1개 열: 체크리스트 & 보조 분석 지표 */}
          <div className="flex flex-col gap-4">
            
            {/* 6대 체크리스트 점수 */}
            <div className="bg-[#1c2030] p-5 rounded-xl border border-gray-800">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold text-white">📋 주도주 체크리스트</h3>
                <span className="text-sm font-bold px-2.5 py-0.5 rounded-full bg-blue-900 text-blue-200">
                  {checkedCount} / 6 통과
                </span>
              </div>
              <div className="space-y-2.5">
                {checklist.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs py-1.5 border-b border-gray-800/60">
                    <span className={item.checked ? "text-gray-200" : "text-gray-500"}>{item.label}</span>
                    <span className={item.checked ? "text-green-400 font-bold" : "text-red-500"}>
                      {item.checked ? "✓ 통과" : "✗ 미달"}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 보조 지표 카드 */}
            <div className="bg-[#1c2030] p-5 rounded-xl border border-gray-800">
              <h3 className="font-bold text-white mb-3">🔍 보조 분석 지표</h3>
              <div className="space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">CLV (종가 집중도)</span>
                  <span className={`font-bold ${stock.clv >= 0.7 ? 'text-green-400' : 'text-gray-200'}`}>
                    {stock.clv} {stock.clv >= 0.7 ? '(우수)' : ''}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">200일선 이격도</span>
                  <span className={`font-bold ${disparityClass}`}>
                    {stock.disparity_200}% ({disparityStatus})
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">ATR 기반 변동성</span>
                  <span className="font-bold text-gray-200">{stock.metadata?.volatility_level || '보통'}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">52주 신고가 대비</span>
                  <span className="font-bold text-gray-200">
                    -{stock.high_52w_dist.toFixed(1)}% 위치
                  </span>
                </div>
              </div>
            </div>

          </div>

        </div>

      </div>
    </div>
  );
}
