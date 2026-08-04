'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Database, KeyRound, LoaderCircle, LockKeyhole, ShieldCheck } from 'lucide-react';

export function LoginForm() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await fetch('/api/session/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(payload.error || '로그인하지 못했습니다.');
        return;
      }
      router.replace('/');
      router.refresh();
    } catch {
      setError('네트워크 연결을 확인해 주세요.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-story" aria-label="서비스 소개">
        <div className="brand-lockup light">
          <span className="brand-mark"><Database size={21} /></span>
          <div><strong>SSMaker Ops</strong><small>Program DB Console</small></div>
        </div>
        <div className="story-copy">
          <span className="eyebrow light">PROGRAM OPERATIONS</span>
          <h1>프로그램 사용자를<br />한곳에서 운영하세요.</h1>
          <p>수익 사이트 통계와 완전히 분리된 사용자 DB 전용 관리 콘솔입니다.</p>
        </div>
        <div className="trust-grid">
          <div><ShieldCheck size={20} /><span>서버 전용 인증</span></div>
          <div><LockKeyhole size={20} /><span>HTTP-only 세션</span></div>
          <div><Database size={20} /><span>운영 DB 연동</span></div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <span className="eyebrow">SECURE ACCESS</span>
          <h2>운영 콘솔 로그인</h2>
          <p>인증 API의 관리자 비밀번호를 입력하세요.</p>
          <form onSubmit={submit}>
            <label htmlFor="admin-password">관리자 비밀번호</label>
            <div className="input-with-icon">
              <KeyRound size={18} />
              <input
                id="admin-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="관리자 비밀번호"
                required
                autoFocus
              />
            </div>
            {error ? <p className="form-error" role="alert">{error}</p> : null}
            <button className="button primary login-submit" disabled={loading} type="submit">
              {loading ? <><LoaderCircle className="spin" size={17} /> 인증 중</> : <>콘솔 접속 <ArrowRight size={17} /></>}
            </button>
          </form>
          <p className="security-note"><ShieldCheck size={15} /> 비밀번호는 브라우저에 저장되지 않습니다.</p>
        </div>
      </section>
    </main>
  );
}
