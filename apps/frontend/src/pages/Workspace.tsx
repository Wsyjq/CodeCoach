import { useEffect, useState } from 'react';
import { BookMarked, CalendarCheck, ClipboardList, Code, MessageSquare, Sparkles } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { AgentTracePanel } from '../components/AgentTracePanel';
import { ChatPanel } from '../components/ChatPanel';
import { DueReviewPanel } from '../components/DueReviewPanel';
import { LearningSnapshot } from '../components/LearningSnapshot';
import { MemoryDetailPanel } from '../components/MemoryDetailPanel';
import { MistakeLibraryPanel } from '../components/MistakeLibraryPanel';
import { ProblemPanel } from '../components/ProblemPanel';
import { SimilarMemoryBanner } from '../components/SimilarMemoryBanner';
import { fetchDueReviews, fetchMemories, fetchMemoryDetail, fetchStatsSummary, markMemoryReviewed, sendChat } from '../lib/api';
import { getReviewCount } from '../lib/reviewState';
import type { AuthUser, ChatResponse, ConversationTurn, DueReviewItem, MemoryItem, ServiceMode, StatsSummary, WorkbenchServiceMode } from '../lib/types';

const initialResponse: ChatResponse = {
  answer: '等待输入题目、代码或问题。建议先试试：我这个代码为什么过不了？',
  intent: 'DEBUG_CODE',
  knowledge_type: 'UNKNOWN',
  knowledge_tags: [],
  similar_memory: { matched: false, title: '', review_tip: '' },
  review_card: { id: '', title: '', error_type: '', next_review_at: '' },
  next_actions: [],
  agent_trace: [
    { node: 'Profile Agent', status: 'waiting', detail: '等待用户输入' },
    { node: 'Intent Router', status: 'waiting', detail: '等待识别意图' },
    { node: 'RAG / Tool', status: 'waiting', detail: '等待工具调用' },
    { node: 'Debug / Hint / Data', status: 'waiting', detail: '等待分析路径' },
    { node: 'Review Agent', status: 'waiting', detail: '等待生成复盘' },
    { node: 'Memory Agent', status: 'waiting', detail: '等待记忆写入' }
  ]
};

type UserLevel = 'beginner' | 'basic' | 'advanced';
type WorkbenchSection = 'input' | 'coach' | 'mistakes' | 'reviews';

interface ChatPayload {
  mode: ServiceMode;
  problemText: string;
  code: string;
  message: string;
  userLevel: UserLevel;
}

const workspaceSections: Array<{ key: WorkbenchSection; label: string; detail: string; icon: LucideIcon; tone: 'blue' | 'orange' | 'cream' | 'ink' | 'soft' }> = [
  { key: 'input', label: '服务输入', detail: '选择服务并提交问题', icon: ClipboardList, tone: 'blue' },
  { key: 'coach', label: '辅导对话', detail: '查看回答并继续追问', icon: MessageSquare, tone: 'orange' },
  { key: 'mistakes', label: '我的错题', detail: '复盘卡和历史档案', icon: BookMarked, tone: 'ink' },
  { key: 'reviews', label: '今日复习', detail: '到期复习任务', icon: CalendarCheck, tone: 'soft' }
];

