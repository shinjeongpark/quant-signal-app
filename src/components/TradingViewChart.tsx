// src/components/TradingViewChart.tsx
// "use client" 지시어를 사용해 Next.js CSR 환경에서 차트를 렌더링합니다.
// TradingView Lightweight Charts 라이브러리를 활용해 캔들스틱, 거래량바, 20일선,
// 그리고 손절선(priceLine) 및 매수 타점 근처의 반투명 초록색 밴드 영역을 오버레이합니다.

"use client";

import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, LineStyle, IChartApi } from 'lightweight-charts';

interface TradingViewChartProps {
  ticker: string;
  market: string;
  stopLoss: number;
  setupType: string;
}

interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20?: number;
}

export default function TradingViewChart({ ticker, market, stopLoss, setupType }: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    setLoading(true);
    setError(null);

    let isMounted = true;

    // 1. 차트 캔들 데이터 fetch
    fetch(`/api/chart?ticker=${ticker}&market=${market}`)
      .then(res => {
        return res.json().then(data => {
          if (!res.ok || data.error) {
            return Promise.reject(new Error(data.error + (data.details ? ` (${data.details})` : '')));
          }
          return data;
        });
      })
      .then((data: CandleData[]) => {
        if (!isMounted) return;

        // 2. 20일 이동평균선(MA20) 계산 추가
        for (let i = 0; i < data.length; i++) {
          if (i >= 19) {
            let sum = 0;
            for (let j = 0; j < 20; j++) {
              sum += data[i - j].close;
            }
            data[i].ma20 = Number((sum / 20).toFixed(2));
          } else {
            data[i].ma20 = undefined;
          }
        }

        // 컨테이너 초기화
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = '';
        }

        // 3. TradingView 차트 생성 (다크 모드 `#131722` 베이스)
        const chart = createChart(chartContainerRef.current!, {
          layout: {
            background: { type: ColorType.Solid, color: '#131722' },
            textColor: '#d1d4dc',
          },
          grid: {
            vertLines: { color: 'rgba(42, 46, 57, 0.2)' },
            horzLines: { color: 'rgba(42, 46, 57, 0.2)' },
          },
          rightPriceScale: {
            borderColor: 'rgba(197, 203, 206, 0.3)',
          },
          timeScale: {
            borderColor: 'rgba(197, 203, 206, 0.3)',
            timeVisible: true,
          },
          height: 380,
          width: chartContainerRef.current!.clientWidth
        }) as any;

        chartRef.current = chart;

        // 4. 캔들스틱 시리즈 추가 (상승 빨강, 하락 파랑 - 한국 전통 색상 반영)
        const candlestickSeries = chart.addCandlestickSeries({
          upColor: '#FF3B30',
          downColor: '#007AFF',
          borderDownColor: '#007AFF',
          borderUpColor: '#FF3B30',
          wickDownColor: '#007AFF',
          wickUpColor: '#FF3B30',
        });

        // 캔들 데이터 적용
        candlestickSeries.setData(data);

        // 5. 20일선 라인 시리즈 추가
        const maData = data
          .filter(d => d.ma20 !== undefined)
          .map(d => ({ time: d.time, value: d.ma20! }));

        const ma20Series = chart.addLineSeries({
          color: '#FF9500', // 주황색
          lineWidth: 1.5,
          title: 'MA20',
          priceLineVisible: false
        });
        ma20Series.setData(maData);

        // 6. 손절선(priceLine) 점선 오버레이 추가
        if (stopLoss > 0) {
          candlestickSeries.createPriceLine({
            price: stopLoss,
            color: '#EF4444',
            lineWidth: 2,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: '손절선(Stop Loss)',
          });
          
          // 7. 매수 타점 근처 반투명 초록색 밴드 영역 오버레이 (area series)
          // 20일선 눌림목의 경우, 20일선의 2% 상방 범위에 반투명 밴드를 그립니다.
          if (setupType === 'A형 눌림') {
            const areaData = data
              .filter(d => d.ma20 !== undefined)
              .map(d => ({
                time: d.time,
                value: d.ma20! * 1.02, // 20일선 기준 상단 2% 한계 영역
              }));
              
            const buyZoneSeries = chart.addAreaSeries({
              topColor: 'rgba(52, 199, 89, 0.08)',
              bottomColor: 'rgba(52, 199, 89, 0.00)',
              lineColor: 'rgba(52, 199, 89, 0.15)',
              lineWidth: 1,
              priceLineVisible: false,
              title: '매수 타점 밴드'
            });
            buyZoneSeries.setData(areaData);
          } else if (setupType === 'B형 VCP') {
            // VCP 돌파의 경우 손절가와 현재 돌파 라인 사이의 변동성 수축 채널 시각화
            const lastCandle = data[data.length - 1];
            const areaData = data.slice(-20).map(d => ({
              time: d.time,
              value: lastCandle.close, // 박스 상단 수평 밴드 오버레이
            }));
            
            const vcpZoneSeries = chart.addAreaSeries({
              topColor: 'rgba(0, 122, 255, 0.08)',
              bottomColor: 'rgba(0, 122, 255, 0.00)',
              lineColor: 'rgba(0, 122, 255, 0.15)',
              lineWidth: 1,
              priceLineVisible: false,
              title: 'VCP 돌파 영역'
            });
            vcpZoneSeries.setData(areaData);
          }
        }

        // 8. 윈도우 리사이즈 대응
        const handleResize = () => {
          if (chartRef.current && chartContainerRef.current) {
            chartRef.current.resize(
              chartContainerRef.current.clientWidth,
              380
            );
          }
        };

        window.addEventListener('resize', handleResize);
        setLoading(false);

        // cleanup
        return () => {
          isMounted = false;
          window.removeEventListener('resize', handleResize);
          chart.remove();
        };
      })
      .catch(err => {
        console.error(err);
        if (isMounted) {
          setError(err.message || "서버 에러로 데이터를 로드할 수 없습니다.");
          setLoading(false);
        }
      });
  }, [ticker, market, stopLoss, setupType]);

  return (
    <div className="w-full h-full relative flex items-center justify-center bg-[#131722] rounded-xl overflow-hidden">
      {loading && (
        <div className="absolute inset-0 bg-[#131722]/80 flex flex-col justify-center items-center text-sm text-gray-400 gap-2 z-10">
          <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-blue-500"></div>
          차트 로딩 중...
        </div>
      )}
      {error && (
        <div className="absolute inset-0 bg-[#131722] flex justify-center items-center text-sm text-red-400 font-semibold z-10">
          {error}
        </div>
      )}
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
}
