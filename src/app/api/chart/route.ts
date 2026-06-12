// src/app/api/chart/route.ts
// 야후 파이낸스의 공개 REST API를 서버사이드에서 대리 호출(Proxy)하여
// TradingView Lightweight Charts 규격에 맞는 최근 150영업일 일봉 데이터를 반환하는 Next.js 15 API입니다.

import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker');
  const market = searchParams.get('market');

  if (!ticker) {
    return NextResponse.json({ error: "티커 정보가 필요합니다." }, { status: 400 });
  }

  // 한국 종목코드 매핑 (예: 005930 -> 코스피는 .KS, 코스닥은 .KQ)
  // 한국 주도주 스캐너의 유니버스 정보를 대조하여 접미사를 붙입니다.
  let targetTicker = ticker;
  if (market === 'KR') {
    // 코스닥 주요 종목 목록 리스트에 포함되는지 확인하여 접미사 맵핑
    // (보통 6자리 숫자이고, 005930 등은 코스피이므로 .KS, 247540 등 코스닥은 .KQ 적용)
    const kosdaqCodes = ['247540', '086520', '028300', '198440', '214150', '035900', '068760', '145020', '293490', '039840'];
    if (kosdaqCodes.includes(ticker)) {
      targetTicker = `${ticker}.KQ`;
    } else {
      targetTicker = `${ticker}.KS`;
    }
  }

  try {
    // 야후 파이낸스 일봉 API 호출 (최근 1년 범위, 일일 주기)
    // [보안 및 안정성]:
    //   - query1 대신 query2 도메인을 활용하여 IP 차단 우회 시도
    //   - 야후 파이낸스가 봇으로 차단하는 것을 방지하기 위해 User-Agent 브라우저 헤더 주입
    //   - cache: 'no-store' 설정을 통해 이전 실패 응답 캐싱으로 인한 지속적 오류 상태 완벽 방지
    const url = `https://query2.finance.yahoo.com/v8/finance/chart/${targetTicker}?interval=1d&range=1y`;
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://finance.yahoo.com/'
      },
      cache: 'no-store'
    });

    if (!res.ok) {
      const errorBody = await res.text();
      console.error("[야후 파이낸스 API 오류]", res.status, errorBody);
      return NextResponse.json({ 
        error: `주가 정보 로드 실패 (HTTP ${res.status})`,
        details: errorBody.slice(0, 100) 
      }, { status: res.status });
    }

    const data = await res.json();
    const result = data?.chart?.result?.[0];
    
    if (!result) {
      return NextResponse.json({ error: "유효한 차트 데이터를 찾을 수 없습니다." }, { status: 404 });
    }

    const timestamps = result.timestamp || [];
    const indicators = result.indicators?.quote?.[0] || {};
    const adjClose = result.indicators?.adjclose?.[0]?.adjclose || indicators.close || [];
    
    const { open = [], high = [], low = [], volume = [] } = indicators;

    // TradingView Lightweight Charts 규격([{ time: 'YYYY-MM-DD', open, high, low, close }])으로 포맷팅
    const chartData = [];
    for (let i = 0; i < timestamps.length; i++) {
      // 0 값이나 결측값 예외 제거
      if (open[i] == null || high[i] == null || low[i] == null || adjClose[i] == null) {
        continue;
      }

      const date = new Date(timestamps[i] * 1000);
      const yyyy = date.getFullYear();
      const mm = String(date.getMonth() + 1).padStart(2, '0');
      const dd = String(date.getDate()).padStart(2, '0');
      const timeStr = `${yyyy}-${mm}-${dd}`;

      chartData.push({
        time: timeStr,
        open: Number(open[i].toFixed(2)),
        high: Number(high[i].toFixed(2)),
        low: Number(low[i].toFixed(2)),
        close: Number(adjClose[i].toFixed(2)),
        volume: Number(volume[i] || 0)
      });
    }

    // 최근 150거래일만 슬라이싱하여 용량 및 가독성 최적화
    const slicedData = chartData.slice(-150);
    return NextResponse.json(slicedData);

  } catch (error) {
    console.error("[차트 API 호출 에러]", error);
    return NextResponse.json({ error: "차트 데이터 가공 중 에러가 발생했습니다." }, { status: 500 });
  }
}