export function Workspace({
  currentUser,
  authToken,
  maintenanceMode = false,
  maintenanceMessage = '',
  statusPending = false,
  onLogout
}: {
  currentUser: AuthUser;
  authToken: string;
  maintenanceMode?: boolean;
  maintenanceMessage?: string;
  statusPending?: boolean;
  onLogout: () => void | Promise<void>;
}) {
  const [response, setResponse] = useState<ChatResponse>(initialResponse);
  const [conversationTurns, setConversationTurns] = useState<ConversationTurn[]>([]);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [dueReviews, setDueReviews] = useState<DueReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [snapshotStatus, setSnapshotStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [activeSection, setActiveSection] = useState<WorkbenchSection>('input');
  const [selectedMemory, setSelectedMemory] = useState<MemoryItem | null>(null);
  const [memoryDetailLoading, setMemoryDetailLoading] = useState(false);
  const [memoryDetailLoadingId, setMemoryDetailLoadingId] = useState('');
  const [memoryDetailError, setMemoryDetailError] = useState('');
  const [reviewCompletionLoadingId, setReviewCompletionLoadingId] = useState('');
  const [sessionId, setSessionId] = useState(() => `session_${Date.now()}`);
  const [currentContext, setCurrentContext] = useState({
    problemText: '',
    code: '',
    userLevel: 'beginner' as UserLevel
  });
  const backendDisabled = maintenanceMode || statusPending;

  useEffect(() => {
    let cancelled = false;
    if (backendDisabled) {
      if (!statusPending) setSnapshotStatus('ready');
      return () => {
        cancelled = true;
      };
    }
    refreshLearningData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [backendDisabled, statusPending, authToken]);

  async function refreshLearningData(isCancelled: () => boolean = () => false) {
    if (backendDisabled) {
      setSnapshotStatus('ready');
      return;
    }
    setSnapshotStatus('loading');
    const [statsResult, memoriesResult, dueResult] = await Promise.allSettled([
      fetchStatsSummary(authToken),
      fetchMemories(authToken),
      fetchDueReviews(authToken)
    ]);
    if (isCancelled()) return;

    const hasAnySuccess = [statsResult, memoriesResult, dueResult].some((result) => result.status === 'fulfilled');
    const nextMemories = memoriesResult.status === 'fulfilled' ? memoriesResult.value : [];
    const nextDueReviews = dueResult.status === 'fulfilled' ? mergeDueReviewsWithMemories(dueResult.value.due_reviews, nextMemories) : [];

    setStats(statsResult.status === 'fulfilled' ? statsResult.value : null);
    setMemories(nextMemories);
    setDueReviews(nextDueReviews);
    setSnapshotStatus(hasAnySuccess ? 'ready' : 'error');
  }

  async function handleSubmit(payload: {
    mode: WorkbenchServiceMode;
    problemText: string;
    code: string;
    message: string;
    userLevel: UserLevel;
  }) {
    setCurrentContext({
      problemText: payload.problemText,
      code: payload.code,
      userLevel: payload.userLevel
    });
    await submitChat(payload);
  }

  async function handleFollowUp(message: string, mode: ServiceMode) {
    await submitChat({
      mode,
      problemText: currentContext.problemText,
      code: currentContext.code,
      message,
      userLevel: currentContext.userLevel
    });
  }

  async function handleOpenMemoryDetail(memoryId: string) {
    if (backendDisabled) {
      setMemoryDetailError('当前处于维护模式，错题详情服务暂不可用。');
      return;
    }
    const fallbackMemory = getMemoryFallback(memoryId, memories, dueReviews);
    setMemoryDetailLoading(true);
    setMemoryDetailLoadingId(memoryId);
    setMemoryDetailError('');

    try {
      const memory = await fetchMemoryDetail(memoryId, authToken);
      setSelectedMemory(memory);
    } catch (err) {
      if (fallbackMemory) {
        setSelectedMemory(fallbackMemory);
        setMemoryDetailError(err instanceof Error ? `${err.message}，已展示当前列表缓存。` : '错题详情读取失败，已展示当前列表缓存。');
      } else {
        setMemoryDetailError(err instanceof Error ? err.message : '错题详情读取失败，请稍后再试。');
      }
    } finally {
      setMemoryDetailLoading(false);
      setMemoryDetailLoadingId('');
    }
  }

  function handleCloseMemoryDetail() {
    setSelectedMemory(null);
    setMemoryDetailError('');
  }

  async function handleCompleteReview(memoryId: string) {
    if (backendDisabled) {
      setMemoryDetailError('当前处于维护模式，复习状态暂不可更新。');
      return;
    }
    setReviewCompletionLoadingId(memoryId);
    setMemoryDetailError('');

    try {
      const reviewedMemory = await markMemoryReviewed(memoryId, authToken);
      applyCompletedReview(memoryId, reviewedMemory);
      await refreshLearningData();
    } catch (err) {
      setMemoryDetailError(err instanceof Error ? err.message : '复习状态更新失败，请稍后再试。');
    } finally {
      setReviewCompletionLoadingId('');
    }
  }

  function applyCompletedReview(memoryId: string, reviewedMemory?: MemoryItem) {
    const reviewedAt = new Date().toISOString().slice(0, 10);

    setSelectedMemory((memory) => (memory?.id === memoryId ? completeMemoryReview(memory, reviewedMemory, reviewedAt) : memory));
    setMemories((items) => items.map((item) => (item.id === memoryId ? completeMemoryReview(item, reviewedMemory, reviewedAt) : item)));
    setDueReviews((items) => items.map((item) => (item.id === memoryId ? completeDueReview(item, reviewedMemory, reviewedAt) : item)));
  }

  async function submitChat(payload: ChatPayload) {
    if (backendDisabled) {
      setError('当前处于维护模式，AI 辅导和学习服务暂不可用。');
      setActiveSection('coach');
      return;
    }
    const requestSessionId = sessionId;
    const userTurn: ConversationTurn = {
      id: makeTurnId('user'),
      role: 'user',
      mode: payload.mode,
      message: payload.message,
      createdAt: new Date().toISOString()
    };

    setLoading(true);
    setError('');
    setConversationTurns((turns) => [...turns, userTurn]);
    setActiveSection('coach');

    try {
      const result = await sendChat({
        user_level: payload.userLevel,
        message: payload.message,
        problem_text: payload.problemText,
        code: payload.code,
        mode: payload.mode,
        session_id: requestSessionId
      }, authToken);
      const effectiveSessionId = result.session_id || requestSessionId;
      const assistantTurn: ConversationTurn = {
        id: result.turn_id || makeTurnId('assistant'),
        role: 'assistant',
        mode: payload.mode,
        message: result.answer,
        response: result,
        createdAt: new Date().toISOString()
      };

      setSessionId(effectiveSessionId);
      setResponse(result);
      setConversationTurns((turns) => [...turns, assistantTurn]);

      if (payload.mode === 'debug' || payload.mode === 'review' || result.review_card.id) {
        refreshLearningData();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败');
    } finally {
      setLoading(false);
    }
  }

  const learningLoading = statusPending || snapshotStatus === 'loading';
  const learningError = snapshotStatus === 'error';

  return (
    <main className="app-stage">
      <section className="dashboard-shell">
        <section className="dashboard-body">
          {backendDisabled ? (
            <div className="maintenance-banner" role="status" aria-live="polite">
              <div>
                <span className="mini-label">服务状态</span>
                <strong>{statusPending ? '正在检查服务状态' : '目前正在维护'}</strong>
              </div>
              <p>
                {statusPending
                  ? '前端页面已加载，正在确认后端服务是否可用。'
                  : maintenanceMessage || '前端页面可浏览，AI 辅导、错题、复习等后端服务暂时不可用。'}
              </p>
            </div>
          ) : null}

          <section className="dashboard-overview">
            <article className="hero-card">
              <div>
                <span className="eyebrow">CodeCoach Workbench</span>
                <h1>
                  该记的帮你记，<br />
                  该懂的带你想。
                </h1>
                <p className="hero-copy">选择一个学习服务，CodeCoach 会把问题讲清楚，并把值得复习的内容沉淀下来。</p>
              </div>
              <div className="hero-visual" aria-hidden="true">
                <Sparkles size={34} />
                <Code size={56} />
              </div>
            </article>

            <article className="overview-card">
              <div className="user-card-heading">
                <div>
                  <span className="eyebrow dark">{currentUser.display_name}</span>
                  <h2>今天的学习状态</h2>
                </div>
                <button className="ghost-button compact" type="button" onClick={onLogout}>切换账号</button>
              </div>
              <div className="overview-metrics" aria-busy={learningLoading} aria-live="polite">
                <div>
                  <span>错题</span>
                  <strong aria-label={learningLoading ? '错题加载中' : undefined}>
                    {learningLoading ? '…' : stats?.total_records ?? memories.length}
                  </strong>
                </div>
                <div>
                  <span>待复习</span>
                  <strong aria-label={learningLoading ? '待复习加载中' : undefined}>
                    {learningLoading ? '…' : dueReviews.length || stats?.review_due_count || 0}
                  </strong>
                </div>
                <div>
                  <span>掌握度</span>
                  <strong aria-label={learningLoading ? '掌握度加载中' : undefined}>
                    {learningLoading ? '…' : stats ? `${Math.round(stats.mastery_avg * 100)}%` : '--'}
                  </strong>
                </div>
              </div>
              <p>{stats?.recommended_actions[0] || '先从左侧选择服务开始，系统会根据本轮学习更新画像。'}</p>
            </article>
          </section>

          <nav className="workspace-section-tabs" aria-label="工作台栏目">
            {workspaceSections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  className={`workspace-tab ${section.tone} ${activeSection === section.key ? 'is-active' : ''}`}
                  key={section.key}
                  type="button"
                  onClick={() => setActiveSection(section.key)}
                >
                  <span className="workspace-tab-icon"><Icon size={18} /></span>
                  <strong>{section.label}</strong>
                  <small>{section.detail}</small>
                </button>
              );
            })}
          </nav>

          <section className="active-workspace">
            {activeSection === 'input' ? (
              <section className="workbench-grid input-focus">
                <ProblemPanel disabled={backendDisabled} loading={loading} onSubmit={handleSubmit} />
                <AgentTracePanel response={response} loading={loading} userLabel={currentUser.display_name} />
              </section>
            ) : null}

            {activeSection === 'coach' ? (
              <section className="single-stack">
                {error ? <div className="error-card">{error}</div> : null}
                <SimilarMemoryBanner memory={response.similar_memory} />
                <ChatPanel disabled={backendDisabled} turns={conversationTurns} loading={loading} onFollowUp={handleFollowUp} />
              </section>
            ) : null}

            {activeSection === 'mistakes' ? (
              <MistakeLibraryPanel
                memories={memories}
                loading={learningLoading}
                error={learningError}
                currentReview={response.review_card}
                knowledgeType={response.knowledge_type}
                knowledgeTags={response.knowledge_tags}
                selectedMemory={selectedMemory}
                detailLoading={memoryDetailLoading}
                detailLoadingId={memoryDetailLoadingId}
                detailError={memoryDetailError}
                reviewCompletionLoadingId={reviewCompletionLoadingId}
                onOpenDetail={handleOpenMemoryDetail}
                onCloseDetail={handleCloseMemoryDetail}
                onCompleteReview={handleCompleteReview}
              />
            ) : null}

            {activeSection === 'reviews' ? (
              <section className="workbench-grid reviews-focus">
                <DueReviewPanel
                  reviews={dueReviews}
                  loading={learningLoading}
                  error={learningError}
                  detailLoadingId={memoryDetailLoadingId}
                  onOpenDetail={handleOpenMemoryDetail}
                />
                <div className="right-stack">
                  <MemoryDetailPanel
                    memory={selectedMemory}
                    loading={memoryDetailLoading}
                    error={memoryDetailError}
                    reviewCompleting={Boolean(selectedMemory && reviewCompletionLoadingId === selectedMemory.id)}
                    onClose={handleCloseMemoryDetail}
                    onCompleteReview={handleCompleteReview}
                  />
                  <LearningSnapshot
                    stats={stats}
                    memories={memories}
                    loading={learningLoading}
                    error={learningError}
                    onOpenMistakes={() => setActiveSection('mistakes')}
                    onOpenReviews={() => setActiveSection('reviews')}
                  />
                </div>
              </section>
            ) : null}
          </section>
        </section>
      </section>
    </main>
  );
}

