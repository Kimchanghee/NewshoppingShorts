export const SESSION_COOKIE_NAME = 'ssmaker_program_admin_session';

const INTERNAL_ERROR_PATTERN = /traceback|psycopg|sqlalchemy|\[sql:|\[parameters:|exception|stack|invalid input value for enum/i;
const ADMIN_PROXY_ALLOWLIST = [
  ['GET', /^users$/],
  ['GET', /^users\/\d+$/],
  ['GET', /^users\/\d+\/history$/],
  ['GET', /^stats$/],
  ['POST', /^users\/\d+\/(?:extend|toggle-active|revoke-subscription|reduce-subscription|reset-password)$/],
  ['DELETE', /^users\/\d+$/],
] as const;

export function authApiBaseUrl() {
  const configured = process.env.AUTH_API_BASE_URL?.trim();
  if (!configured) throw new Error('AUTH_API_BASE_URL is required');
  const url = new URL(configured);
  if (process.env.NODE_ENV === 'production' && url.protocol !== 'https:') {
    throw new Error('AUTH_API_BASE_URL must use HTTPS in production');
  }
  if (!['https:', 'http:'].includes(url.protocol)) throw new Error('AUTH_API_BASE_URL protocol is invalid');
  return configured.replace(/\/+$/, '');
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
  for (const candidate of [value.message, value.detail, value.error]) {
    if (typeof candidate !== 'string') continue;
    const message = candidate.trim();
    if (message && message.length <= 200 && !INTERNAL_ERROR_PATTERN.test(message)) return message;
  }
  return fallback;
}

export function adminProxyAllowed(method: string, path: string) {
  return ADMIN_PROXY_ALLOWLIST.some(([allowedMethod, pattern]) => (
    allowedMethod === method && pattern.test(path)
  ));
}
