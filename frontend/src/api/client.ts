/**
 * API client for GitHub Activities backend
 */

const API_BASE = '/api';

export interface User {
  id: number;
  username: string;
  display_name: string | null;
  last_collected_at: string | null;
  collect_from_date: string | null;
  activity_count: number;
}

export interface ActivityBreakdown {
  commit: number;
  pr_opened: number;
  pr_merged: number;
  review: number;
  issue_opened: number;
  issue_closed: number;
  total: number;
}

export interface WeeklyData {
  week: string;
  start_date: string;
  end_date: string;
  commit: number;
  pr_opened: number;
  pr_merged: number;
  review: number;
  issue_opened: number;
  issue_closed: number;
  total: number;
}

export interface MonthlyData {
  month: string;
  commit: number;
  pr_opened: number;
  pr_merged: number;
  review: number;
  issue_opened: number;
  issue_closed: number;
  total: number;
}

export interface WeeklyResponse {
  user: string;
  period: string;
  data: WeeklyData[];
}

export interface MonthlyResponse {
  user: string;
  period: string;
  data: MonthlyData[];
}

export interface SummaryResponse {
  user: string;
  this_week: ActivityBreakdown;
  last_week: ActivityBreakdown;
  this_month: ActivityBreakdown;
  last_month: ActivityBreakdown;
  week_change: ActivityBreakdown;
  month_change: ActivityBreakdown;
}

export interface ComparisonData {
  username: string;
  total: number;
  breakdown: ActivityBreakdown;
}

export interface ComparisonResponse {
  period: string;
  from_date: string;
  to_date: string;
  users: ComparisonData[];
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export const api = {
  async getUsers(): Promise<User[]> {
    return fetchJson<User[]>(`${API_BASE}/users`);
  },

  async getUser(username: string): Promise<User> {
    return fetchJson<User>(`${API_BASE}/users/${username}`);
  },

  async getWeeklyActivities(
    username: string,
    from?: string,
    to?: string
  ): Promise<WeeklyResponse> {
    const params = new URLSearchParams();
    params.set('user', username);
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    return fetchJson<WeeklyResponse>(`${API_BASE}/activities/weekly?${params}`);
  },

  async getMonthlyActivities(
    username: string,
    year?: number
  ): Promise<MonthlyResponse> {
    const params = new URLSearchParams();
    params.set('user', username);
    if (year) params.set('year', year.toString());
    return fetchJson<MonthlyResponse>(`${API_BASE}/activities/monthly?${params}`);
  },

  async getSummary(username: string): Promise<SummaryResponse> {
    return fetchJson<SummaryResponse>(`${API_BASE}/activities/summary?user=${username}`);
  },

  async getComparison(
    users: string[],
    period: 'weekly' | 'monthly' = 'weekly',
    from?: string,
    to?: string
  ): Promise<ComparisonResponse> {
    const params = new URLSearchParams();
    params.set('users', users.join(','));
    params.set('period', period);
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    return fetchJson<ComparisonResponse>(`${API_BASE}/activities/comparison?${params}`);
  },
};
