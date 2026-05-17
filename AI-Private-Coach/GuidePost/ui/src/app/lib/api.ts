export type AudioStatus = 'uploaded' | 'processing' | 'ready' | 'error';

export interface AudioUploadResponse {
  audioId: string;
}

export interface AudioJobResponse {
  audioId: string;
  status: AudioStatus;
  createdAt: number;
  updatedAt: number;
  transcript?: string | null;
  analysis?: string | null;
  errorMessage?: string | null;
}

export interface ReportResponse {
  report: string;
  finalStrategy?: string | null;
  conversationScore?: number | null;
  conversationMetrics?: Record<string, unknown> | null;
}

export interface DashboardProgressPoint {
  date: string; // ISO date (YYYY-MM-DD)
  overall: number; // 0-100
}

export interface DashboardSkillScore {
  skill: string;
  score: number; // 0-100
  changePct?: number | null;
}

export interface DashboardMetricsResponse {
  overallScore: number; // 0-100
  overallChangePct?: number | null;
  conversationsAnalyzedThisMonth: number;
  daysActiveThisMonth: number;
  progressOverTime: DashboardProgressPoint[];
  skills: DashboardSkillScore[];
  avgCri?: number | null; // raw 1-5
  avgCei?: number | null; // raw 1-5
}

export interface HomeSummaryResponse {
  summary: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string | null;
  occupation?: string | null;
  seniorityLevel?: string | null;
  rankedSkills?: string[] | null;
  otherFocus?: string | null;
  voiceRecorded?: boolean | null;
}

export type ConversationPhase = 'alignment' | 'coaching';

export interface ChatResponse {
  reply: string;
  conversationId?: string | null;
  phase?: ConversationPhase | null;
  alignedFocus?: string | null;
}

async function assertOk(res: Response) {
  if (res.ok) return;
  const text = await res.text().catch(() => '');
  throw new Error(text || `Request failed (${res.status})`);
}

export async function uploadVoiceReference(params: {
  targetName: string;
  blob: Blob;
  filename?: string;
  email?: string;
  userId?: string;
}): Promise<void> {
  const { targetName, blob } = params;
  const filename = params.filename ?? `${targetName || 'target'}-voice-reference.webm`;

  const form = new FormData();
  form.append('targetName', targetName);
  if (params.email) form.append('email', params.email);
  if (params.userId) form.append('userId', params.userId);
  form.append('file', new File([blob], filename, { type: blob.type || 'audio/webm' }));

  const res = await fetch('/api/voice_reference', {
    method: 'POST',
    body: form,
  });
  await assertOk(res);
}

export async function uploadAudio(params: {
  file: File;
  targetName?: string;
  userContext?: string;
  userEmail?: string;
  userId?: string;
}): Promise<AudioUploadResponse> {
  const form = new FormData();
  form.append('file', params.file);
  if (params.targetName) form.append('targetName', params.targetName);
  if (params.userContext) form.append('userContext', params.userContext);
  if (params.userEmail) form.append('userEmail', params.userEmail);
  if (params.userId) form.append('userId', params.userId);

  const res = await fetch('/api/audio', {
    method: 'POST',
    body: form,
  });
  await assertOk(res);
  return (await res.json()) as AudioUploadResponse;
}

export async function getAudioJob(audioId: string): Promise<AudioJobResponse> {
  const res = await fetch(`/api/audio/${encodeURIComponent(audioId)}`, {
    method: 'GET',
  });
  await assertOk(res);
  return (await res.json()) as AudioJobResponse;
}

export async function createReport(params: {
  audioId: string;
  userContext?: string;
  targetName?: string;
  alignedFocus?: string;
}): Promise<ReportResponse> {
  const res = await fetch('/api/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  await assertOk(res);
  return (await res.json()) as ReportResponse;
}

export async function chat(params: {
  audioId: string;
  message: string;
  conversationId?: string;
  userContext?: string;
  phase?: ConversationPhase;
}): Promise<ChatResponse> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  await assertOk(res);
  return (await res.json()) as ChatResponse;
}

export async function getDashboardMetrics(params: { userId?: string; email?: string }): Promise<DashboardMetricsResponse> {
  const qp = new URLSearchParams();
  if (params.userId) qp.set('userId', params.userId);
  if (params.email) qp.set('email', params.email);
  const url = `/api/dashboard_metrics${qp.toString() ? `?${qp.toString()}` : ''}`;
  const res = await fetch(url, { method: 'GET' });
  await assertOk(res);
  return (await res.json()) as DashboardMetricsResponse;
}

export async function getHomeSummary(params: {
  userName: string;
  conversationId?: string;
}): Promise<HomeSummaryResponse> {
  const qp = new URLSearchParams();
  qp.set('userName', params.userName);
  if (params.conversationId) qp.set('conversationId', params.conversationId);
  const res = await fetch(`/api/home-summary?${qp.toString()}`, { method: 'GET' });
  await assertOk(res);
  return (await res.json()) as HomeSummaryResponse;
}

export async function upsertUser(params: {
  email: string;
  name?: string;
  occupation?: string;
  seniorityLevel?: string;
  rankedSkills?: string[];
  otherFocus?: string;
  voiceRecorded?: boolean;
}): Promise<UserProfile> {
  const res = await fetch('/api/user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  await assertOk(res);
  return (await res.json()) as UserProfile;
}

export async function getUserByEmail(params: { email: string }): Promise<UserProfile> {
  const url = `/api/user?email=${encodeURIComponent(params.email)}`;
  const res = await fetch(url, { method: 'GET' });
  await assertOk(res);
  return (await res.json()) as UserProfile;
}

export async function resetUser(params: { email: string }): Promise<{ ok: boolean; deleted: boolean }> {
  const res = await fetch('/api/reset_user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  await assertOk(res);
  return (await res.json()) as { ok: boolean; deleted: boolean };
}

