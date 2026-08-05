import type { User } from '@/lib/types';

export function parseApiDate(value?: string | null) {
  if (!value) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value?: string | null, compact = false) {
  const date = parseApiDate(value);
  if (!date) return '—';
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: compact ? undefined : 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function remainingLabel(value?: string | null, now = Date.now()) {
  const date = parseApiDate(value);
  if (!date) return '만료일 없음';
  const diff = Math.ceil((date.getTime() - now) / 86_400_000);
  if (diff < 0) return `${Math.abs(diff)}일 전 만료`;
  if (diff === 0) return '오늘 만료';
  return `${diff}일 남음`;
}

export function entitlementState(user: Pick<User, 'user_type' | 'subscription_expires_at'>, now = Date.now()) {
  const expiry = parseApiDate(user.subscription_expires_at);
  const hasValidExpiry = Boolean(expiry && expiry.getTime() > now);

  if (user.user_type === 'admin') {
    return { label: '관리자', tone: 'info', expiryLabel: '관리자 권한 만료', expired: false, canManageSubscription: false };
  }
  if (user.user_type === 'subscriber' && hasValidExpiry) {
    return { label: '구독', tone: 'positive', expiryLabel: '구독 만료', expired: false, canManageSubscription: true };
  }
  if (user.user_type === 'subscriber') {
    return { label: '구독 만료', tone: 'neutral', expiryLabel: '구독 만료', expired: true, canManageSubscription: true };
  }
  return {
    label: hasValidExpiry ? '체험' : '체험 만료',
    tone: 'neutral',
    expiryLabel: '체험 만료',
    expired: Boolean(expiry && !hasValidExpiry),
    canManageSubscription: false,
  };
}

export function projectedExpiry(value: string | null | undefined, days: number, direction: 'extend' | 'reduce') {
  const current = parseApiDate(value);
  const base = direction === 'extend' && (!current || current.getTime() < Date.now()) ? new Date() : current;
  if (!base) return null;
  const projected = new Date(base);
  projected.setUTCDate(projected.getUTCDate() + (direction === 'extend' ? days : -days));
  return projected.toISOString();
}
