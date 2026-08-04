'use client';

import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpFromLine,
  Ban,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  Clock3,
  Database,
  Gauge,
  History,
  Laptop,
  LoaderCircle,
  LogOut,
  Menu,
  MoreHorizontal,
  Power,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserCheck,
  Users,
  Wifi,
  X,
} from 'lucide-react';
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import type {
  AdminActionResponse,
  LoginHistory as LoginHistoryItem,
  LoginHistoryResponse,
  ProgramKey,
  StatsResponse,
  User,
  UserListResponse,
} from '@/lib/types';

const PROGRAMS: Array<{ key: ProgramKey; label: string; short: string }> = [
  { key: 'all', label: '전체 프로그램', short: 'ALL' },
  { key: 'ssmaker', label: 'SSMaker', short: 'SS' },
  { key: 'stmaker', label: 'STMaker', short: 'ST' },
];

const EMPTY_STATS: StatsResponse = {
  users: { total: 0, active: 0, online: 0, with_subscription: 0 },
  work: { total_used: 0, users_with_work: 0, in_progress_users: 0, avg_used_per_user: 0 },
};

type FilterKey = 'all' | 'subscriber' | 'trial' | 'online' | 'inactive';
type ConfirmState = {
  kind: 'toggle' | 'revoke' | 'reduce' | 'delete';
  title: string;
  description: string;
  confirmLabel: string;
  danger?: boolean;
  days?: number;
} | null;

type ApiErrorPayload = {
  error?: unknown;
  detail?: unknown;
  message?: unknown;
};

