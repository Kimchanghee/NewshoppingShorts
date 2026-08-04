export const SESSION_COOKIE_NAME = 'ssmaker_program_admin_session';

export function authApiBaseUrl() {
  return (process.env.AUTH_API_BASE_URL || 'https://newshopping-shorts-auth.vercel.app').replace(/\/+$/, '');
}

export function sameOrigin(request: Request) {
  const origin = request.headers.get('origin');
  if (!origin) return true;
  let originUrl: URL;
  try {
    originUrl = new URL(origin);
  } catch {
    return false;
  }
  const requestUrl = new URL(request.url);
  const forwardedHost = request.headers.get('x-forwarded-host')?.split(',')[0]?.trim();
  const requestHost = request.headers.get('host')?.trim();
  const allowedHosts = new Set([requestUrl.host, requestHost, forwardedHost].filter(Boolean));
  const forwardedProtocol = request.headers.get('x-forwarded-proto')?.split(',')[0]?.trim();
  const allowedProtocols = new Set([requestUrl.protocol.replace(':', ''), forwardedProtocol].filter(Boolean));
  return allowedHosts.has(originUrl.host) && allowedProtocols.has(originUrl.protocol.replace(':', ''));
}

export function backendErrorMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== 'object') return fallback;
  const value = payload as Record<string, unknown>;
  if (typeof value.message === 'string' && value.message.trim()) return value.message;
  if (typeof value.detail === 'string' && value.detail.trim()) return value.detail;
  if (typeof value.error === 'string' && value.error.trim()) return value.error;
  return fallback;
}
