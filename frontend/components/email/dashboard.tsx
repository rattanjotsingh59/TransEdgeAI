import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Mail, CheckCircle, AlertCircle, Send, MessageSquare, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface EmailStats {
  total: number;
  read: number;
  unread: number;
  replied: number;
  drafted: number;
  avgResponse: number;
}

interface ActivityData {
  time: string;
  emails: number;
  hour: number;
}

interface DashboardProps {
  selectedAccount: string | null;
}

const defaultStats: EmailStats = {
  total: 0,
  read: 0,
  unread: 0,
  replied: 0,
  drafted: 0,
  avgResponse: 0,
};

const formatResponseTime = (hours: number): string => {
  if (!hours || hours === 0) return '0';
  if (hours < 1) {
    const minutes = Math.round(hours * 60);
    return `${minutes}m`;
  }
  if (hours < 24) {
    return `${Math.round(hours)}h`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = Math.round(hours % 24);
  if (remainingHours === 0) {
    return `${days}d`;
  }
  return `${days}d ${remainingHours}h`;
};

const EmailDashboard: React.FC<DashboardProps> = ({ selectedAccount }) => {
  const [stats, setStats] = useState<EmailStats>(defaultStats);
  const [timeValue, setTimeValue] = useState<string>('24');
  const [tempTimeValue, setTempTimeValue] = useState(timeValue);
  const [timeUnit, setTimeUnit] = useState<'hours' | 'days'>('hours');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activityData, setActivityData] = useState<ActivityData[]>([]);
  const [activityLoading, setActivityLoading] = useState<boolean>(false);
  const isInitialMount = useRef(true);
  const timeInputRef = useRef<HTMLInputElement>(null);

  const getHours = useCallback(() => {
    const value = parseInt(timeValue);
    if (isNaN(value)) return 24; // Default to 24 if invalid
    return timeUnit === 'days' ? value * 24 : value;
  }, [timeValue, timeUnit]);

  const fetchEmailActivity = useCallback(async () => {
    try {
      setActivityLoading(true);
      const hours = getHours();
      const response = await fetch(`/api/email-activity?hours=${hours}`, {
        signal: AbortSignal.timeout(300000) // 5 minute timeout
      });
      if (!response.ok) throw new Error('Failed to fetch activity data');
      const data = await response.json();
      setActivityData(data);
    } catch (err: unknown) {
      const error = err as Error;
      if (error.name === 'TimeoutError') {
        console.error('Activity data request timed out');
      } else {
        console.error('Error fetching activity data:', error);
      }
    } finally {
      setActivityLoading(false);
    }
  }, [getHours]);

  const fetchEmailStats = useCallback(async () => {
    if (!timeValue || parseInt(timeValue) <= 0) return;

    try {
      setLoading(true);
      setError(null);
      
      const hours = getHours();
      const params = new URLSearchParams({
        hours: hours.toString(),
        ...(selectedAccount && { account: selectedAccount })
      });

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes

      try {
        const response = await fetch(`/api/email-stats?${params}`, {
          headers: {
            'Accept': 'application/json',
          },
          signal: controller.signal
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          let errorMessage = 'An error occurred while fetching data';
          
          if (response.status === 504) {
            errorMessage = 'Request timed out. Try a smaller time range or try again.';
          } else if (errorData?.detail) {
            errorMessage = errorData.detail;
          }
          
          throw new Error(errorMessage);
        }
        
        const data = await response.json();
        setStats({
          total: data.total ?? 0,
          read: data.read ?? 0,
          unread: data.unread ?? 0,
          replied: data.replied ?? 0,
          drafted: data.drafted ?? 0,
          avgResponse: data.avgResponse ?? 0
        });

        await fetchEmailActivity();
      } finally {
        clearTimeout(timeoutId);
      }
    } catch (err: unknown) {
      const error = err as Error;
      if (error.name === 'AbortError') {
        setError('Request timed out. For large time ranges, try using a smaller range or try again.');
      } else {
        setError(error.message || 'An error occurred while fetching data');
      }
      console.error('Error fetching email stats:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, timeValue, getHours, fetchEmailActivity]);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      fetchEmailStats();
    }
  }, [fetchEmailStats]);


  const handleTimeValueSubmit = () => {
    const newValue = tempTimeValue;
    if (newValue && parseInt(newValue) > 0) {
      setTimeValue(newValue);
      fetchEmailStats();
    }
  };

  const handleTimeValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    if (newValue === '' || parseInt(newValue) > 0) {
      setTempTimeValue(newValue);
    }
  };

  const handleTimeValueKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleTimeValueSubmit();
      timeInputRef.current?.blur();
    }
  };

  const handleTimeValueBlur = () => {
    handleTimeValueSubmit();
  };

  const handleTimeUnitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newUnit = e.target.value as 'hours' | 'days';
    setTimeUnit(newUnit);
    
    // Convert the current value based on the new unit
    const currentHours = parseInt(timeValue);
    if (!isNaN(currentHours)) {
      if (newUnit === 'days' && timeUnit === 'hours') {
        // Converting from hours to days
        setTimeValue(Math.max(1, Math.floor(currentHours / 24)).toString());
        setTempTimeValue(Math.max(1, Math.floor(currentHours / 24)).toString());
      } else if (newUnit === 'hours' && timeUnit === 'days') {
        // Converting from days to hours
        setTimeValue((currentHours * 24).toString());
        setTempTimeValue((currentHours * 24).toString());
      }
    }
    
    // Only trigger fetch after state updates
    setTimeout(() => {
      fetchEmailStats();
    }, 0);
  };

  if (loading && isInitialMount.current) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 relative">
      {/* Loading Overlay */}
      {loading && !isInitialMount.current && (
        <div className="fixed inset-0 bg-black bg-opacity-30 z-50 flex items-center justify-center">
          <div className="bg-white p-4 rounded-lg shadow-lg flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            <p className="text-sm text-gray-600">Loading data...</p>
          </div>
        </div>
      )}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Email Monitoring Dashboard</h1>
              <p className="mt-1 text-sm text-gray-600">
                {selectedAccount ? `Viewing: ${selectedAccount}` : 'Welcome back'}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center bg-white rounded-lg border border-gray-200 shadow-sm">
                <input
                  ref={timeInputRef}
                  type="number"
                  min="1"
                  value={tempTimeValue}
                  onChange={handleTimeValueChange}
                  onKeyDown={handleTimeValueKeyDown}
                  onBlur={handleTimeValueBlur}
                  className="w-16 border-none rounded-l-lg focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Time"
                  disabled={loading}
                />
                <select
                  value={timeUnit}
                  onChange={handleTimeUnitChange}
                  className="border-none rounded-r-lg border-l border-gray-200 focus:ring-blue-500 focus:border-blue-500 bg-gray-50"
                  disabled={loading}
                >
                  <option value="hours">Hours</option>
                  <option value="days">Days</option>
                </select>
              </div>
              {loading && (
                <div className="text-sm text-blue-500">
                  Fetching data...
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative">
            {error}
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-6">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Received</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">{stats.total}</p>
                </div>
                <Mail className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Read</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">{stats.read}</p>
                </div>
                <CheckCircle className="h-8 w-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Unread</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">{stats.unread}</p>
                </div>
                <AlertCircle className="h-8 w-8 text-red-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Replied</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">{stats.replied}</p>
                </div>
                <Send className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Drafted</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">{stats.drafted}</p>
                </div>
                <MessageSquare className="h-8 w-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Avg Response</p>
                  <p className="mt-1 text-3xl font-semibold text-gray-900">
                    {formatResponseTime(stats.avgResponse)}
                  </p>
                </div>
                <Clock className="h-8 w-8 text-orange-500" />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Email Activity (Last {timeValue} {timeUnit})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                {activityLoading ? (
                  <div className="absolute inset-0 bg-white bg-opacity-70 flex items-center justify-center z-10">
                    <div className="flex flex-col items-center gap-2">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
                      <p className="text-sm text-gray-500">Loading activity data...</p>
                    </div>
                  </div>
                ) : activityData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={activityData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="time"
                        interval="preserveStartEnd"
                        tick={{ fontSize: 12 }}
                        angle={-45}
                        textAnchor="end"
                        height={60}
                      />
                      <YAxis allowDecimals={false} domain={[0, 'auto']} />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="emails"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : !error ? (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    No activity data available for the selected time range
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default EmailDashboard;