import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';
import { authApiBaseUrl, sameOrigin, SESSION_COOKIE_NAME } from '@/lib/admin';

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ error: '허용되지 않은 요청입니다.' }, { status: 403 });
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (token) {
    try {
      await fetch(`${authApiBaseUrl()}/api/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
        cache: 'no-store',
        signal: AbortSignal.timeout(10_000),
      });
    } catch (error) {
      console.warn('[admin-session] upstream logout failed', {
        error: error instanceof Error ? error.name : 'UnknownError',
      });
    }
  }
  const response = NextResponse.json({ success: true });
  response.cookies.delete(SESSION_COOKIE_NAME);
  response.headers.set('Cache-Control', 'no-store');
  return response;
}
