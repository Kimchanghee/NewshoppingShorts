export type ProgramKey = 'all' | 'ssmaker' | 'stmaker' | 'pineoptimizer' | 'subblur' | 'fitshot' | 'locationalarm';

export type User = {
  id: number;
  username: string;
  email?: string | null;
  phone?: string | null;
  name?: string | null;
  created_at?: string | null;
  subscription_expires_at?: string | null;
  is_active: boolean;
  last_login_at?: string | null;
  last_login_ip?: string | null;
  login_count: number;
  work_count: number;
  work_used: number;
  user_type: string;
  program_type: string;
  is_online: boolean;
  last_heartbeat?: string | null;
  current_task?: string | null;
  app_version?: string | null;
};

export type UserListResponse = { users: User[]; total: number };

export type StatsResponse = {
  users: { total: number; active: number; online: number; with_subscription: number };
  work: { total_used: number; users_with_work: number; in_progress_users: number; avg_used_per_user: number };
  registration_requests?: { pending: number; approved: number; rejected: number };
};

export type LoginHistory = {
  id: number;
  username: string;
  program_type?: string;
  ip_address: string;
  attempted_at: string;
  success: boolean;
};

export type LoginHistoryResponse = { history: LoginHistory[] };

export type AdminActionResponse = {
  success: boolean;
  message?: string;
  data?: Record<string, unknown> | null;
};
