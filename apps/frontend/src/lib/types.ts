export type Intent =
  | 'KNOWLEDGE_QA'
  | 'DATA_QA'
  | 'DEBUG_CODE'
  | 'NEED_HINT'
  | 'REVIEW_SUMMARY'
  | 'UNDERSTAND_PROBLEM';

export type KnowledgeType = 'MEMORIZE' | 'UNDERSTAND' | 'MIXED' | 'UNKNOWN';

export type ServiceMode = 'auto' | 'knowledge' | 'problem' | 'hint' | 'debug' | 'data' | 'review' | 'followup';

export type WorkbenchServiceMode = Exclude<ServiceMode, 'auto' | 'followup'>;

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
}

export interface AuthSession {
  token: string;
  user: AuthUser;
}

export interface ChatRequest {
  user_id?: string;
  user_level: 'beginner' | 'basic' | 'advanced';
  message: string;
  problem_text: string;
  code: string;
  mode: ServiceMode;
  session_id: string;
}

export interface AgentTraceItem {
  node: string;
  status: 'waiting' | 'running' | 'done' | 'warning' | 'error';
  detail: string;
}

export interface SimilarMemory {
  matched: boolean;
  id?: string;
  title: string;
  mistake_summary?: string;
  review_tip: string;
  score?: number;
  first_seen_at?: string;
  last_seen_at?: string;
  occurrence_count?: number;
  exact_match?: boolean;
}

export interface ReviewCard {
  id: string;
  title: string;
  error_type: string;
  knowledge_type?: KnowledgeType;
  knowledge_tags?: string[];
  mistake_summary?: string;
  review_tip?: string;
  remember_points?: string[];
  understand_points?: string[];
  common_mistakes?: string[];
  next_review_at: string;
}

export interface ChatResponse {
  session_id?: string;
  turn_id?: string;
  is_follow_up?: boolean;
  conversation_title?: string;
  answer: string;
  intent: Intent;
  knowledge_type: KnowledgeType;
  knowledge_tags: string[];
  similar_memory: SimilarMemory;
  review_card: ReviewCard;
  next_actions: NextAction[];
  agent_trace: AgentTraceItem[];
}

export interface NextAction {
  label: string;
  message: string;
  mode: ServiceMode;
}

export interface ConversationTurn {
  id: string;
  role: 'user' | 'assistant';
  mode?: ServiceMode;
  message: string;
  response?: ChatResponse;
  createdAt: string;
}

export interface StatsSummary {
  metric: string;
  time_range: string;
  total_records: number;
  top_errors: Array<{ error_type: string; count: number }>;
  weak_tags: string[];
  review_due_count: number;
  mastery_avg: number;
  recommended_actions: string[];
}

export interface MemoryItem {
  id: string;
  title: string;
  error_type: string;
  knowledge_type?: KnowledgeType;
  knowledge_tags: string[];
  mistake_summary: string;
  review_tip: string;
  remember_points?: string[];
  understand_points?: string[];
  common_mistakes?: string[];
  last_seen_at: string;
  next_review_at: string;
  mastery: number;
  mastery_status?: string;
  review_count?: number;
  last_reviewed_at?: string;
}

export interface DueReviewItem {
  id: string;
  title: string;
  error_type: string;
  mastery_status?: string;
  knowledge_tags: string[];
  review_tip: string;
  next_review_at: string;
  review_count?: number;
  last_reviewed_at?: string;
}

export interface DueReviewsResponse {
  metric: string;
  time_range: string;
  due_reviews: DueReviewItem[];
}
