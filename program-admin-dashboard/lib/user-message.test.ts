import { describe, expect, it } from 'vitest';

import { adminApiErrorMessage, safeAdminMessage } from './user-message';

describe('safeAdminMessage', () => {
  it('keeps useful Korean guidance', () => {
    expect(safeAdminMessage('사용자 정보를 다시 확인해 주세요.', '대체 문구'))
      .toBe('사용자 정보를 다시 확인해 주세요.');
  });

  it.each([
    'Only one active job is allowed. Finish or clear the current item first.',
    'PermissionError: access denied',
    '[LOGIN_REJECTED] invalid credentials',
    'Traceback: File "route.py", line 10',
  ])('hides developer-facing details: %s', (raw) => {
    expect(safeAdminMessage(raw, '다시 시도해 주세요.')).toBe('다시 시도해 주세요.');
  });

  it('does not expose an HTTP status number in the fallback', () => {
    expect(adminApiErrorMessage(422, { detail: 'Invalid payload schema' }))
      .toBe('요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');
  });
});
