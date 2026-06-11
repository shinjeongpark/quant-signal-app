// src/lib/supabase.ts
// Supabase Database 연동을 위한 클라이언트 초기화 모듈입니다.
// Next.js API Routes 및 컴포넌트 전체에서 재사용 가능한 싱글톤 인스턴스를 반환합니다.

import { createClient } from '@supabase/supabase-js';

// 환경 변수 검출 (클라이언트 사이드 환경과 깃허브 액션/Vercel 서버사이드 환경 지원)
// 빌드 타임에 환경 변수가 없어 빌드가 크래시되는 것을 방지하기 위해 placeholder 값을 폴백으로 제공합니다.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || 'https://placeholder-url.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_KEY || 'placeholder-key';

if (!process.env.NEXT_PUBLIC_SUPABASE_URL && !process.env.SUPABASE_URL) {
  console.warn(
    "[주의] Supabase URL 또는 ANON_KEY 환경 변수가 로드되지 않았습니다. " +
    "빌드 타임 placeholder 주소를 임시 사용합니다."
  );
}

// Supabase 클라이언트 객체 생성 및 반환
export const supabase = createClient(
  supabaseUrl || '',
  supabaseAnonKey || ''
);
