import { afterEach, describe, expect, it, vi } from 'vitest';

import { adminProxyAllowed, authApiBaseUrl, backendErrorMessage } from '@/lib/admin';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('admin server boundary', () => {
  it('requires an explicit API base URL', () => {
    vi.stubEnv('AUTH_API_BASE_URL', '');
    expect(() => authApiBaseUrl()).toThrow('AUTH_API_BASE_URL is required');
  });

  it('rejects plaintext production upstreams', () => {
    vi.stubEnv('AUTH_API_BASE_URL', 'http://auth.example.com');
    vi.stubEnv('NODE_ENV', 'production');
    expect(() => authApiBaseUrl()).toThrow('must use HTTPS');
  });

  it('allows only dashboard routes and methods', () => {
    expect(adminProxyAllowed('GET', 'users/12/history')).toBe(true);
    expect(adminProxyAllowed('POST', 'users/12/extend')).toBe(true);
    expect(adminProxyAllowed('POST', 'users/12/reset-password')).toBe(true);
    expect(adminProxyAllowed('DELETE', 'users/12')).toBe(true);
    expect(adminProxyAllowed('PATCH', 'users/12')).toBe(false);
    expect(adminProxyAllowed('GET', 'users/12/reset-password')).toBe(false);
    expect(adminProxyAllowed('GET', 'users/12/password')).toBe(false);
  });

  it('does not expose internal backend errors', () => {
    expect(backendErrorMessage({ detail: 'psycopg connection traceback' }, 'safe')).toBe('safe');
    expect(backendErrorMessage({ detail: '사용자를 찾을 수 없습니다.' }, 'safe')).toBe('사용자를 찾을 수 없습니다.');
  });
});
