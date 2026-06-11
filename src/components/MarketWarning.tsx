// src/components/MarketWarning.tsx
// 미국 및 한국 주식 시장의 200일선 상회 상태(Market Filter)를 각각 체크하여,
// Risk-Off 상태일 시 화면 최상단에 과매매 방지용 주의 배너를 독립적으로 노출하는 컴포넌트입니다.

import React from 'react';

interface MarketWarningProps {
  spyAbove200: boolean;
  qqqAbove200: boolean;
  kospiAbove200: boolean;
  kosdaqAbove200: boolean;
}

export default function MarketWarning({
  spyAbove200,
  qqqAbove200,
  kospiAbove200,
  kosdaqAbove200,
}: MarketWarningProps) {
  // 미국 통합 필터 (SPY와 QQQ 둘 다 200일선 밑이면 Risk-Off)
  const isUsRiskOff = !spyAbove200 && !qqqAbove200;
  // 한국 통합 필터 (KOSPI와 KOSDAQ 둘 다 200일선 밑이면 Risk-Off)
  const isKrRiskOff = !kospiAbove200 && !kosdaqAbove200;

  if (!isUsRiskOff && !isKrRiskOff) return null;

  return (
    <div className="w-full flex flex-col gap-2 mb-6">
      {isUsRiskOff && (
        <div className="bg-red-950/40 border border-red-500/50 text-red-200 px-4 py-3 rounded-lg flex items-center gap-3 animate-pulse">
          <span className="text-xl">⚠️</span>
          <div>
            <strong className="font-bold">Market Filter OFF (미국 시장 경고)</strong>
            <span className="block sm:inline text-sm text-red-300 ml-2">
              현재 미국 지수가 200일선 하단에 위치하고 있습니다. 신규 매수 성공 확률이 매우 낮은 하락 추세 구간입니다. 과매매를 방지하십시오.
            </span>
          </div>
        </div>
      )}
      
      {isKrRiskOff && (
        <div className="bg-amber-950/40 border border-amber-500/50 text-amber-200 px-4 py-3 rounded-lg flex items-center gap-3">
          <span className="text-xl">⚠️</span>
          <div>
            <strong className="font-bold">Market Filter OFF (한국 시장 경고)</strong>
            <span className="block sm:inline text-sm text-amber-300 ml-2">
              현재 한국 지수가 200일선 하단에 위치하고 있습니다. 개별 종목의 셋업이 발생하더라도 돌파 실패 가능성이 높으니 신규 진입에 각별히 유의하십시오.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
