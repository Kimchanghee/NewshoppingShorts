import { NextRequest, NextResponse } from 'next/server';
import { sameOrigin, SESSION_COOKIE_NAME } from '@/lib/admin';

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ error: '허용되지 않은 요청입니다.' }, { status: 403 });
  const response = NextResponse.json({ success: true });
  response.cookies.delete(SESSION_COOKIE_NAME);
  response.headers.set('Cache-Control', 'no-store');
  return response;
}
