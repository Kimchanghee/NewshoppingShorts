import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';
import { adminProxyAllowed, authApiBaseUrl, backendErrorMessage, sameOrigin, SESSION_COOKIE_NAME } from '@/lib/admin';

type Context = { params: Promise<{ path: string[] }> };
const SUPPORTED_PROGRAMS = new Set(['ssmaker', 'stmaker']);

async function proxy(request: NextRequest, context: Context) {
  if (request.method !== 'GET' && !sameOrigin(request)) {
    return NextResponse.json({ error: '허용되지 않은 요청입니다.' }, { status: 403 });
  }
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!token) return NextResponse.json({ error: '로그인이 필요합니다.' }, { status: 401 });

  const { path } = await context.params;
  if (!path.length || path.some((part) => !part || part === '.' || part === '..')) {
    return NextResponse.json({ error: '잘못된 API 경로입니다.' }, { status: 400 });
  }

  const normalizedPath = path.join('/');
  if (!adminProxyAllowed(request.method, normalizedPath)) {
    return NextResponse.json({ error: '허용되지 않은 관리자 API 요청입니다.' }, { status: 405 });
  }

  const programType = request.nextUrl.searchParams.get('program_type');
  if (programType && !SUPPORTED_PROGRAMS.has(programType)) {
    return NextResponse.json({ error: '지원하지 않는 프로그램입니다.' }, { status: 400 });
  }

  let upstreamUrl: URL;
  try {
    upstreamUrl = new URL(`/user/admin/${path.map(encodeURIComponent).join('/')}`, authApiBaseUrl());
  } catch {
    return NextResponse.json({ error: '운영 API가 구성되지 않았습니다.' }, { status: 503 });
  }
  request.nextUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.append(key, value));
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
    Accept: 'application/json',
    'X-Request-ID': crypto.randomUUID(),
  });
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);

  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET') {
    body = await request.arrayBuffer();
    if (body.byteLength > 4096) {
      return NextResponse.json({ error: '요청 본문이 너무 큽니다.' }, { status: 413 });
    }
  }

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body,
      cache: 'no-store',
      signal: AbortSignal.timeout(20_000),
    });
    const payload = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      console.error('[admin-proxy] upstream failure', {
        path: normalizedPath,
        programType: programType || 'all',
        status: upstream.status,
      });
      const fallback = upstream.status >= 500
        ? '사용자 DB 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.'
        : `관리자 요청을 처리하지 못했습니다. (${upstream.status})`;
      const response = NextResponse.json(
        { error: backendErrorMessage(payload, fallback) },
        { status: upstream.status, headers: { 'Cache-Control': 'no-store' } },
      );
      if (upstream.status === 401) response.cookies.delete(SESSION_COOKIE_NAME);
      return response;
    }

    const response = NextResponse.json(payload ?? {}, {
      status: upstream.status,
      headers: { 'Cache-Control': 'no-store' },
    });
    return response;
  } catch (error) {
    const timedOut = error instanceof Error && error.name === 'TimeoutError';
    console.error('[admin-proxy] request failed', {
      path: path.join('/'),
      programType: programType || 'all',
      error: error instanceof Error ? error.name : 'UnknownError',
    });
    return NextResponse.json(
      { error: timedOut ? '운영 API 응답 시간이 초과되었습니다.' : '운영 API에 연결할 수 없습니다.' },
      { status: timedOut ? 504 : 502, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}

export const dynamic = 'force-dynamic';
export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
