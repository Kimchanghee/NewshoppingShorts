import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { authApiBaseUrl, SESSION_COOKIE_NAME } from '@/lib/admin';

export const dynamic = 'force-dynamic';

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ authenticated: false }, { status: 401 });
  try {
    const upstream = await fetch(`${authApiBaseUrl()}/user/admin/session/verify`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(10_000),
    });
    const invalidSession = upstream.status === 401 || upstream.status === 403;
    const response = NextResponse.json(
      upstream.ok
        ? { authenticated: true }
        : { authenticated: false, error: invalidSession ? '관리자 세션이 만료되었습니다.' : '인증 서버에서 세션을 확인하지 못했습니다.' },
      { status: upstream.ok ? 200 : invalidSession ? 401 : 502 },
    );
    if (invalidSession) response.cookies.delete(SESSION_COOKIE_NAME);
    return response;
  } catch {
    return NextResponse.json({ authenticated: false, error: '인증 서버 연결 실패' }, { status: 503 });
  }
}