function makeTurnId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function getMemoryFallback(memoryId: string, memories: MemoryItem[], dueReviews: DueReviewItem[]): MemoryItem | null {
  const memory = memories.find((item) => item.id === memoryId);
  if (memory) return memory;

  const dueReview = dueReviews.find((item) => item.id === memoryId);
  if (!dueReview) return null;

  return {
    id: dueReview.id,
    title: dueReview.title,
    error_type: dueReview.error_type,
    knowledge_tags: dueReview.knowledge_tags,
    mistake_summary: '',
    review_tip: dueReview.review_tip,
    remember_points: [],
    understand_points: [],
    common_mistakes: [],
    last_seen_at: '',
    next_review_at: dueReview.next_review_at,
    mastery: 0,
    mastery_status: dueReview.mastery_status,
    review_count: dueReview.review_count,
    last_reviewed_at: dueReview.last_reviewed_at
  };
}

function mergeDueReviewsWithMemories(dueReviews: DueReviewItem[], memories: MemoryItem[]): DueReviewItem[] {
  return dueReviews.map((review) => {
    const memory = memories.find((item) => item.id === review.id);
    if (!memory) return review;

    return {
      ...review,
      title: memory.title || review.title,
      error_type: memory.error_type || review.error_type,
      mastery_status: memory.mastery_status ?? review.mastery_status,
      knowledge_tags: memory.knowledge_tags.length ? memory.knowledge_tags : review.knowledge_tags,
      review_tip: memory.review_tip || review.review_tip,
      next_review_at: memory.next_review_at || review.next_review_at,
      review_count: memory.review_count ?? review.review_count,
      last_reviewed_at: memory.last_reviewed_at ?? review.last_reviewed_at
    };
  });
}

