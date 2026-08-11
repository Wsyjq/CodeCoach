import type {
  AgentTraceItem,
  ChatRequest,
  ChatResponse,
  DueReviewItem,
  DueReviewsResponse,
  Intent,
  KnowledgeType,
  MemoryItem,
  NextAction,
  ReviewCard,
  ServiceMode,
  StatsSummary
} from './types';
import type { AuthSession } from './types';

const INTENTS: Intent[] = ['KNOWLEDGE_QA', 'DATA_QA', 'DEBUG_CODE', 'NEED_HINT', 'REVIEW_SUMMARY', 'UNDERSTAND_PROBLEM'];
const KNOWLEDGE_TYPES: KnowledgeType[] = ['MEMORIZE', 'UNDERSTAND', 'MIXED', 'UNKNOWN'];
const SERVICE_MODES: ServiceMode[] = ['auto', 'knowledge', 'problem', 'hint', 'debug', 'data', 'review', 'followup'];
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export interface AppStatus {
  status: string;
  maintenance: boolean;
  message: string;
}

const defaultTrace: AgentTraceItem[] = [
  { node: 'Profile Agent', status: 'waiting', detail: '等待用户输入' },
  { node: 'Intent Router', status: 'waiting', detail: '等待识别意图' },
  { node: 'RAG / Tool', status: 'waiting', detail: '等待工具调用' },
  { node: 'Debug / Hint / Data', status: 'waiting', detail: '等待分析路径' },
  { node: 'Review Agent', status: 'waiting', detail: '等待生成复盘' },
  { node: 'Memory Agent', status: 'waiting', detail: '等待记忆写入' }
];

export async function fetchAppStatus(): Promise<AppStatus> {
  const response = await fetch(`${API_BASE_URL}/api/status`);
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  const data = await response.json();
  return {
    status: typeof data.status === 'string' ? data.status : 'ok',
    maintenance: Boolean(data.maintenance),
    message: typeof data.message === 'string' ? data.message : ''
  };
}

export async function registerUser(request: { username: string; display_name: string; password: string }): Promise<AuthSession> {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    throw new Error(await responseError(response, '注册失败'));
  }
  return normalizeAuthSession(await response.json());
}

export async function loginUser(request: { username: string; password: string }): Promise<AuthSession> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    throw new Error(await responseError(response, '登录失败'));
  }
  return normalizeAuthSession(await response.json());
}

export async function fetchCurrentUser(token: string): Promise<AuthSession['user']> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, { headers: authHeaders(token) });
  if (!response.ok) {
    throw new Error(`AUTH_ME_${response.status}:${await responseError(response, '登录状态已失效')}`);
  }
  return normalizeAuthSession({ token, ...(await response.json()) }).user;
}

export async function logoutUser(token: string): Promise<void> {
  await fetch(`${API_BASE_URL}/api/auth/logout`, { method: 'POST', headers: authHeaders(token) });
}

export async function sendChat(request: ChatRequest, token = ''): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return normalizeChatResponse(await response.json());
}

export async function fetchStatsSummary(token = ''): Promise<StatsSummary> {
  const response = await fetch(`${API_BASE_URL}/api/stats/summary`, { headers: authHeaders(token) });
  if (!response.ok) {
    throw new Error(`Stats request failed: ${response.status}`);
  }
  return normalizeStatsSummary(await response.json());
}

export async function fetchMemories(token = ''): Promise<MemoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/memories`, { headers: authHeaders(token) });
  if (!response.ok) {
    throw new Error(`Memories request failed: ${response.status}`);
  }
  const data = await response.json();
  return Array.isArray(data.items) ? data.items.map(normalizeMemoryItem) : [];
}

export async function fetchMemoryDetail(memoryId: string, token = ''): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/api/memories/${encodeURIComponent(memoryId)}`, { headers: authHeaders(token) });
  if (!response.ok) {
    throw new Error(`Memory detail request failed: ${response.status}`);
  }
  return normalizeMemoryItem(await response.json());
}

export async function markMemoryReviewed(memoryId: string, token = ''): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/api/memories/${encodeURIComponent(memoryId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ outcome: 'reviewed' })
  });

  if (!response.ok) {
    throw new Error(`Memory review request failed: ${response.status}`);
  }

  return normalizeMemoryItem(await response.json());
}