const INTERNAL_ERROR_PATTERN = /traceback|psycopg|sqlalchemy|\[sql:|\[parameters:|exception|invalid input value for enum/i;

function safeApiMessage(value: unknown, fallback: string) {
  if (typeof value !== 'string') return fallback;
  const message = value.trim();
  if (!message || message.length > 200 || INTERNAL_ERROR_PATTERN.test(message)) return fallback;
  return message;
}

function apiErrorMessage(status: number, payload: ApiErrorPayload) {
  if (status >= 500) return '사용자 DB 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
  if (status === 404) return '요청한 사용자 정보를 찾을 수 없습니다.';
  if (status === 403) return '이 작업을 수행할 권한이 없습니다.';
  if (status === 429) return '요청이 많습니다. 잠시 후 다시 시도해 주세요.';
  const fallback = `요청을 처리하지 못했습니다. (${status})`;
  return safeApiMessage(payload.error, safeApiMessage(payload.message, safeApiMessage(payload.detail, fallback)));
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, { ...init, cache: 'no-store' });
  if (response.status === 401) {
    window.location.assign('/login');
    throw new Error('세션이 만료되었습니다.');
  }
  const payload = await response.json().catch(() => ({})) as ApiErrorPayload;
  if (!response.ok) {
    throw new Error(apiErrorMessage(response.status, payload));
  }
  return payload as T;
}

function parseApiDate(value?: string | null) {
  if (!value) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasZone ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value?: string | null, compact = false) {
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

function remainingLabel(value?: string | null) {
  const date = parseApiDate(value);
  if (!date) return '만료일 없음';
  const diff = Math.ceil((date.getTime() - Date.now()) / 86_400_000);
  if (diff < 0) return `${Math.abs(diff)}일 전 만료`;
  if (diff === 0) return '오늘 만료';
  return `${diff}일 남음`;
}

function programLabel(key?: string) {
  return PROGRAMS.find((program) => program.key === key)?.label || key || '미지정';
}

function userState(user: User) {
  if (!user.is_active) return { label: '비활성', tone: 'neutral' };
  if (user.is_online) return { label: '온라인', tone: 'positive' };
  return { label: '활성', tone: 'info' };
}

export function DashboardShell() {
  const router = useRouter();
  const [program, setProgram] = useState<ProgramKey>('all');
  const [filter, setFilter] = useState<FilterKey>('all');
  const [search, setSearch] = useState('');
  const deferredSearch = useDeferredValue(search.trim());
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<StatsResponse>(EMPTY_STATS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [history, setHistory] = useState<LoginHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [customDays, setCustomDays] = useState(30);
  const [actionBusy, setActionBusy] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [deleteText, setDeleteText] = useState('');
  const [toast, setToast] = useState<{ message: string; tone: 'success' | 'error' } | null>(null);
  const requestSequence = useRef(0);

  const loadData = useCallback(async (quiet = false) => {
    const requestId = ++requestSequence.current;
    quiet ? setRefreshing(true) : setLoading(true);
    setError('');
    if (!quiet) {
      setUsers([]);
      setTotal(0);
      setStats(EMPTY_STATS);
    }
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      include_total: 'true',
      cleanup_offline: 'true',
    });
    const statsQuery = new URLSearchParams({ include_requests: 'false' });
    if (program !== 'all') {
      query.set('program_type', program);
      statsQuery.set('program_type', program);
    }
    if (deferredSearch) query.set('search', deferredSearch);
    try {
      // The user-list call expires stale heartbeats. Read stats only after that
      // cleanup commits so the online count cannot race ahead with old flags.
      const userData = await apiRequest<UserListResponse>(`users?${query}`);
      if (requestId !== requestSequence.current) return;
      const statsData = await apiRequest<StatsResponse>(`stats?${statsQuery}`);
      if (requestId !== requestSequence.current) return;
      setUsers(userData.users || []);
      setTotal(userData.total || 0);
      setStats(statsData);
      setLastUpdated(new Date());
    } catch (requestError) {
      if (requestId !== requestSequence.current) return;
      setUsers([]);
      setTotal(0);
      setStats(EMPTY_STATS);
      setError(requestError instanceof Error ? requestError.message : '운영 데이터를 불러오지 못했습니다.');
    } finally {
      if (requestId !== requestSequence.current) return;
      setLoading(false);
      setRefreshing(false);
    }
  }, [deferredSearch, page, pageSize, program]);

  useEffect(() => { void loadData(false); }, [loadData]);
  useEffect(() => { setPage(1); }, [deferredSearch, program]);
  useEffect(() => {
    const timer = window.setInterval(() => void loadData(true), 60_000);
    return () => window.clearInterval(timer);
  }, [loadData]);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3600);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filteredUsers = useMemo(() => users.filter((user) => {
    if (filter === 'subscriber') return user.user_type === 'subscriber';
    if (filter === 'trial') return user.user_type === 'trial';
    if (filter === 'online') return user.is_online;
    if (filter === 'inactive') return !user.is_active;
    return true;
  }), [filter, users]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const activeProgram = PROGRAMS.find((item) => item.key === program) || PROGRAMS[0];

  async function openUser(user: User) {
    setSelectedUser(user);
    setHistory([]);
    setHistoryLoading(true);
    try {
      const [detail, historyData] = await Promise.all([
        apiRequest<User>(`users/${user.id}`),
        apiRequest<LoginHistoryResponse>(`users/${user.id}/history`),
      ]);
      setSelectedUser(detail);
      setHistory(historyData.history || []);
    } catch (requestError) {
      showToast(requestError instanceof Error ? requestError.message : '사용자 상세 정보를 불러오지 못했습니다.', 'error');
    } finally {
      setHistoryLoading(false);
    }
  }

  function showToast(message: string, tone: 'success' | 'error' = 'success') {
    setToast({ message, tone });
  }

  async function refreshSelected(userId: number) {
    const detail = await apiRequest<User>(`users/${userId}`);
    setSelectedUser(detail);
  }

  async function mutate(path: string, method: 'POST' | 'DELETE', successMessage: string, body?: object) {
    if (!selectedUser) return;
    setActionBusy(true);
    try {
      const result = await apiRequest<AdminActionResponse>(path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (result.success === false) throw new Error(safeApiMessage(result.message, '작업이 적용되지 않았습니다.'));
      showToast(successMessage);
      if (method === 'DELETE') {
        setSelectedUser(null);
      } else {
        await refreshSelected(selectedUser.id);
      }
      await loadData(true);
    } catch (requestError) {
      showToast(requestError instanceof Error ? requestError.message : '작업을 완료하지 못했습니다.', 'error');
    } finally {
      setActionBusy(false);
      setConfirm(null);
      setDeleteText('');
    }
  }

  async function extend(days: number) {
    if (!selectedUser || days < 1 || days > 3650) return;
    await mutate(`users/${selectedUser.id}/extend`, 'POST', `${selectedUser.username} 구독을 ${days}일 연장했습니다.`, { days });
  }

  async function executeConfirmed() {
    if (!selectedUser || !confirm) return;
    if (confirm.kind === 'toggle') {
      await mutate(`users/${selectedUser.id}/toggle-active`, 'POST', `${selectedUser.username} 계정을 ${selectedUser.is_active ? '비활성화' : '활성화'}했습니다.`);
    } else if (confirm.kind === 'revoke') {
      await mutate(`users/${selectedUser.id}/revoke-subscription`, 'POST', `${selectedUser.username} 구독을 회수했습니다.`);
    } else if (confirm.kind === 'reduce') {
      await mutate(`users/${selectedUser.id}/reduce-subscription`, 'POST', `${selectedUser.username} 구독을 ${confirm.days}일 축소했습니다.`, { days: confirm.days });
    } else if (confirm.kind === 'delete') {
      await mutate(`users/${selectedUser.id}`, 'DELETE', `${selectedUser.username} 사용자를 삭제했습니다.`);
    }
  }

  async function logout() {
    await fetch('/api/session/logout', { method: 'POST' }).catch(() => undefined);
    router.replace('/login');
    router.refresh();
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'open' : ''}`}>
        <div className="sidebar-head">
          <div className="brand-lockup">
            <span className="brand-mark"><Database size={20} /></span>
            <div><strong>SSMaker Ops</strong><small>Program DB Console</small></div>
          </div>
          <button className="icon-button mobile-only" aria-label="메뉴 닫기" onClick={() => setMobileNav(false)}><X size={19} /></button>
        </div>

        <nav className="primary-nav" aria-label="기본 메뉴">
          <span className="nav-label">OPERATIONS</span>
          <button className="nav-item active"><Gauge size={18} /> 운영 현황</button>
          <button className="nav-item"><Users size={18} /> 사용자 DB <span>{stats.users.total}</span></button>
          <button className="nav-item"><Activity size={18} /> 실시간 활동 <span>{stats.users.online}</span></button>
        </nav>

        <div className="program-nav">
          <span className="nav-label">PROGRAMS</span>
          {PROGRAMS.map((item) => (
            <button
              className={`program-item ${program === item.key ? 'active' : ''}`}
              key={item.key}
              onClick={() => { setProgram(item.key); setMobileNav(false); }}
            >
              <span className="program-avatar">{item.short}</span>
              <span>{item.label}</span>
              {program === item.key ? <Check size={15} /> : null}
            </button>
          ))}
        </div>

        <div className="sidebar-foot">
          <div className="secure-status"><ShieldCheck size={16} /><div><strong>운영 API 연결됨</strong><span>암호화 세션</span></div></div>
          <button className="nav-item logout" onClick={logout}><LogOut size={17} /> 로그아웃</button>
        </div>
      </aside>
      {mobileNav ? <button className="sidebar-backdrop" aria-label="메뉴 닫기" onClick={() => setMobileNav(false)} /> : null}

      <main className="main-content">
        <header className="topbar">
          <button className="icon-button mobile-only" aria-label="메뉴 열기" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
          <div className="topbar-title"><span className="eyebrow">LIVE DATABASE</span><h1>프로그램 사용자 운영</h1></div>
          <div className="topbar-actions">
            <div className="sync-state"><span className="live-dot" />{lastUpdated ? `${lastUpdated.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })} 갱신` : '연결 중'}</div>
            <button className="button secondary" onClick={() => void loadData(true)} disabled={refreshing}>
              <RefreshCw className={refreshing ? 'spin' : ''} size={16} /> 새로고침
            </button>
          </div>
        </header>

        <section className="content-area">
          <div className="section-intro">
            <div><p className="breadcrumb">프로그램 DB <span>/</span> {activeProgram.label}</p><h2>{activeProgram.label} 운영 현황</h2><p>사용자 상태와 구독, 작업 사용량을 실시간으로 관리합니다.</p></div>
            <div className="scope-badge"><Database size={16} /> AUTH PRODUCTION</div>
          </div>

          {error ? <div className="inline-alert"><AlertTriangle size={18} /><span>{error}</span><button onClick={() => void loadData(false)}>다시 시도</button></div> : null}

          <section className="metrics-grid" aria-label="운영 통계">
            <MetricCard label="전체 사용자" value={stats.users.total} meta={`${stats.users.active}명 활성`} icon={<Users size={20} />} tone="ink" />
            <MetricCard label="활성 구독" value={stats.users.with_subscription} meta={`${stats.users.total ? Math.round(stats.users.with_subscription / stats.users.total * 100) : 0}% 전환`} icon={<Sparkles size={20} />} tone="violet" />
            <MetricCard label="현재 온라인" value={stats.users.online} meta={`${stats.work.in_progress_users}명 작업 중`} icon={<Wifi size={20} />} tone="green" />
            <MetricCard label="누적 작업" value={stats.work.total_used.toLocaleString()} meta={`사용자당 평균 ${stats.work.avg_used_per_user}`} icon={<Activity size={20} />} tone="amber" />
          </section>

          <section className="data-panel">
            <div className="panel-head">
              <div><h3>사용자 DB</h3><p>검색 결과 {total.toLocaleString()}명</p></div>
              <div className="search-box"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="아이디, 이름, 이메일, 전화번호 검색" aria-label="사용자 검색" />{search ? <button aria-label="검색어 지우기" onClick={() => setSearch('')}><X size={15} /></button> : null}</div>
            </div>
            <div className="filter-row" role="group" aria-label="사용자 상태 필터">
              {([
                ['all', '전체'], ['subscriber', '구독자'], ['trial', '체험'], ['online', '온라인'], ['inactive', '비활성'],
              ] as Array<[FilterKey, string]>).map(([key, label]) => <button className={filter === key ? 'active' : ''} onClick={() => setFilter(key)} key={key}>{label}</button>)}
            </div>

            <div className="table-wrap">
              <table>
                <thead><tr><th>사용자</th><th>프로그램</th><th>플랜</th><th>작업 사용량</th><th>계정 상태</th><th>마지막 로그인</th><th>구독 만료</th><th><span className="sr-only">작업</span></th></tr></thead>
                <tbody>
                  {loading ? <TableSkeleton /> : filteredUsers.length ? filteredUsers.map((user) => {
                    const state = userState(user);
                    const expiry = parseApiDate(user.subscription_expires_at);
                    const expired = Boolean(expiry && expiry.getTime() < Date.now());
                    return (
                      <tr key={user.id} onClick={() => void openUser(user)} tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter') void openUser(user); }}>
                        <td><div className="user-cell"><span className="user-avatar">{user.username.slice(0, 2).toUpperCase()}</span><div><strong>{user.username}</strong><span>{user.name || user.email || `ID ${user.id}`}</span></div></div></td>
                        <td><span className="program-chip">{programLabel(user.program_type)}</span></td>
                        <td><span className={`status-pill ${user.user_type === 'subscriber' && !expired ? 'positive' : 'neutral'}`}>{user.user_type === 'subscriber' && !expired ? '구독' : '체험'}</span></td>
                        <td><div className="usage-cell"><strong>{user.work_used.toLocaleString()}</strong><span>{user.work_count === -1 ? '무제한' : `/ ${user.work_count}`}</span></div></td>
                        <td><span className={`status-pill ${state.tone}`}><i />{state.label}</span></td>
                        <td><span className="date-primary">{formatDate(user.last_login_at, true)}</span><small>{user.login_count.toLocaleString()}회 로그인</small></td>
                        <td><span className={expired ? 'date-danger' : 'date-primary'}>{formatDate(user.subscription_expires_at, true)}</span><small>{remainingLabel(user.subscription_expires_at)}</small></td>
                        <td><button className="icon-button" aria-label={`${user.username} 상세 보기`} onClick={(event) => { event.stopPropagation(); void openUser(user); }}><MoreHorizontal size={18} /></button></td>
                      </tr>
                    );
                  }) : <tr><td colSpan={8}><div className="empty-state"><Search size={24} /><strong>조건에 맞는 사용자가 없습니다</strong><span>검색어나 필터를 변경해 보세요.</span></div></td></tr>}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span>{total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} / ${total}` : '0명'}</span>
              <div><button className="icon-button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}><ChevronLeft size={17} /></button><span>{page} / {pageCount}</span><button className="icon-button" disabled={page >= pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}><ChevronRight size={17} /></button></div>
            </div>
          </section>
        </section>
      </main>

      {selectedUser ? (
        <>
          <button className="drawer-backdrop" aria-label="상세 패널 닫기" onClick={() => setSelectedUser(null)} />
          <aside className="user-drawer" aria-label={`${selectedUser.username} 사용자 상세`}>
            <div className="drawer-head"><div><span className="eyebrow">USER #{selectedUser.id}</span><h2>사용자 상세</h2></div><button className="icon-button" aria-label="닫기" onClick={() => setSelectedUser(null)}><X size={19} /></button></div>
            <div className="profile-hero">
              <span className="profile-avatar">{selectedUser.username.slice(0, 2).toUpperCase()}</span>
              <div><h3>{selectedUser.username}</h3><p>{selectedUser.name || '이름 미등록'} · {programLabel(selectedUser.program_type)}</p><div><span className={`status-pill ${selectedUser.is_active ? 'positive' : 'neutral'}`}><i />{selectedUser.is_active ? '활성 계정' : '비활성 계정'}</span>{selectedUser.is_online ? <span className="status-pill info"><i />온라인</span> : null}</div></div>
            </div>

            <div className="drawer-scroll">
              <section className="detail-section">
                <div className="detail-title"><h4>계정 정보</h4><span>{formatDate(selectedUser.created_at)} 가입</span></div>
                <dl className="detail-grid"><div><dt>이메일</dt><dd>{selectedUser.email || '—'}</dd></div><div><dt>전화번호</dt><dd>{selectedUser.phone || '—'}</dd></div><div><dt>앱 버전</dt><dd>{selectedUser.app_version || '—'}</dd></div><div><dt>마지막 IP</dt><dd>{selectedUser.last_login_ip || '—'}</dd></div></dl>
              </section>

              <section className="detail-section subscription-card">
                <div className="detail-title"><h4>구독 관리</h4><span className={`status-pill ${selectedUser.user_type === 'subscriber' ? 'positive' : 'neutral'}`}>{selectedUser.user_type === 'subscriber' ? '구독자' : '체험'}</span></div>
                <div className="expiry-block"><div><span>현재 만료일</span><strong>{formatDate(selectedUser.subscription_expires_at)}</strong></div><span>{remainingLabel(selectedUser.subscription_expires_at)}</span></div>
                <div className="quick-actions"><span>빠른 연장</span><div>{[7, 30, 90, 365].map((days) => <button key={days} disabled={actionBusy} onClick={() => void extend(days)}>+{days}일</button>)}</div></div>
                <div className="custom-action"><input type="number" min={1} max={3650} value={customDays} onChange={(event) => setCustomDays(Math.max(1, Number(event.target.value) || 1))} aria-label="구독 일수" /><button className="button primary" disabled={actionBusy} onClick={() => void extend(customDays)}>{actionBusy ? <LoaderCircle className="spin" size={15} /> : <ArrowUpFromLine size={15} />} 연장</button></div>
                <div className="secondary-actions"><button disabled={selectedUser.user_type !== 'subscriber'} onClick={() => setConfirm({ kind: 'reduce', title: '구독 기간 축소', description: `${selectedUser.username}의 구독을 ${customDays}일 줄입니다. 만료일이 지나면 체험 계정으로 전환됩니다.`, confirmLabel: `${customDays}일 축소`, days: customDays, danger: true })}><ArrowDownToLine size={15} /> {customDays}일 축소</button><button disabled={selectedUser.user_type !== 'subscriber'} onClick={() => setConfirm({ kind: 'revoke', title: '구독 회수', description: `${selectedUser.username}을 체험 계정으로 전환하고 작업 횟수를 초기화합니다.`, confirmLabel: '구독 회수', danger: true })}><Ban size={15} /> 구독 회수</button></div>
              </section>

              <section className="detail-section">
                <div className="detail-title"><h4>사용 현황</h4><span>{selectedUser.current_task || '대기 중'}</span></div>
                <div className="usage-summary"><div><Laptop size={18} /><span>작업 사용</span><strong>{selectedUser.work_used.toLocaleString()}</strong></div><div><Clock3 size={18} /><span>로그인 횟수</span><strong>{selectedUser.login_count.toLocaleString()}</strong></div></div>
              </section>

              <section className="detail-section">
                <div className="detail-title"><h4>최근 로그인 이력</h4><History size={16} /></div>
                <div className="history-list">{historyLoading ? <div className="history-loading"><LoaderCircle className="spin" size={17} /> 이력 불러오는 중</div> : history.length ? history.slice(0, 8).map((item) => <div className="history-item" key={item.id}><span className={item.success ? 'history-dot success' : 'history-dot failed'} /><div><strong>{item.success ? '로그인 성공' : '로그인 실패'}</strong><span>{item.ip_address}</span></div><time>{formatDate(item.attempted_at, true)}</time></div>) : <div className="empty-mini">로그인 이력이 없습니다.</div>}</div>
              </section>

              <section className="detail-section danger-zone">
                <div><h4>계정 제어</h4><p>운영에 영향을 주는 작업은 확인 후 적용됩니다.</p></div>
                <button className="button secondary" onClick={() => setConfirm({ kind: 'toggle', title: selectedUser.is_active ? '계정 비활성화' : '계정 활성화', description: `${selectedUser.username} 계정의 프로그램 접근을 ${selectedUser.is_active ? '차단' : '허용'}합니다.`, confirmLabel: selectedUser.is_active ? '비활성화' : '활성화', danger: selectedUser.is_active })}><Power size={15} /> {selectedUser.is_active ? '비활성화' : '활성화'}</button>
                <button className="button danger" onClick={() => setConfirm({ kind: 'delete', title: '사용자 영구 삭제', description: '이 작업은 되돌릴 수 없습니다. 확인을 위해 사용자명을 정확히 입력해야 합니다.', confirmLabel: '영구 삭제', danger: true })}><Trash2 size={15} /> 사용자 삭제</button>
              </section>
            </div>
          </aside>
        </>
      ) : null}

      {confirm && selectedUser ? <ConfirmDialog state={confirm} username={selectedUser.username} deleteText={deleteText} setDeleteText={setDeleteText} busy={actionBusy} onCancel={() => { setConfirm(null); setDeleteText(''); }} onConfirm={() => void executeConfirmed()} /> : null}
      {toast ? <div className={`toast ${toast.tone}`} role="status">{toast.tone === 'success' ? <UserCheck size={18} /> : <AlertTriangle size={18} />}<span>{toast.message}</span><button onClick={() => setToast(null)} aria-label="알림 닫기"><X size={15} /></button></div> : null}
    </div>
  );
}

