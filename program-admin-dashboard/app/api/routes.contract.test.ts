import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const { cookieGet } = vi.hoisted(() => ({
  cookieGet: vi.fn(),
}));

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({ get: cookieGet })),
}));

import { DELETE as proxyDelete, GET as proxyGet, POST as proxyPost } from '@/app/api/admin/[...path]/route';
import { POST as login } from '@/app/api/session/login/route';
import { POST as logout } from '@/app/api/session/logout/route';
import { GET as verify } from '@/app/api/session/verify/route';
import { SESSION_COOKIE_NAME } from '@/lib/admin';

const dashboardOrigin = 'https://admin.example.com';
type NextRequestInit = Omit<RequestInit, 'signal'> & { signal?: AbortSignal };

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function sessionRequest(path: string, init: NextRequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set('Origin', dashboardOrigin);
  return new NextRequest(`${dashboardOrigin}${path}`, {
    ...init,
    headers,
  });
}

function expectBearer(init: RequestInit | undefined, token = 'session-token') {
  const headers = new Headers(init?.headers);
  expect(headers.get('Authorization')).toBe(`Bearer ${token}`);
  expect(headers.has('X-Admin-API-Key')).toBe(false);
}

beforeEach(() => {
  vi.stubEnv('AUTH_API_BASE_URL', 'https://backend.example.com/');
  cookieGet.mockReset();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('admin session route contract', () => {
  it('logs in with the administrator password and stores only the returned bearer token', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ access_token: 'signed-token', expires_in: 1800 }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await login(sessionRequest('/api/session/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'correct horse' }),
    }));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://backend.example.com/user/admin/session/login');
    expect(JSON.parse(String(init?.body))).toEqual({ password: 'correct horse' });
    const setCookie = response.headers.get('set-cookie') || '';
    expect(setCookie).toContain(`${SESSION_COOKIE_NAME}=signed-token`);
    expect(setCookie.toLowerCase()).toContain('httponly');
    expect(setCookie.toLowerCase()).toContain('samesite=strict');
    expect(setCookie).not.toContain('correct horse');
  });

  it('verifies the session with the bearer token', async () => {
    cookieGet.mockReturnValue({ value: 'session-token' });
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ authenticated: true }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await verify();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ authenticated: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://backend.example.com/user/admin/session/verify');
    expectBearer(init);
  });

  it('logs out upstream and clears the local session even if the backend body is empty', async () => {
    cookieGet.mockReturnValue({ value: 'session-token' });
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await logout(sessionRequest('/api/session/logout', { method: 'POST' }));

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('https://backend.example.com/user/admin/session/logout');
    expectBearer(init);
    const setCookie = response.headers.get('set-cookie') || '';
    expect(setCookie).toContain(`${SESSION_COOKIE_NAME}=`);
    expect(setCookie.toLowerCase()).toMatch(/max-age=0|expires=/);
  });
});

describe('admin API proxy contract', () => {
  beforeEach(() => cookieGet.mockReturnValue({ value: 'session-token' }));

  it('forwards allowlisted requests to /user/admin with bearer auth and query parameters', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ users: [], total: 0 }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyGet(
      sessionRequest('/api/admin/users?program_type=ssmaker&page=2'),
      { params: Promise.resolve({ path: ['users'] }) },
    );

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('https://backend.example.com/user/admin/users?program_type=ssmaker&page=2');
    expectBearer(init);
  });

  it('forwards mutation bodies without an administrator API key', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ success: true }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyPost(
      sessionRequest('/api/admin/users/42/extend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: 30 }),
      }),
      { params: Promise.resolve({ path: ['users', '42', 'extend'] }) },
    );

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('https://backend.example.com/user/admin/users/42/extend');
    expectBearer(init);
    expect(new TextDecoder().decode(init?.body as ArrayBuffer)).toBe('{"days":30}');
  });

  it('never forwards unapproved methods or routes', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    const response = await proxyDelete(
      sessionRequest('/api/admin/users/42/history', { method: 'DELETE' }),
      { params: Promise.resolve({ path: ['users', '42', 'history'] }) },
    );

    expect(response.status).toBe(405);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
