import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { LoginForm } from '@/components/login-form';
import { SESSION_COOKIE_NAME } from '@/lib/admin';

export const dynamic = 'force-dynamic';

export default async function LoginPage() {
  const cookieStore = await cookies();
  if (cookieStore.get(SESSION_COOKIE_NAME)?.value) redirect('/');
  return <LoginForm />;
}
