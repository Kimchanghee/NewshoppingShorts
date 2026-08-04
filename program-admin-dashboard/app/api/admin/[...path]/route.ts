import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';
import { authApiBaseUrl, sameOrigin, SESSION_COOKIE_NAME } from '@/lib/admin';

type Context = { params: Promise<{ path: string[] }> };

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

  const upstreamUrl = new URL(`/api/admin/${path.map(encodeURIComponent).join('/')}`, authApiBaseUrl());
  request.nextUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.append(key, value));
  const headers = new Headers({ Authorization: `Bearer ${token}`, Accept: 'application/json' });
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);

  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: request.method === 'GET' ? undefined : await request.arrayBuffer(),
      cache: 'no-store',
      signal: AbortSignal.timeout(20_000),
    });
    const response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: { 'Content-Type': upstream.headers.get('content-type') || 'application/json', 'Cache-Control': 'no-store' },
    });
    if (upstream.status === 401) response.cookies.delete(SESSION_COOKIE_NAME);
    return response;
  } catch {
    return NextResponse.json({ error: '운영 API 응답 시간이 초과되었습니다.' }, { status: 504 });
  }
}

export const dynamic = 'force-dynamic';
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
