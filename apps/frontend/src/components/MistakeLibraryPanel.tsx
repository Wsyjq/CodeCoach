import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { formatReviewState, isReviewDone } from '../lib/reviewState';
import type { KnowledgeType, MemoryItem, ReviewCard } from '../lib/types';
import { MemoryDetailPanel } from './MemoryDetailPanel';
import { ReviewCardView } from './ReviewCard';

const RECENT_MEMORY_LIMIT = 2;

export function MistakeLibraryPanel({
  memories,
  loading,
  error,
  currentReview,
  knowledgeType,
  knowledgeTags,
  selectedMemory,
  detailLoading,
  detailLoadingId,
  detailError,
  reviewCompletionLoadingId,
  onOpenDetail,
  onCloseDetail,
  onCompleteReview
}: {
  memories: MemoryItem[];
  loading: boolean;
  error: boolean;
  currentReview: ReviewCard;
  knowledgeType: KnowledgeType;
  knowledgeTags: string[];
  selectedMemory: MemoryItem | null;
  detailLoading: boolean;
  detailLoadingId: string;
  detailError: string;
  reviewCompletionLoadingId: string;
  onOpenDetail: (memoryId: string) => void | Promise<void>;
  onCloseDetail: () => void;
  onCompleteReview: (memoryId: string) => void | Promise<void>;
}) {
  const [archiveOpen, setArchiveOpen] = useState(false);
  const recentMemories = memories.slice(0, RECENT_MEMORY_LIMIT);
  const hasMoreMemories = memories.length > RECENT_MEMORY_LIMIT;

  useEffect(() => {
    if (!archiveOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setArchiveOpen(false);
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [archiveOpen]);

  function openDetailFromArchive(memoryId: string) {
    setArchiveOpen(false);
    onOpenDetail(memoryId);
  }

  return (
    <section className="mistake-page">
      <ReviewCardView card={currentReview} knowledgeType={knowledgeType} knowledgeTags={knowledgeTags} />
      <MemoryDetailPanel
        memory={selectedMemory}
        loading={detailLoading}
        error={detailError}
        reviewCompleting={Boolean(selectedMemory && reviewCompletionLoadingId === selectedMemory.id)}
        onClose={onCloseDetail}
        onCompleteReview={onCompleteReview}
      />

      <section className="panel detail-panel">
        <div className="panel-heading">
          <span>我的错题</span>
          <span className="mini-label">{memories.length ? `${memories.length} 条记录` : '错题档案'}</span>
        </div>

        {loading ? (
          <div className="mini-skeleton">
            <span />
            <span />
            <span />
          </div>
        ) : error ? (
          <p className="muted-text">后端启动后会恢复错题列表。</p>
        ) : memories.length ? (
          <>
            <div className="detail-list">
              {recentMemories.map((memory) => (
                <MemoryArchiveCard
                  key={memory.id}
                  memory={memory}
                  detailLoadingId={detailLoadingId}
                  onOpenDetail={onOpenDetail}
                />
              ))}
            </div>

            {hasMoreMemories ? (
              <button className="ghost-button archive-more-button" type="button" onClick={() => setArchiveOpen(true)}>
                查看更多
                <span>{memories.length} 条错题</span>
              </button>
            ) : null}
          </>
        ) : (
          <p className="muted-text">暂无错题记忆。完成一次纠错或复盘后会出现在这里。</p>
        )}
      </section>

      {archiveOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setArchiveOpen(false)}>
          <section
            aria-labelledby="mistake-archive-title"
            aria-modal="true"
            className="mistake-archive-modal"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <span className="mini-label">全部错题</span>
                <h3 id="mistake-archive-title">我的错题档案</h3>
              </div>
              <button className="icon-ghost-button" type="button" aria-label="关闭全部错题" onClick={() => setArchiveOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <p className="archive-summary">共 {memories.length} 条错题，按当前列表顺序展示。主页面只保留最近 {RECENT_MEMORY_LIMIT} 条，完整内容从这里检索。</p>

            <div className="archive-list">
              {memories.map((memory) => (
                <MemoryArchiveCard
                  key={`archive-${memory.id}`}
                  memory={memory}
                  detailLoadingId={detailLoadingId}
                  onOpenDetail={openDetailFromArchive}
                />
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function MemoryArchiveCard({
  memory,
  detailLoadingId,
  onOpenDetail
}: {
  memory: MemoryItem;
  detailLoadingId: string;
  onOpenDetail: (memoryId: string) => void | Promise<void>;
}) {
  return (
    <article className="detail-item">
      <div className="detail-item-heading">
        <strong>{memory.title}</strong>
        <div className="detail-item-meta">
          <span className="mastery-chip">{Math.round(memory.mastery * 100)}%</span>
          <span className={`review-state-badge ${isReviewDone(memory) ? 'done' : 'pending'}`}>{formatReviewState(memory)}</span>
        </div>
      </div>
      <p>{memory.mistake_summary || memory.review_tip || '这条错题还在整理中。'}</p>
      <div className="tag-row compact-tags">
        {(memory.knowledge_tags.length ? memory.knowledge_tags : [memory.error_type]).map((tag) => (
          <span className="tag" key={`${memory.id}-${tag}`}>{tag}</span>
        ))}
      </div>
      {memory.next_review_at ? <small>下次复习：{memory.next_review_at}</small> : null}
      <div className="card-action-row">
        <button className="ghost-button compact" type="button" onClick={() => onOpenDetail(memory.id)} disabled={detailLoadingId === memory.id}>
          {detailLoadingId === memory.id ? '读取中...' : '查看详情'}
        </button>
      </div>
    </article>
  );
}