function completeMemoryReview(memory: MemoryItem, reviewedMemory: MemoryItem | undefined, reviewedAt: string): MemoryItem {
  const existingCount = getReviewCount(memory);
  const remoteCount = typeof reviewedMemory?.review_count === 'number' ? reviewedMemory.review_count : 0;
  const nextCount = remoteCount > existingCount ? remoteCount : existingCount + 1;

  return {
    ...memory,
    ...reviewedMemory,
    id: memory.id,
    mastery_status: reviewedMemory?.mastery_status || memory.mastery_status || 'reviewing',
    next_review_at: reviewedMemory?.next_review_at || memory.next_review_at,
    review_count: nextCount,
    last_reviewed_at: reviewedMemory?.last_reviewed_at || reviewedAt
  };
}

function completeDueReview(review: DueReviewItem, reviewedMemory: MemoryItem | undefined, reviewedAt: string): DueReviewItem {
  const existingCount = getReviewCount(review);
  const remoteCount = typeof reviewedMemory?.review_count === 'number' ? reviewedMemory.review_count : 0;
  const nextCount = remoteCount > existingCount ? remoteCount : existingCount + 1;

  return {
    ...review,
    title: reviewedMemory?.title || review.title,
    error_type: reviewedMemory?.error_type || review.error_type,
    mastery_status: reviewedMemory?.mastery_status || review.mastery_status || 'reviewing',
    knowledge_tags: reviewedMemory?.knowledge_tags?.length ? reviewedMemory.knowledge_tags : review.knowledge_tags,
    review_tip: reviewedMemory?.review_tip || review.review_tip,
    next_review_at: reviewedMemory?.next_review_at || review.next_review_at,
    review_count: nextCount,
    last_reviewed_at: reviewedMemory?.last_reviewed_at || reviewedAt
  };
}
