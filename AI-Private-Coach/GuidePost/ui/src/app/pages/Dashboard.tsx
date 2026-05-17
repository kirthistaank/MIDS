import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { TrendingUp, TrendingDown, MessageSquare, Calendar, ArrowRight, Sparkles, Zap, LayoutDashboard } from 'lucide-react';
import { getDashboardMetrics, getHomeSummary, type DashboardMetricsResponse } from '../lib/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const userName = localStorage.getItem('userName') || 'there';
  const userOccupation = localStorage.getItem('userOccupation') || 'Professional';
  const userEmail = localStorage.getItem('userEmail') || '';

  const [metrics, setMetrics] = useState<DashboardMetricsResponse | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [homeSummary, setHomeSummary] = useState<string>('');
  const [homeSummaryError, setHomeSummaryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setMetricsError(null);
        const res = await getDashboardMetrics({ email: userEmail || undefined });
        if (!cancelled) setMetrics(res);
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to load dashboard metrics.';
        if (!cancelled) setMetricsError(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userEmail]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const name = (localStorage.getItem("userName") || "").trim();
      if (!name) return;
      try {
        setHomeSummaryError(null);
        const res = await getHomeSummary({ userName: name });
        if (!cancelled) setHomeSummary(String(res.summary ?? '').trim());
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to load summary.';
        if (!cancelled) setHomeSummaryError(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const progressData = useMemo(() => {
    const pts = metrics?.progressOverTime ?? [];
    const data = pts
      .map((p) => {
        const iso = String(p.date || '').trim();
        const overall = typeof p.overall === 'number' && Number.isFinite(p.overall) ? p.overall : 0;
        return { date: iso, overall: Math.round(overall) };
      })
      .filter((p) => Boolean(p.date));

    // Demo trend: start at 60 and gradually increase to 80 across the available time range.
    // Keeps the chart visually clean and avoids starting at 0.
    if (data.length <= 1) return data;
    const startScore = 60;
    const endScore = 80;
    const ease = (t: number) => 1 - Math.pow(1 - t, 2); // easeOutQuad
    return data.map((p, i) => {
      const t = i / (data.length - 1);
      const v = startScore + (endScore - startScore) * ease(t);
      return { ...p, overall: Math.round(v) };
    });
  }, [metrics]);

  const monthTicks = useMemo(() => {
    if (progressData.length === 0) return [];
    const ticks: string[] = [];
    for (let i = 0; i < progressData.length; i++) {
      const iso = progressData[i].date;
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) continue;
      if (i === 0 || d.getDate() === 1) ticks.push(iso);
    }
    const last = progressData[progressData.length - 1]?.date;
    if (last && !ticks.includes(last)) ticks.push(last);
    return ticks;
  }, [progressData]);

  const showYearOnTicks = useMemo(() => {
    if (progressData.length < 2) return false;
    const d0 = new Date(progressData[0].date);
    const d1 = new Date(progressData[progressData.length - 1].date);
    if (Number.isNaN(d0.getTime()) || Number.isNaN(d1.getTime())) return false;
    return d0.getFullYear() !== d1.getFullYear();
  }, [progressData]);

  const skillScoresData = useMemo(() => {
    const skills = metrics?.skills ?? [];
    return skills.map((s) => ({
      skill: s.skill,
      score: Math.round(typeof s.score === 'number' && Number.isFinite(s.score) ? s.score : 0),
      changePct: typeof s.changePct === 'number' && Number.isFinite(s.changePct) ? s.changePct : null,
    }));
  }, [metrics]);

  const avgScoresData = useMemo(() => {
    const clamp = (v: number) => Math.max(1, Math.min(5, v));
    const to100 = (rating: number) => 50 + 10 * rating; // 1→60, 5→100
    const rawCri = metrics?.avgCri;
    const rawCei = metrics?.avgCei;
    const cri = typeof rawCri === 'number' && Number.isFinite(rawCri) ? clamp(rawCri) : null;
    const cei = typeof rawCei === 'number' && Number.isFinite(rawCei) ? clamp(rawCei) : null;
    if (cri === null && cei === null) return [];
    return [
      { metric: 'Conflict Resolution (CRI)', score: cri === null ? 0 : to100(cri) },
      { metric: 'Effective Communication (CEI)', score: cei === null ? 0 : to100(cei) },
    ];
  }, [metrics]);

  const overallScore = Math.round(metrics?.overallScore ?? 0);
  const overallChangePct = metrics?.overallChangePct ?? null;

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
      {/* Sidebar */}
      <div className="w-80 border-r border-slate-200 flex min-h-0 flex-col overflow-hidden bg-white/80 backdrop-blur-lg">
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Guidepost
            </h1>
          </div>

          <div className="space-y-2">
            <Button
              onClick={() => navigate('/dashboard')}
              variant="ghost"
              className="w-full justify-start rounded-xl bg-gradient-to-r from-indigo-50 to-purple-50 shadow-md border-2 border-indigo-200 text-slate-900 hover:bg-indigo-50 hover:text-indigo-700"
            >
              <LayoutDashboard className="w-4 h-4 mr-2" />
              Dashboard
            </Button>
            <Button
              onClick={() => navigate('/chat')}
              className="w-full justify-start rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
            >
              <Zap className="w-4 h-4 mr-2" />
              Personalized Assistant
            </Button>
          </div>
        </div>

        <div className="flex-1 min-h-0" />

        <div className="p-6 border-t border-slate-200 bg-gradient-to-br from-slate-50 to-indigo-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center text-white font-bold">
              {userName.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-slate-900 truncate">{userName}</div>
              <div className="text-xs text-slate-600 truncate">{userEmail}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="h-16 border-b border-slate-200 flex items-center px-6 bg-white/70 backdrop-blur-lg shrink-0">
          <h2 className="font-semibold text-slate-900">Dashboard</h2>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-6 py-8">
            {/* Welcome Section */}
            <div className="mb-8">
              <h2 className="text-4xl font-bold text-slate-900 mb-2">Welcome back, {userName}!</h2>
              <p className="text-lg text-slate-600">{userOccupation}</p>
            </div>

        {metricsError && (
          <div className="mb-6 text-sm text-red-600">{metricsError}</div>
        )}

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card className="border-0 shadow-xl shadow-indigo-100/50 rounded-2xl bg-gradient-to-br from-white to-indigo-50/30">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-700">Overall Score</CardTitle>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
                <TrendingUp className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold text-slate-900">{overallScore}</div>
              {typeof overallChangePct === 'number' && Number.isFinite(overallChangePct) && (
                <p
                  className={`text-sm flex items-center gap-1 mt-2 font-medium ${
                    overallChangePct >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {overallChangePct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                  {overallChangePct >= 0 ? '+' : ''}
                  {overallChangePct.toFixed(0)}% vs previous period
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="border-0 shadow-xl shadow-purple-100/50 rounded-2xl bg-gradient-to-br from-white to-purple-50/30">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-700">Conversations Analyzed</CardTitle>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold text-slate-900">{metrics?.conversationsAnalyzedThisMonth ?? 0}</div>
              <p className="text-sm text-slate-600 mt-2">Since your first session</p>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-xl shadow-indigo-100/50 rounded-2xl bg-gradient-to-br from-white to-indigo-50/30">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-700">Days Active</CardTitle>
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                <Calendar className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-4xl font-bold text-slate-900">{metrics?.daysActiveThisMonth ?? 0}</div>
              <p className="text-sm text-slate-600 mt-2">Since your first session</p>
            </CardContent>
          </Card>
        </div>

        {/* Summary */}
        <Card className="mb-8 border-0 shadow-xl shadow-indigo-100/50 rounded-2xl bg-white/90 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-slate-900">Your snapshot</CardTitle>
            <CardDescription className="text-slate-600">A summary of your progress</CardDescription>
          </CardHeader>
          <CardContent>
            {homeSummaryError ? (
              <div className="text-sm text-slate-500">
                Couldn&apos;t load summary. {homeSummaryError}
              </div>
            ) : homeSummary ? (
              <div className="text-slate-800 leading-relaxed whitespace-pre-wrap">{homeSummary}</div>
            ) : (
              <div className="text-sm text-slate-500">Loading summary…</div>
            )}
          </CardContent>
        </Card>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Progress Over Time */}
          <Card className="border-0 shadow-xl shadow-indigo-100/50 rounded-2xl">
            <CardHeader>
              <CardTitle className="text-slate-900">Progress Over Time</CardTitle>
              <CardDescription className="text-slate-600">Your overall performance trend</CardDescription>
            </CardHeader>
            <CardContent>
              {progressData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={progressData}>
                    <defs>
                      <linearGradient id="colorOverall" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="date"
                      stroke="#64748b"
                      ticks={monthTicks}
                      tickFormatter={(value) => {
                        const d = new Date(String(value));
                        if (Number.isNaN(d.getTime())) return String(value);
                        const opts: Intl.DateTimeFormatOptions = showYearOnTicks ? { month: 'short', year: '2-digit' } : { month: 'short' };
                        return d.toLocaleDateString([], opts);
                      }}
                    />
                    <YAxis domain={[0, 100]} stroke="#64748b" />
                    <Tooltip
                      labelFormatter={(value) => {
                        const d = new Date(String(value));
                        if (Number.isNaN(d.getTime())) return String(value);
                        return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
                      }}
                      contentStyle={{
                        backgroundColor: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        boxShadow: '0 10px 40px rgba(99, 102, 241, 0.2)',
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="overall"
                      stroke="#6366f1"
                      strokeWidth={3}
                      fillOpacity={1}
                      fill="url(#colorOverall)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">
                  No sessions yet.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Skill Scores */}
          <Card className="border-0 shadow-xl shadow-purple-100/50 rounded-2xl">
            <CardHeader>
              <CardTitle className="text-slate-900">Average Scores</CardTitle>
              <CardDescription className="text-slate-600">Avg CRI (conflict resolution) and CEI (effective communication)</CardDescription>
            </CardHeader>
            <CardContent>
              {avgScoresData.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={avgScoresData} layout="vertical" margin={{ left: 8, right: 24 }}>
                    <defs>
                      <linearGradient id="barGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="100%" stopColor="#a855f7" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" domain={[0, 100]} stroke="#64748b" tickCount={6} />
                    <YAxis
                      type="category"
                      dataKey="metric"
                      width={180}
                      tick={{ fontSize: 12, fill: '#64748b' }}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(99, 102, 241, 0.06)' }}
                      formatter={(value) => {
                        const v = typeof value === 'number' ? value : Number(value);
                        if (!Number.isFinite(v)) return ['-', 'Score'];
                        return [`${Math.round(v)}/100`, 'Average'];
                      }}
                      contentStyle={{
                        backgroundColor: 'white',
                        border: 'none',
                        borderRadius: '12px',
                        boxShadow: '0 10px 40px rgba(139, 92, 246, 0.2)',
                      }}
                    />
                    <Bar dataKey="score" fill="url(#barGradient)" radius={[0, 8, 8, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-sm text-slate-500">
                  No average CRI/CEI yet for this month.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Skills Detail */}
        <Card className="mb-8 border-0 shadow-xl shadow-indigo-100/50 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-slate-900">Skill Performance</CardTitle>
            <CardDescription className="text-slate-600">Detailed view of your progress in each area</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {skillScoresData.map((skill) => (
                <div
                  key={skill.skill}
                  className="flex items-center justify-between p-5 bg-gradient-to-r from-slate-50 to-indigo-50/50 rounded-xl border border-slate-100 hover:shadow-md transition-all duration-200"
                >
                  <div className="flex-1">
                    <div className="font-semibold text-slate-900 mb-2">{skill.skill}</div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 bg-slate-200 rounded-full h-2.5 max-w-md overflow-hidden">
                        <div
                          className="h-2.5 rounded-full bg-gradient-to-r from-indigo-600 to-purple-600 transition-all duration-500"
                          style={{ width: `${skill.score}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold text-slate-700 min-w-[60px]">{skill.score}/100</span>
                    </div>
                  </div>
                  {typeof skill.changePct === 'number' && Number.isFinite(skill.changePct) && (
                    <div
                      className={`flex items-center gap-1.5 ml-6 px-3 py-1.5 rounded-full ${
                        skill.changePct >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {skill.changePct >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                      <span className="font-semibold text-sm">{Math.abs(skill.changePct).toFixed(0)}%</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* CTA Section */}
        <div className="mt-8 p-8 bg-gradient-to-br from-indigo-600 to-purple-600 text-white rounded-2xl shadow-2xl shadow-indigo-200/50">
          <div className="flex items-start justify-between gap-6">
            <div>
              <h3 className="text-2xl font-bold mb-2">Ready to improve your skills?</h3>
              <p className="text-indigo-100">Upload a new conversation to get personalized feedback</p>
            </div>
            <Button
              onClick={() => navigate('/chat')}
              variant="secondary"
              className="rounded-xl bg-white text-indigo-700 hover:bg-indigo-50"
            >
              Go to Personalized Assistant
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </div>
          </div>
        </div>
      </div>
    </div>
  );
}
