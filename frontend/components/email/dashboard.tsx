import React, { useState, useEffect, useCallback } from 'react';
import { Mail, CheckCircle, AlertCircle, Send, MessageSquare } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { TimeframeSelector } from '@/components/ui/timeframe-selector';
import RecentEmails  from '@/components/ui/recent-emails';

interface EmailStats {
  total: number;
  read: number;
  unread: number;
  replied: number;
  drafted: number;
}

interface RecentEmail {
  id: string;
  subject: string;
  sender: string;
  timestamp: string;
  isRead: boolean;
  isStarred: boolean;
}

interface DashboardProps {
  selectedAccount: {
    email: string;
    service: string;
  } | null;
}

const StatsCard: React.FC<{ title: string; value: number; icon: React.ReactNode; loading?: boolean }> = ({ 
  title, value, icon, loading 
}) => (
  <Card>
    <CardContent className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">
            {loading ? (
              <span className="inline-block w-8 h-8 bg-gray-200 animate-pulse rounded" />
            ) : (
              value
            )}
          </p>
        </div>
        {loading ? (
          <div className="w-8 h-8 bg-gray-200 animate-pulse rounded-full" />
        ) : (
          icon
        )}
      </div>
    </CardContent>
  </Card>
);

const EmailDashboard: React.FC<DashboardProps> = ({ selectedAccount }) => {
  const [stats, setStats] = useState<EmailStats>({
    total: 0,
    read: 0,
    unread: 0,
    replied: 0,
    drafted: 0,
  });
  const [recentEmails, setRecentEmails] = useState<RecentEmail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentHours, setCurrentHours] = useState("24");

  const TIMEOUT_DURATION = 300000;

  const fetchData = useCallback(async (hours: string) => {
    if (!selectedAccount) return;

    setLoading(true);
    setError(null);

    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort();
    }, TIMEOUT_DURATION);

    try {
      const hoursNum = parseInt(hours);
      if (hoursNum > 720) {
        setError('Warning: Large time ranges may take longer to load');
      }

      const params = new URLSearchParams({
        service: selectedAccount.service,
        hours: hours,
        account: selectedAccount.email
      });

      // Fetch stats
      const statsResponse = await fetch(`/api/email-stats?${params}`, {
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });

      // Fetch recent emails
      const emailsResponse = await fetch(`/api/recent-emails?${params}`, {
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        }
      });

      if (!statsResponse.ok || !emailsResponse.ok) {
        const errorData = await statsResponse.json().catch(() => null) || 
                         await emailsResponse.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to fetch data');
      }

      const statsData = await statsResponse.json();
      const emailsData = await emailsResponse.json();

      setStats(statsData);
      setRecentEmails(emailsData);
      setCurrentHours(hours);
      setError(null);
    } catch (error: any) {
      if (error.name === 'AbortError') {
        setError('Request timed out after 5 minutes. Try a smaller time range or try again.');
      } else {
        setError(error.message || 'Failed to fetch data');
        setStats({
          total: 0,
          read: 0,
          unread: 0,
          replied: 0,
          drafted: 0,
        });
        setRecentEmails([]);
      }
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }, [selectedAccount]);

  useEffect(() => {
    if (selectedAccount) {
      fetchData(currentHours);
    }
  }, [selectedAccount, fetchData]);

  const handleTimeframeChange = (hours: string) => {
    fetchData(hours);
  };

  if (!selectedAccount) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">Select an email account to view statistics</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 relative">
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Email Statistics</h1>
              <p className="mt-1 text-sm text-gray-600">
                {selectedAccount.email} ({selectedAccount.service})
              </p>
            </div>
            <TimeframeSelector 
              onTimeframeChange={handleTimeframeChange}
              defaultValue={currentHours}
              defaultUnit={parseInt(currentHours) >= 24 ? 'hours' : 'days'}
              isLoading={loading}
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className={`flex items-center px-4 py-3 rounded relative ${
            error.startsWith('Warning') 
              ? 'bg-yellow-50 border border-yellow-200 text-yellow-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            <AlertCircle className="h-5 w-5 mr-2" />
            {error}
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
          <StatsCard
            title="Total Received"
            value={stats.total}
            icon={<Mail className="h-8 w-8 text-blue-500" />}
            loading={loading}
          />
          <StatsCard
            title="Read"
            value={stats.read}
            icon={<CheckCircle className="h-8 w-8 text-green-500" />}
            loading={loading}
          />
          <StatsCard
            title="Unread"
            value={stats.unread}
            icon={<AlertCircle className="h-8 w-8 text-red-500" />}
            loading={loading}
          />
          <StatsCard
            title="Replied"
            value={stats.replied}
            icon={<Send className="h-8 w-8 text-blue-500" />}
            loading={loading}
          />
          <StatsCard
            title="Drafted"
            value={stats.drafted}
            icon={<MessageSquare className="h-8 w-8 text-purple-500" />}
            loading={loading}
          />
        </div>

        <RecentEmails emails={recentEmails} />
      </div>
    </div>
  );
};

export default EmailDashboard;