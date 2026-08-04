import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { authApiBaseUrl, SESSION_COOKIE_NAME } from '@/lib/admin';

export const dynamic = 'force-dynamic';

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ authenticated: false }, { status: 401 });
  try {
    const upstream = await fetch(`${authApiBaseUrl()}/api/auth/verify`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(10_000),
    });
    const response = NextResponse.json({ authenticated: upstream.ok }, { status: upstream.ok ? 200 : 401 });
    if (!upstream.ok) response.cookies.delete(SESSION_COOKIE_NAME);
    return response;
  } catch {
    return NextResponse.json({ authenticated: false, error: '인증 서버 연결 실패' }, { status: 503 });
  }
}
