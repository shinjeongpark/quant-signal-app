// src/components/StockCard.tsx
// 개별 종목의 핵심 기술적 상태를 가독성 높게 전달하는 미니멀 종목 카드 컴포넌트입니다.
// 종목명, 셋업 유형, RS 점수, 거래량 비율, 손절가, 등급을 노출하며, 시장 위험 시 주의 딱지를 렌더링합니다.

import React from 'react';

export interface StockData {
  ticker: string;
  name: string;
  market: string;
  sector: string;
  setup_type: string;
  rs_score: number;
  volume_ratio: number;
  stop_loss: number;
  grade: string;
  clv: number;
  atr: number;
  disparity_200: number;
  high_52w_dist: number;
  metadata: any;
  updated_at: string;
}

interface StockCardProps {
  stock: StockData;
  isMarketRiskOff: boolean; // 해당 시장의 Risk-Off 여부
  onClick: () => void; // 카드 클릭 시 상세 팝업 연동
}

export default function StockCard({ stock, isMarketRiskOff, onClick }: StockCardProps) {
  // 등급별 테두리 및 텍스트 컬러 매핑
  const gradeColors: { [key: string]: { border: string; text: string; bg: string } } = {
    'A+': { border: 'border-emerald-500', text: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    'A': { border: 'border-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/10' },
    'B': { border: 'border-amber-500', text: 'text-amber-400', bg: 'bg-amber-500/10' },
    'C': { border: 'border-gray-700', text: 'text-gray-400', bg: 'bg-gray-700/20' }
  };

  const currentColors = gradeColors[stock.grade] || gradeColors['C'];

  return (
    <div 
      onClick={onClick}
      className={`bg-[#1c2030] rounded-xl p-5 border ${currentColors.border} hover:scale-[1.02] active:scale-[0.99] transition-all cursor-pointer flex flex-col justify-between h-[210px] shadow-lg relative overflow-hidden`}
    >
      {/* 1. 시장 경고 배지 (해당 시장이 Risk-Off 인 경우에만 노출) */}
      {isMarketRiskOff && (
        <div className="absolute top-0 left-0 w-full bg-red-600/90 text-white text-[10px] font-bold text-center py-1 select-none">
          ⚠️ 시장 환경 악화 (신규 매수 주의)
        </div>
      )}

      {/* 2. 카드 헤더: 티커 & 회사명 & 등급 표시 */}
      <div className={`flex justify-between items-start ${isMarketRiskOff ? 'mt-4' : ''}`}>
        <div className="flex flex-col">
          <span className="text-xl font-bold text-white tracking-wider">{stock.ticker}</span>
          <span className="text-xs text-gray-400 truncate max-w-[150px]">{stock.name}</span>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-bold ${currentColors.bg} ${currentColors.text}`}>
          Setup {stock.grade}
        </span>
      </div>

      {/* 3. 카드 바디: 셋업 정보 */}
      <div className="my-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">셋업 유형</span>
        <span className={`text-sm font-semibold ${stock.setup_type !== '없음' ? 'text-green-400' : 'text-gray-500'}`}>
          {stock.setup_type === 'A형 눌림' && '🟢 A형 눌림'}
          {stock.setup_type === 'B형 VCP' && '🚀 B형 VCP'}
          {stock.setup_type === '없음' && '관찰 대상'}
        </span>
      </div>

      {/* 4. 카드 푸터: 핵심 기술 수치들 */}
      <div className="grid grid-cols-3 gap-2 pt-3 border-t border-gray-800/80 text-center">
        <div className="flex flex-col">
          <span className="text-[10px] text-gray-500">RS (상대강도)</span>
          <span className="text-xs font-bold text-gray-200">{(stock.rs_score * 100).toFixed(1)}%</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-gray-500">거래량 비율</span>
          <span className={`text-xs font-bold ${stock.volume_ratio >= 1.5 ? 'text-green-400' : 'text-gray-200'}`}>
            {stock.volume_ratio.toFixed(1)}x
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[10px] text-gray-500">손절가</span>
          <span className="text-xs font-bold text-red-400">
            {stock.stop_loss > 0 ? stock.stop_loss.toLocaleString() : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  );
}
