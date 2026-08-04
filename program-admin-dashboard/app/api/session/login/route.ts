import { NextRequest, NextResponse } from 'next/server';
import { authApiBaseUrl, backendErrorMessage, sameOrigin, SESSION_COOKIE_NAME } from '@/lib/admin';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ error: '허용되지 않은 요청입니다.' }, { status: 403 });

  const body = await request.json().catch(() => ({}));
  const password = typeof body.password === 'string' ? body.password : '';
  if (!password || password.length > 256) {
    return NextResponse.json({ error: '관리자 비밀번호를 확인해 주세요.' }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${authApiBaseUrl()}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ password }),
      cache: 'no-store',
      signal: AbortSignal.timeout(15_000),
    });
    const payload = await upstream.json().catch(() => ({}));
    if (!upstream.ok || typeof payload.access_token !== 'string') {
      return NextResponse.json(
        { error: upstream.status === 401 ? '관리자 비밀번호가 일치하지 않습니다.' : backendErrorMessage(payload, '인증 서버에 연결하지 못했습니다.') },
        { status: upstream.status === 401 ? 401 : 502 },
      );
    }

    const response = NextResponse.json({ success: true });
    const maxAge = Math.min(Math.max(Number(payload.expires_in) || 43_200, 300), 43_200);
    response.cookies.set(SESSION_COOKIE_NAME, payload.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      path: '/',
      maxAge,
    });
    response.headers.set('Cache-Control', 'no-store');
    return response;
  } catch {
    return NextResponse.json({ error: '인증 서버 응답이 지연되고 있습니다.' }, { status: 504 });
  }
}