function MetricCard({ label, value, meta, icon, tone }: { label: string; value: string | number; meta: string; icon: React.ReactNode; tone: string }) {
  return <article className="metric-card"><div className={`metric-icon ${tone}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{meta}</small></div></article>;
}

function TableSkeleton() {
  return <>{Array.from({ length: 6 }, (_, index) => <tr className="skeleton-row" key={index}><td colSpan={8}><div /></td></tr>)}</>;
}

function ConfirmDialog({ state, username, deleteText, setDeleteText, busy, onCancel, onConfirm }: { state: NonNullable<ConfirmState>; username: string; deleteText: string; setDeleteText: (value: string) => void; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const deleteBlocked = state.kind === 'delete' && deleteText !== username;
  return <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><div className="confirm-card"><div className={`state-icon ${state.danger ? 'danger' : ''}`}>{state.kind === 'delete' ? <Trash2 size={22} /> : <AlertTriangle size={22} />}</div><h3 id="confirm-title">{state.title}</h3><p>{state.description}</p>{state.kind === 'delete' ? <label className="confirm-input"><span>확인을 위해 <strong>{username}</strong> 입력</span><input value={deleteText} onChange={(event) => setDeleteText(event.target.value)} autoFocus /></label> : null}<div className="confirm-actions"><button className="button secondary" disabled={busy} onClick={onCancel}>취소</button><button className={`button ${state.danger ? 'danger' : 'primary'}`} disabled={busy || deleteBlocked} onClick={onConfirm}>{busy ? <LoaderCircle className="spin" size={16} /> : null}{state.confirmLabel}</button></div></div></div>;
}
