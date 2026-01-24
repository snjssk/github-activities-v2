import { useEffect, useState } from 'react';
import {
  Card,
  Title,
  Text,
  Select,
  SelectItem,
  Grid,
  Metric,
  Badge,
  AreaChart,
  BarList,
} from '@tremor/react';
import {
  api,
  User,
  SummaryResponse,
  WeeklyResponse,
  ComparisonResponse,
} from '../api/client';

interface DashboardProps {
  users: User[];
  selectedUser: string;
  onUserChange: (user: string) => void;
}

// Color scheme for activity types
const ACTIVITY_COLORS = {
  commit: 'emerald',
  pr_opened: 'blue',
  pr_merged: 'violet',
  review: 'amber',
  issue_opened: 'cyan',
  issue_closed: 'slate',
} as const;

function formatChange(value: number): string {
  if (value > 0) return `+${value}`;
  return value.toString();
}

function getChangeColor(value: number): 'green' | 'red' | 'gray' {
  if (value > 0) return 'green';
  if (value < 0) return 'red';
  return 'gray';
}

function getCurrentWeekLabel(): string {
  const now = new Date();
  const startOfYear = new Date(now.getFullYear(), 0, 1);
  const days = Math.floor((now.getTime() - startOfYear.getTime()) / (24 * 60 * 60 * 1000));
  const weekNum = Math.ceil((days + startOfYear.getDay() + 1) / 7);
  return `${now.getFullYear()}-W${weekNum.toString().padStart(2, '0')}`;
}

function getCurrentMonthLabel(): string {
  const now = new Date();
  return `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}`;
}

