import { expect, test } from '@playwright/test';

const adminPassword = process.env.E2E_ADMIN_PASSWORD;

test('admin can log in and inspect server-filtered program data', async ({ page }) => {
  test.skip(!adminPassword, 'E2E_ADMIN_PASSWORD is required for authenticated smoke testing');

  await page.goto('/login');
  await page.getByLabel('관리자 비밀번호').fill(adminPassword!);
  await Promise.all([
    page.waitForURL('/'),
    page.getByRole('button', { name: '운영 콘솔 접속' }).click(),
  ]);

  await expect(page.getByRole('heading', { name: /운영 현황/ })).toBeVisible();
  await expect(page.getByText('AUTH PRODUCTION')).toBeVisible();

  const verifyProgramOnlineCount = async (program: 'ssmaker' | 'stmaker', label: string) => {
    const statsResponse = page.waitForResponse((response) => (
      response.url().includes('/api/admin/stats?') && response.url().includes(`program_type=${program}`)
    ));
    await page.getByRole('button', { name: new RegExp(label) }).click();
    const response = await statsResponse;
    expect(response.ok()).toBe(true);
    const stats = await response.json();
    const onlineCard = page.locator('.metric-card').filter({ hasText: '현재 온라인' }).locator('strong');
    await expect(onlineCard).toHaveText(String(stats.users.online));
    return stats.users.online as number;
  };

  const ssmakerOnline = await verifyProgramOnlineCount('ssmaker', 'SSMaker');
  const stmakerOnline = await verifyProgramOnlineCount('stmaker', 'STMaker');
  console.log(`ONLINE_COUNTS ssmaker=${ssmakerOnline} stmaker=${stmakerOnline}`);

  const onlineResponse = page.waitForResponse((response) => (
    response.url().includes('/api/admin/users?') && response.url().includes('status=online')
  ));
  await page.getByRole('button', { name: '온라인', exact: true }).click();
  const filtered = await onlineResponse;
  expect(filtered.ok()).toBe(true);
  const payload = await filtered.json();
  expect(payload.total).toBeGreaterThanOrEqual(0);
  expect(payload.total).toBeGreaterThanOrEqual(payload.users.length);
  expect(payload.users.every((user: { is_online: boolean }) => user.is_online)).toBe(true);

  await expect(page.getByText(/검색 결과 .*명/)).toBeVisible();

  const allResponse = page.waitForResponse((response) => (
    response.url().includes('/api/admin/users?') && !response.url().includes('status=')
  ));
  await page.locator('.filter-row').getByRole('button', { name: '전체', exact: true }).click();
  const allPayload = await (await allResponse).json();
  if (allPayload.users.length > 0) {
    await page.locator('tbody tr').first().click();
    await expect(page.getByRole('heading', { name: '사용자 상세' })).toBeVisible();
    await expect(page.getByText('마지막 IP (마스킹)')).toBeVisible();
  }
});
