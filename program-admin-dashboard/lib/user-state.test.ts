import { describe, expect, it } from 'vitest';

import { entitlementState, parseApiDate, projectedExpiry, remainingLabel } from '@/lib/user-state';

const NOW = Date.parse('2026-08-05T00:00:00Z');

describe('user entitlement presentation', () => {
  it('keeps a future-expiry trial labelled as trial', () => {
    const state = entitlementState({ user_type: 'trial', subscription_expires_at: '2026-08-12T00:00:00Z' }, NOW);
    expect(state.label).toBe('체험');
    expect(state.expiryLabel).toBe('체험 만료');
  });

  it('marks only valid subscribers as active subscriptions', () => {
    expect(entitlementState({ user_type: 'subscriber', subscription_expires_at: '2026-08-12T00:00:00Z' }, NOW).label).toBe('구독');
    expect(entitlementState({ user_type: 'subscriber', subscription_expires_at: '2026-08-01T00:00:00Z' }, NOW).label).toBe('구독 만료');
  });

  it('treats timezone-less API values as UTC', () => {
    expect(parseApiDate('2026-08-05T09:00:00')?.toISOString()).toBe('2026-08-05T09:00:00.000Z');
  });

  it('calculates stable labels and reductions', () => {
    expect(remainingLabel('2026-08-07T00:00:00Z', NOW)).toBe('2일 남음');
    expect(projectedExpiry('2026-08-10T00:00:00Z', 3, 'reduce')).toBe('2026-08-07T00:00:00.000Z');
  });
});