export default function Dashboard({ users, selectedUser, onUserChange }: DashboardProps) {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [weekly, setWeekly] = useState<WeeklyResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [compareUsers, setCompareUsers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedUser) return;

    setLoading(true);
    // Get last 4 weeks of data (to avoid gaps in historical data)
    const today = new Date();
    const fourWeeksAgo = new Date(today.getTime() - 28 * 24 * 60 * 60 * 1000);
    const fromDate = fourWeeksAgo.toISOString().split('T')[0];
    const toDate = today.toISOString().split('T')[0];

    Promise.all([
      api.getSummary(selectedUser),
      api.getWeeklyActivities(selectedUser, fromDate, toDate),
    ])
      .then(([summaryData, weeklyData]) => {
        setSummary(summaryData);
        setWeekly(weeklyData);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch data:', err);
        setLoading(false);
      });
  }, [selectedUser]);

  useEffect(() => {
    if (compareUsers.length > 0) {
      api.getComparison(compareUsers, 'weekly')
        .then(setComparison)
        .catch(console.error);
    } else {
      setComparison(null);
    }
  }, [compareUsers]);

  const handleCompareToggle = (username: string) => {
    setCompareUsers((prev) =>
      prev.includes(username)
        ? prev.filter((u) => u !== username)
        : [...prev, username]
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen p-8">
        <div className="text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  const formatDateRange = (startDate: string, endDate: string): string => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const startStr = `${start.getMonth() + 1}/${start.getDate()}`;
    const endStr = `${end.getMonth() + 1}/${end.getDate()}`;
    return `${startStr}~${endStr}`;
  };

  const chartData = weekly?.data.map((d) => ({
    week: formatDateRange(d.start_date, d.end_date),
    Commit: d.commit,
    'PR Opened': d.pr_opened,
    'PR Merged': d.pr_merged,
    Review: d.review,
    'Issue Opened': d.issue_opened,
    'Issue Closed': d.issue_closed,
    Total: d.total,
  })) || [];

  const breakdownData = summary ? [
    { name: 'Commits', value: summary.this_week.commit, color: ACTIVITY_COLORS.commit },
    { name: 'PR Opened', value: summary.this_week.pr_opened, color: ACTIVITY_COLORS.pr_opened },
    { name: 'PR Merged', value: summary.this_week.pr_merged, color: ACTIVITY_COLORS.pr_merged },
    { name: 'Reviews', value: summary.this_week.review, color: ACTIVITY_COLORS.review },
    { name: 'Issue Opened', value: summary.this_week.issue_opened, color: ACTIVITY_COLORS.issue_opened },
    { name: 'Issue Closed', value: summary.this_week.issue_closed, color: ACTIVITY_COLORS.issue_closed },
  ] : [];

  const comparisonData = comparison?.users.map((u) => ({
    name: u.username,
    value: u.total,
  })) || [];

  const currentWeek = getCurrentWeekLabel();
  const currentMonth = getCurrentMonthLabel();

  // Get this week's date range from the last item in weekly data
  const thisWeekRange = weekly?.data.length
    ? formatDateRange(weekly.data[weekly.data.length - 1].start_date, weekly.data[weekly.data.length - 1].end_date)
    : '';

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">GitHub Activities Dashboard</h1>
          <p className="text-lg font-semibold text-gray-600 mt-1">
            Track and visualize development activities
          </p>
          {thisWeekRange && (
            <p className="text-sm text-gray-500 mt-1">
              Latest period: {weekly?.data[weekly.data.length - 1]?.start_date} ~ {weekly?.data[weekly.data.length - 1]?.end_date}
            </p>
          )}
        </div>
        <Select value={selectedUser} onValueChange={onUserChange} className="w-48">
          {users.map((user) => (
            <SelectItem key={user.username} value={user.username}>
              {user.display_name || user.username}
            </SelectItem>
          ))}
        </Select>
      </div>

      {/* KPI Cards */}
      <Grid numItems={1} numItemsSm={2} numItemsLg={5} className="gap-4 mb-8">
        <Card className="border-2 border-indigo-500">
          <p className="font-bold text-gray-700">Monthly ({currentMonth})</p>
          <Metric>{summary?.this_month.total || 0}</Metric>
          <Badge color={getChangeColor(summary?.month_change.total || 0)}>
            {formatChange(summary?.month_change.total || 0)} vs last month
          </Badge>
        </Card>
        <Card className="border-2 border-blue-500">
          <p className="font-bold text-gray-700">Activity</p>
          <Metric>{summary?.this_week.total || 0}</Metric>
          <Badge color={getChangeColor(summary?.week_change.total || 0)}>
            {formatChange(summary?.week_change.total || 0)} vs last week
          </Badge>
        </Card>
        <Card className="border-2 border-emerald-500">
          <p className="font-bold text-gray-700">Commits</p>
          <Metric>{summary?.this_week.commit || 0}</Metric>
          <Badge color={getChangeColor(summary?.week_change.commit || 0)}>
            {formatChange(summary?.week_change.commit || 0)} vs last week
          </Badge>
        </Card>
        <Card className="border-2 border-blue-500">
          <p className="font-bold text-gray-700">PRs</p>
          <Metric>{summary?.this_week.pr_opened || 0}</Metric>
          <Badge color={getChangeColor(summary?.week_change.pr_opened || 0)}>
            {formatChange(summary?.week_change.pr_opened || 0)} vs last week
          </Badge>
        </Card>
        <Card className="border-2 border-amber-500">
          <p className="font-bold text-gray-700">Reviews</p>
          <Metric>{summary?.this_week.review || 0}</Metric>
          <Badge color={getChangeColor(summary?.week_change.review || 0)}>
            {formatChange(summary?.week_change.review || 0)} vs last week
          </Badge>
        </Card>
      </Grid>

      {/* Weekly Trend Chart */}
      <Card className="mb-8 border-2 border-gray-200">
        <h2 className="text-xl font-bold text-gray-900">Weekly Activity Trend</h2>
        <AreaChart
          className="mt-4 h-72"
          data={chartData}
          index="week"
          categories={['Total', 'PR Opened', 'Review', 'Issue Opened']}
          colors={['indigo', 'blue', 'orange', 'teal']}
          yAxisWidth={40}
          showAnimation={true}
          curveType="monotone"
        />
      </Card>

      {/* Activity Breakdown and Comparison */}
      <Grid numItems={1} numItemsLg={2} className="gap-8">
        {/* Activity Breakdown */}
        <Card className="border-2 border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Activity Breakdown ({thisWeekRange})</h2>
          <BarList
            data={breakdownData}
            className="mt-4"
          />
        </Card>

        {/* Member Comparison */}
        <Card className="border-2 border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Member Comparison</h2>
          <Text className="mb-4">Select users to compare</Text>
          <div className="flex flex-wrap gap-2 mb-4">
            {users.map((user) => (
              <button
                key={user.username}
                onClick={() => handleCompareToggle(user.username)}
                className={`px-3 py-1 rounded-full text-sm ${
                  compareUsers.includes(user.username)
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                {user.display_name || user.username}
              </button>
            ))}
          </div>
          {comparisonData.length > 0 && (
            <BarList data={comparisonData} className="mt-4" color="blue" />
          )}
          {comparisonData.length === 0 && (
            <Text className="text-gray-400 mt-4">
              Select users above to compare activities
            </Text>
          )}
        </Card>
      </Grid>
    </div>
  );
}
