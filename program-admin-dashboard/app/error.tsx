'use client';

import { AlertTriangle, RotateCcw } from 'lucide-react';

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="center-state">
      <div className="state-icon danger"><AlertTriangle size={24} /></div>
      <h1>화면을 불러오지 못했습니다</h1>
      <p>잠시 후 다시 시도하거나 운영 API 상태를 확인해 주세요.</p>
      <button className="button primary" onClick={reset}><RotateCcw size={16} /> 다시 시도</button>
    </main>
  );
}
