import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="center-state">
      <span className="eyebrow">404</span>
      <h1>요청한 화면이 없습니다</h1>
      <Link className="button primary" href="/">운영 콘솔로 돌아가기</Link>
    </main>
  );
}