export async function fetchDueReviews(token = ''): Promise<DueReviewsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/reviews/due`, { headers: authHeaders(token) });
  if (!response.ok) {
    throw new Error(`Due reviews request failed: ${response.status}`);
  }
  return normalizeDueReviews(await response.json());
}

function authHeaders(token: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function responseError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    return typeof data.detail === 'string' ? data.detail : fallback;
  } catch {
    return fallback;
  }
}

function normalizeAuthSession(data: Partial<AuthSession>): AuthSession {
  const user = data.user ?? { id: '', username: '', display_name: '' };
  return {
    token: typeof data.token === 'string' ? data.token : '',
    user: {
      id: typeof user.id === 'string' ? user.id : '',
      username: typeof user.username === 'string' ? user.username : '',
      display_name: typeof user.display_name === 'string' && user.display_name ? user.display_name : typeof user.username === 'string' ? user.username : ''
    }
  };
}

function normalizeChatResponse(data: Partial<ChatResponse>): ChatResponse {
  const similarMemory = data.similar_memory ?? { matched: false, title: '', review_tip: '' };
  const reviewCard = normalizeReviewCard(data.review_card);

  return {
    session_id: typeof data.session_id === 'string' ? data.session_id : undefined,
    turn_id: typeof data.turn_id === 'string' ? data.turn_id : undefined,
    is_follow_up: typeof data.is_follow_up === 'boolean' ? data.is_follow_up : undefined,
    conversation_title: typeof data.conversation_title === 'string' ? data.conversation_title : undefined,
    answer: typeof data.answer === 'string' && data.answer.trim() ? data.answer : '暂未收到教学讲解，请稍后重试。',
    intent: isIntent(data.intent) ? data.intent : 'KNOWLEDGE_QA',
    knowledge_type: isKnowledgeType(data.knowledge_type) ? data.knowledge_type : 'UNKNOWN',
    knowledge_tags: toStringArray(data.knowledge_tags),
    similar_memory: {
      matched: Boolean(similarMemory.matched),
      id: typeof similarMemory.id === 'string' ? similarMemory.id : undefined,
      title: typeof similarMemory.title === 'string' ? similarMemory.title : '',
      mistake_summary: typeof similarMemory.mistake_summary === 'string' ? similarMemory.mistake_summary : '',
      review_tip: typeof similarMemory.review_tip === 'string' ? similarMemory.review_tip : '',
      score: typeof similarMemory.score === 'number' ? similarMemory.score : undefined,
      first_seen_at: typeof similarMemory.first_seen_at === 'string' ? similarMemory.first_seen_at : undefined,
      last_seen_at: typeof similarMemory.last_seen_at === 'string' ? similarMemory.last_seen_at : undefined,
      occurrence_count: typeof similarMemory.occurrence_count === 'number' ? similarMemory.occurrence_count : undefined,
      exact_match: typeof similarMemory.exact_match === 'boolean' ? similarMemory.exact_match : undefined
    },
    review_card: reviewCard,
    next_actions: normalizeNextActions(data.next_actions),
    agent_trace: normalizeAgentTrace(data.agent_trace)
  };
}

function normalizeReviewCard(card?: Partial<ReviewCard>): ReviewCard {
  return {
    id: typeof card?.id === 'string' ? card.id : '',
    title: typeof card?.title === 'string' ? card.title : '',
    error_type: typeof card?.error_type === 'string' ? card.error_type : '',
    knowledge_type: isKnowledgeType(card?.knowledge_type) ? card.knowledge_type : undefined,
    knowledge_tags: toStringArray(card?.knowledge_tags),
    mistake_summary: typeof card?.mistake_summary === 'string' ? card.mistake_summary : '',
    review_tip: typeof card?.review_tip === 'string' ? card.review_tip : '',
    remember_points: toStringArray(card?.remember_points),
    understand_points: toStringArray(card?.understand_points),
    common_mistakes: toStringArray(card?.common_mistakes),
    next_review_at: typeof card?.next_review_at === 'string' ? card.next_review_at : ''
  };
}

function normalizeAgentTrace(trace?: AgentTraceItem[]): AgentTraceItem[] {
  if (!Array.isArray(trace) || trace.length === 0) return defaultTrace;
  return trace
    .filter((item) => item && typeof item.node === 'string')
    .map((item) => ({
      node: item.node,
      status: ['waiting', 'running', 'done', 'warning', 'error'].includes(item.status) ? item.status : 'done',
      detail: typeof item.detail === 'string' ? item.detail : ''
    }));
}

function normalizeStatsSummary(data: Partial<StatsSummary>): StatsSummary {
  return {
    metric: typeof data.metric === 'string' ? data.metric : 'common_errors',
    time_range: typeof data.time_range === 'string' ? data.time_range : '7d',
    total_records: typeof data.total_records === 'number' ? data.total_records : 0,
    top_errors: Array.isArray(data.top_errors) ? data.top_errors : [],
    weak_tags: toStringArray(data.weak_tags),
    review_due_count: typeof data.review_due_count === 'number' ? data.review_due_count : 0,
    mastery_avg: typeof data.mastery_avg === 'number' ? data.mastery_avg : 0,
    recommended_actions: toStringArray(data.recommended_actions)
  };
}

function normalizeMemoryItem(item: Partial<MemoryItem>): MemoryItem {
  return {
    id: typeof item.id === 'string' ? item.id : crypto.randomUUID(),
    title: typeof item.title === 'string' ? item.title : '未命名错题',
    error_type: typeof item.error_type === 'string' ? item.error_type : '未知错误',
    knowledge_type: isKnowledgeType(item.knowledge_type) ? item.knowledge_type : undefined,
    knowledge_tags: toStringArray(item.knowledge_tags),
    mistake_summary: typeof item.mistake_summary === 'string' ? item.mistake_summary : '',
    review_tip: typeof item.review_tip === 'string' ? item.review_tip : '',
    remember_points: toStringArray(item.remember_points),
    understand_points: toStringArray(item.understand_points),
    common_mistakes: toStringArray(item.common_mistakes),
    last_seen_at: typeof item.last_seen_at === 'string' ? item.last_seen_at : '',
    next_review_at: typeof item.next_review_at === 'string' ? item.next_review_at : '',
    mastery: typeof item.mastery === 'number' ? item.mastery : 0,
    mastery_status: typeof item.mastery_status === 'string' ? item.mastery_status : undefined,
    review_count: typeof item.review_count === 'number' ? item.review_count : undefined,
    last_reviewed_at: typeof item.last_reviewed_at === 'string' ? item.last_reviewed_at : undefined
  };
}

function normalizeDueReviews(data: Partial<DueReviewsResponse>): DueReviewsResponse {
  return {
    metric: typeof data.metric === 'string' ? data.metric : 'today_review',
    time_range: typeof data.time_range === 'string' ? data.time_range : 'today',
    due_reviews: Array.isArray(data.due_reviews) ? data.due_reviews.map(normalizeDueReviewItem) : []
  };
}

function normalizeDueReviewItem(item: Partial<DueReviewItem>): DueReviewItem {
  return {
    id: typeof item.id === 'string' ? item.id : crypto.randomUUID(),
    title: typeof item.title === 'string' ? item.title : '未命名复习任务',
    error_type: typeof item.error_type === 'string' ? item.error_type : '待复习',
    mastery_status: typeof item.mastery_status === 'string' ? item.mastery_status : undefined,
    knowledge_tags: toStringArray(item.knowledge_tags),
    review_tip: typeof item.review_tip === 'string' ? item.review_tip : '',
    next_review_at: typeof item.next_review_at === 'string' ? item.next_review_at : '',
    review_count: typeof item.review_count === 'number' ? item.review_count : undefined,
    last_reviewed_at: typeof item.last_reviewed_at === 'string' ? item.last_reviewed_at : undefined
  };
}

function normalizeNextActions(actions?: NextAction[]): NextAction[] {
  if (!Array.isArray(actions)) return [];
  return actions
    .filter((action) => action && typeof action.label === 'string' && typeof action.message === 'string')
    .map((action) => ({
      label: action.label,
      message: action.message,
      mode: isServiceMode(action.mode) ? action.mode : 'followup'
    }));
}

function toStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function isIntent(value: unknown): value is Intent {
  return typeof value === 'string' && INTENTS.includes(value as Intent);
}

function isKnowledgeType(value: unknown): value is KnowledgeType {
  return typeof value === 'string' && KNOWLEDGE_TYPES.includes(value as KnowledgeType);
}

function isServiceMode(value: unknown): value is ServiceMode {
  return typeof value === 'string' && SERVICE_MODES.includes(value as ServiceMode);
}
