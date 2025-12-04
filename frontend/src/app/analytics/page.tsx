'use client';

/**
 * BI Analytics Dashboard Page
 * 
 * This page displays basic usage analytics for the Colink application:
 * - Total counts of users, channels, and messages
 * - Top 5 channels by message count
 * - Daily message counts for the last 7 days
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { analyticsApi } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { 
  BarChart3, 
  Users, 
  Hash, 
  MessageSquare, 
  ArrowLeft,
  TrendingUp,
  Shield,
  Activity,
  Clock
} from 'lucide-react';
import Link from 'next/link';

// ============================================================================
// Types for Analytics API Response
// ============================================================================

interface Totals {
  total_users: number;
  total_channels: number;
  total_messages: number;
  active_users_today: number;
  messages_today: number;
  avg_messages_per_day: number;
}

interface TopChannel {
  channel_id: string;
  channel_name: string;
  message_count: number;
  member_count: number;
}

interface DailyMessage {
  date: string;
  count: number;
}

interface TopUser {
  user_id: string;
  username: string;
  display_name: string;
  message_count: number;
}

interface ChannelDistribution {
  public: number;
  private: number;
  direct: number;
}

interface HourlyActivity {
  hour: number;
  count: number;
}

interface AnalyticsSummary {
  totals: Totals;
  top_channels: TopChannel[];
  daily_messages: DailyMessage[];
  top_users: TopUser[];
  channel_distribution: ChannelDistribution;
  hourly_activity: HourlyActivity[];
}

// ============================================================================
// Analytics Dashboard Component
// ============================================================================

export default function AnalyticsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  // Check if user is admin
  const isAdmin = user?.role?.toUpperCase() === 'ADMIN';

  // Redirect to login if not authenticated, or to channels if not admin
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    } else if (user && !isAdmin) {
      router.push('/channels');
    }
  }, [isAuthenticated, user, isAdmin, router]);

  // Fetch analytics data from message service (only if admin)
  const { data: analytics, isLoading, error } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: async () => {
      return await analyticsApi.get<AnalyticsSummary>('/analytics/summary');
    },
    enabled: isAuthenticated && isAdmin,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (!isAuthenticated || !isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <Shield className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600 mb-4">Only administrators can access the analytics dashboard.</p>
          <Link 
            href="/channels" 
            className="text-purple-600 hover:text-purple-700 font-medium"
          >
            ← Back to Channels
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <BarChart3 className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Unable to Load Analytics</h2>
          <p className="text-gray-600 mb-4">There was an error loading the analytics data.</p>
          <Link 
            href="/channels" 
            className="text-purple-600 hover:text-purple-700 font-medium"
          >
            ← Back to Channels
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <Link
                href="/channels"
                className="flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="h-5 w-5 mr-1" />
                Back
              </Link>
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-6 w-6 text-purple-600" />
                <h1 className="text-xl font-semibold text-gray-900">BI Analytics Dashboard</h1>
              </div>
            </div>
            <div className="text-sm text-gray-500">
              Last updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Primary Stats Cards Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          {/* Total Users Card */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-blue-100">
                <Users className="h-5 w-5 text-blue-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Total Users</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.total_users ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Active Users Today */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-green-100">
                <Activity className="h-5 w-5 text-green-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Active Today</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.active_users_today ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Total Channels Card */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-indigo-100">
                <Hash className="h-5 w-5 text-indigo-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Channels</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.total_channels ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Total Messages Card */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-purple-100">
                <MessageSquare className="h-5 w-5 text-purple-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Messages</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.total_messages ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Messages Today */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-orange-100">
                <TrendingUp className="h-5 w-5 text-orange-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Msgs Today</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.messages_today ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Avg Messages/Day */}
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center">
              <div className="p-2 rounded-full bg-pink-100">
                <BarChart3 className="h-5 w-5 text-pink-600" />
              </div>
              <div className="ml-3">
                <p className="text-xs font-medium text-gray-500">Avg/Day</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics?.totals.avg_messages_per_day?.toFixed(1) ?? '0'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Channel Distribution Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shadow p-4 text-white">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-blue-100 text-sm">Public Channels</p>
                <p className="text-3xl font-bold">{analytics?.channel_distribution?.public ?? 0}</p>
              </div>
              <Hash className="h-10 w-10 text-blue-200 opacity-80" />
            </div>
          </div>
          <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg shadow p-4 text-white">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-purple-100 text-sm">Private Channels</p>
                <p className="text-3xl font-bold">{analytics?.channel_distribution?.private ?? 0}</p>
              </div>
              <Shield className="h-10 w-10 text-purple-200 opacity-80" />
            </div>
          </div>
          <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg shadow p-4 text-white">
            <div className="flex justify-between items-center">
              <div>
                <p className="text-green-100 text-sm">Direct Messages</p>
                <p className="text-3xl font-bold">{analytics?.channel_distribution?.direct ?? 0}</p>
              </div>
              <MessageSquare className="h-10 w-10 text-green-200 opacity-80" />
            </div>
          </div>
        </div>

        {/* Two Column Layout for Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Top Channels Table */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center space-x-2">
                <TrendingUp className="h-5 w-5 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">Top Channels</h2>
              </div>
              <p className="text-sm text-gray-500 mt-1">Channels with most messages</p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Channel
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Members
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Messages
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {analytics?.top_channels && analytics.top_channels.length > 0 ? (
                    analytics.top_channels.map((channel, index) => (
                      <tr key={channel.channel_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold mr-3 ${
                              index === 0 ? 'bg-yellow-100 text-yellow-700' :
                              index === 1 ? 'bg-gray-100 text-gray-700' :
                              index === 2 ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-50 text-gray-500'
                            }`}>
                              {index + 1}
                            </span>
                            <Hash className="h-4 w-4 text-gray-400 mr-2" />
                            <span className="text-sm font-medium text-gray-900">
                              {channel.channel_name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <span className="text-sm text-gray-500">
                            {channel.member_count}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            {channel.message_count}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={3} className="px-6 py-8 text-center text-gray-500">
                        No channel data available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top Users Table */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center space-x-2">
                <Users className="h-5 w-5 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">Most Active Users</h2>
              </div>
              <p className="text-sm text-gray-500 mt-1">Users with most messages</p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Messages
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {analytics?.top_users && analytics.top_users.length > 0 ? (
                    analytics.top_users.map((user, index) => (
                      <tr key={user.user_id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold mr-3 ${
                              index === 0 ? 'bg-yellow-100 text-yellow-700' :
                              index === 1 ? 'bg-gray-100 text-gray-700' :
                              index === 2 ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-50 text-gray-500'
                            }`}>
                              {index + 1}
                            </span>
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center text-white font-semibold text-xs mr-3">
                              {user.display_name?.charAt(0).toUpperCase() || user.username?.charAt(0).toUpperCase() || '?'}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-gray-900">
                                {user.display_name || user.username}
                              </p>
                              <p className="text-xs text-gray-500">@{user.username}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {user.message_count}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={2} className="px-6 py-8 text-center text-gray-500">
                        No user data available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Activity Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Daily Messages Chart */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center space-x-2">
                <BarChart3 className="h-5 w-5 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">Daily Messages</h2>
              </div>
              <p className="text-sm text-gray-500 mt-1">Message activity over the last 7 days</p>
            </div>
            <div className="p-6">
              <div className="space-y-3">
                {analytics?.daily_messages && analytics.daily_messages.length > 0 ? (
                  analytics.daily_messages.map((day) => {
                    const maxCount = Math.max(
                      ...analytics.daily_messages.map((d) => d.count),
                      1
                    );
                    const barWidth = (day.count / maxCount) * 100;
                    const dateObj = new Date(day.date + 'T00:00:00');
                    const formattedDate = dateObj.toLocaleDateString('en-US', {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                    });

                    return (
                      <div key={day.date} className="flex items-center space-x-4">
                        <div className="w-24 text-sm text-gray-600 flex-shrink-0">
                          {formattedDate}
                        </div>
                        <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-purple-400 to-purple-600 h-full rounded-full transition-all duration-300"
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                        <div className="w-12 text-right text-sm font-medium text-gray-900">
                          {day.count}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    No message data available
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Hourly Activity Chart */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center space-x-2">
                <Clock className="h-5 w-5 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">Hourly Activity</h2>
              </div>
              <p className="text-sm text-gray-500 mt-1">Message distribution by hour (24h)</p>
            </div>
            <div className="p-6">
              <div className="flex items-end justify-between space-x-1 h-40">
                {analytics?.hourly_activity && analytics.hourly_activity.length > 0 ? (
                  analytics.hourly_activity.map((hour) => {
                    const maxCount = Math.max(
                      ...analytics.hourly_activity.map((h) => h.count),
                      1
                    );
                    const barHeight = (hour.count / maxCount) * 100;
                    const formattedHour = hour.hour === 0 ? '12am' : 
                                          hour.hour === 12 ? '12pm' :
                                          hour.hour < 12 ? `${hour.hour}am` : `${hour.hour - 12}pm`;

                    return (
                      <div key={hour.hour} className="flex flex-col items-center flex-1">
                        <div className="w-full flex items-end justify-center h-32">
                          <div
                            className="w-full max-w-[20px] bg-gradient-to-t from-blue-400 to-blue-600 rounded-t transition-all duration-300 hover:from-blue-500 hover:to-blue-700"
                            style={{ height: `${Math.max(barHeight, 4)}%` }}
                            title={`${formattedHour}: ${hour.count} messages`}
                          />
                        </div>
                        {hour.hour % 4 === 0 && (
                          <span className="text-xs text-gray-500 mt-1">{formattedHour}</span>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="w-full text-center text-gray-500 py-8">
                    No hourly data available
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer Note */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Analytics data is refreshed every 30 seconds automatically.</p>
        </div>
      </main>
    </div>
  );
}
