// src/app/api/stocks/route.ts
// Supabase Database에서 실시간으로 스캔 완료된 주도주 데이터 및 지수 현황을 가져와서
// 프론트엔드 대시보드에 JSON 형식으로 제공하는 Next.js 15 API 라우터입니다.

import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

// 캐시를 적용하지 않고 최신 DB 상태를 실시간 반환하도록 dynamic 강제 설정
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // 1. 4대 주요 지수 상태 정보 조회
    const { data: marketData, error: marketError } = await supabase
      .from('market_status')
      .select('*')
      .eq('id', 1)
      .single();

    if (marketError) {
      console.error("[지수 데이터 조회 에러]", marketError);
    }

    // 2. 스캔된 주도주 정보 리스트 전체 조회
    // 셋업 등급(Grade) 기준으로 A+ -> A -> B -> C 순으로 가중치를 두고, 
    // 동일 등급 내에서는 Minervini RS Score(상대강도)가 높은 순으로 정렬합니다.
    const { data: stockData, error: stockError } = await supabase
      .from('scanned_stocks')
      .select('*')
      .order('grade', { ascending: true }) // A+는 문자열 정렬상 특성이 있으므로, 쿼리 후 코드 정렬 보완 예정
      .order('rs_score', { ascending: false });

    if (stockError) {
      console.error("[주도주 데이터 조회 에러]", stockError);
      return NextResponse.json({ error: "데이터베이스 조회에 실패했습니다." }, { status: 500 });
    }

    // 셋업 등급(A+, A, B, C) 순서 정밀 정돈 (A+가 문자열 정렬 시 A 뒤로 가는 현상 정돈)
    let sortedStocks = [];
    if (stockData) {
      const gradePriority: { [key: string]: number } = { 'A+': 1, 'A': 2, 'B': 3, 'C': 4 };
      sortedStocks = [...stockData].sort((a, b) => {
        const priorityA = gradePriority[a.grade] || 99;
        const priorityB = gradePriority[b.grade] || 99;
        if (priorityA !== priorityB) {
          return priorityA - priorityB;
        }
        return (b.rs_score || 0) - (a.rs_score || 0); // RS Score 기준 내림차순
      });
    }

    // 3. 지수 상태와 주도주 데이터를 결합하여 최종 응답 반환
    return NextResponse.json({
      marketStatus: marketData || {
        spy_above_200ma: true,
        qqq_above_200ma: true,
        kospi_above_200ma: true,
        kosdaq_above_200ma: true,
        spy_close: 0, qqq_close: 0, kospi_close: 0, kosdaq_close: 0
      },
      stocks: sortedStocks
    });

  } catch (error) {
    console.error("[API 내부 시스템 에러]", error);
    return NextResponse.json({ error: "내부 서버 에러가 발생했습니다." }, { status: 500 });
  }
}
