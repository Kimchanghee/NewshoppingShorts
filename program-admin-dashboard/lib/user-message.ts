export type ApiErrorPayload = {
  error?: unknown;
  detail?: unknown;
  message?: unknown;
};

const INTERNAL_ERROR_PATTERN = /(?:traceback|psycopg|sqlalchemy|\[sql:|\[parameters:|exception|stack trace|invalid input value for enum|status_code|request_id|winerror|errno|[a-z_]+error\b)/i;
const INTERNAL_CODE_PATTERN = /\b(?:ST-[A-Z]\d{3}|LOGIN_[A-Z0-9_]+|[A-Z][A-Z0-9]+_[A-Z0-9_]{2,})\b/;
const ENGLISH_ERROR_PATTERN = /\b(?:error|exception|failed|failure|invalid|denied|forbidden|not found|timed? out|unavailable|unexpected|cannot|could not|only one active job)\b/i;

function isEnglishDeveloperError(message: string) {
  if (!ENGLISH_ERROR_PATTERN.test(message)) return false;
  const hangul = (message.match(/[가-힣]/g) || []).length;
  const latin = (message.match(/[A-Za-z]/g) || []).length;
  return latin >= 8 && latin > hangul;
}

export function safeAdminMessage(value: unknown, fallback: string) {
  if (typeof value !== 'string') return fallback;
  const message = value.trim();
  if (
    !message
    || message.length > 200
    || INTERNAL_ERROR_PATTERN.test(message)
    || INTERNAL_CODE_PATTERN.test(message)
    || isEnglishDeveloperError(message)
  ) {
    return fallback;
  }
  return message;
}

export function adminApiErrorMessage(status: number, payload: ApiErrorPayload) {
  if (status >= 500) return '서버 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
  if (status === 404) return '요청한 사용자 정보를 찾을 수 없습니다.';
  if (status === 403) return '이 작업을 수행할 권한이 없습니다.';
  if (status === 429) return '요청이 많습니다. 잠시 후 다시 시도해 주세요.';
  const fallback = '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.';
  return safeAdminMessage(
    payload.error,
    safeAdminMessage(payload.message, safeAdminMessage(payload.detail, fallback)),
  );
}
