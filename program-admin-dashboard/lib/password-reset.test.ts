import { describe, expect, it } from 'vitest';

import { passwordResetError } from '@/lib/password-reset';

const validInput = {
  expectedUsername: 'account_name',
  usernameConfirmation: 'account_name',
  newPassword: 'FreshPassword123',
  confirmPassword: 'FreshPassword123',
};

describe('password reset validation', () => {
  it('accepts an exact account confirmation and a valid matching password', () => {
    expect(passwordResetError(validInput)).toBeNull();
  });

  it('requires the exact selected username', () => {
    expect(passwordResetError({ ...validInput, usernameConfirmation: 'other' }))
      .toBe('확인 사용자명이 일치하지 않습니다.');
  });

  it('requires the shared length and complexity policy', () => {
    expect(passwordResetError({ ...validInput, newPassword: 'short1', confirmPassword: 'short1' }))
      .toContain('8자 이상');
    expect(passwordResetError({ ...validInput, newPassword: 'onlyletters', confirmPassword: 'onlyletters' }))
      .toContain('영문자와 숫자');
  });

  it('rejects a mismatched confirmation', () => {
    expect(passwordResetError({ ...validInput, confirmPassword: 'Different123' }))
      .toBe('새 비밀번호 확인이 일치하지 않습니다.');
  });
});
