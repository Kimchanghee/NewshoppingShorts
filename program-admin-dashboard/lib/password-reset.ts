export type PasswordResetInput = {
  expectedUsername: string;
  usernameConfirmation: string;
  newPassword: string;
  confirmPassword: string;
};

export function passwordResetError(input: PasswordResetInput): string | null {
  if (input.usernameConfirmation !== input.expectedUsername) {
    return '확인 사용자명이 일치하지 않습니다.';
  }
  if (input.newPassword.length < 8 || input.newPassword.length > 128) {
    return '새 비밀번호는 8자 이상 128자 이하로 입력해 주세요.';
  }
  if (!/[A-Za-z]/.test(input.newPassword) || !/[0-9]/.test(input.newPassword)) {
    return '새 비밀번호에는 영문자와 숫자를 각각 1자 이상 포함해 주세요.';
  }
  if (input.newPassword !== input.confirmPassword) {
    return '새 비밀번호 확인이 일치하지 않습니다.';
  }
  return null;
}
