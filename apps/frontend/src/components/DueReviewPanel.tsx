import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { formatReviewState, isReviewDone } from '../lib/reviewState';
import type { DueReviewItem } from '../lib/types';

const RECENT_REVIEW_LIMIT = 2;
type ReviewFilter = 'pending' | 'reviewed';

export function DueReviewPanel({
  reviews,
  loading,
  error,
  compact = false,
  detailLoadingId = '',
  onOpenDetail
}: {
  reviews: DueReviewItem[];
  loading: boolean;
  error: boolean;
  compact?: boolean;
  detailLoadingId?: string;
  onOpenDetail?: (memoryId: string) => void | Promise<void>;
}) {
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [activeFilter, setActiveFilter] = useState<ReviewFilter>('pending');
  const pendingReviews = reviews.filter((review) => !isReviewDone(review));
  const reviewedReviews = reviews.filter(isReviewDone);
  const filteredReviews = activeFilter === 'pending' ? pendingReviews : reviewedReviews;
  const visibleReviews = filteredReviews.slice(0, RECENT_REVIEW_LIMIT);
  const activeFilterLabel = activeFilter === 'pending' ? '开始复习' : '已复习';

  useEffect(() => {
    if (!archiveOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setArchiveOpen(false);
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [archiveOpen]);

  useEffect(() => {
    setArchiveOpen(false);
  }, [activeFilter]);

  function openDetailFromArchive(reviewId: string) {
    setArchiveOpen(false);
    onOpenDetail?.(reviewId);
  }

  return (
    <section className={`panel detail-panel ${compact ? 'compact-panel' : ''}`}>
      <div className="panel-heading">
        <span>今日复习</span>
        <div className="review-heading-actions">
          {!compact ? (
            <div className="review-filter-tabs" aria-label="复习状态筛选">
              <button
                aria-pressed={activeFilter === 'pending'}
                className={`review-filter-button ${activeFilter === 'pending' ? 'is-active' : ''}`}
                type="button"
                onClick={() => setActiveFilter('pending')}
              >
                开始复习
                <span>{pendingReviews.length}</span>
              </button>
              <button
                aria-pressed={activeFilter === 'reviewed'}
                className={`review-filter-button ${activeFilter === 'reviewed' ? 'is-active' : ''}`}
                type="button"
                onClick={() => setActiveFilter('reviewed')}
              >
                已复习
                <span>{reviewedReviews.length}</span>
              </button>
            </div>
          ) : null}
          <span className="mini-label">{filteredReviews.length ? `${filteredReviews.length} 个任务` : '复习任务'}</span>
        </div>
      </div>

      {loading ? (
        <div className="mini-skeleton">
          <span />
          <span />
        </div>
      ) : error ? (
        <p className="muted-text">暂时无法读取今日复习，后端恢复后会自动显示。</p>
      ) : visibleReviews.length ? (
        <>
          <div className="detail-list">
            {visibleReviews.map((review) => (
              <ReviewArchiveCard
                key={review.id}
                review={review}
                detailLoadingId={detailLoadingId}
                onOpenDetail={onOpenDetail}
              />
            ))}
          </div>

          {!compact ? (
            <button className="ghost-button archive-more-button" type="button" onClick={() => setArchiveOpen(true)}>
              查看更多
              <span>{filteredReviews.length} 个任务</span>
            </button>
          ) : null}
        </>
      ) : (
        <p className="muted-text">
          {activeFilter === 'pending'
            ? '今天暂时没有待开始的复习任务。'
            : '当前还没有已复习的题目。完成复习后会出现在这里。'}
        </p>
      )}

      {archiveOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setArchiveOpen(false)}>
          <section
            aria-labelledby="review-archive-title"
            aria-modal="true"
            className="mistake-archive-modal review-archive-modal"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <span className="mini-label">全部复习</span>
                <h3 id="review-archive-title">今日复习任务</h3>
              </div>
              <button className="icon-ghost-button" type="button" aria-label="关闭全部复习" onClick={() => setArchiveOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <p className="archive-summary">共 {filteredReviews.length} 个{activeFilterLabel}任务，主页面只保留前 {RECENT_REVIEW_LIMIT} 个，完整复习清单从这里查看。</p>

            <div className="archive-list">
              {filteredReviews.map((review) => (
                <ReviewArchiveCard
                  key={`review-archive-${review.id}`}
                  review={review}
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

function ReviewArchiveCard({
  review,
  detailLoadingId,
  onOpenDetail
}: {
  review: DueReviewItem;
  detailLoadingId: string;
  onOpenDetail?: (memoryId: string) => void | Promise<void>;
}) {
  return (
    <article className="detail-item due">
      <div className="detail-item-heading">
        <strong>{review.title}</strong>
        <div className="detail-item-meta">
          <span className="error-chip">{review.error_type}</span>
          <span className={`review-state-badge ${isReviewDone(review) ? 'done' : 'pending'}`}>{formatReviewState(review)}</span>
        </div>
      </div>
      <p>{review.review_tip || '先复述错误原因，再做一道同类小题。'}</p>
      <div className="tag-row compact-tags">
        {review.knowledge_tags.map((tag) => (
          <span className="tag" key={`${review.id}-${tag}`}>{tag}</span>
        ))}
      </div>
      {review.next_review_at ? <small>安排：{review.next_review_at}</small> : null}
      {onOpenDetail ? (
        <div className="card-action-row">
          <button className="ghost-button compact" type="button" onClick={() => onOpenDetail(review.id)} disabled={detailLoadingId === review.id}>
            {detailLoadingId === review.id ? '读取中...' : '查看详情'}
          </button>
        </div>
      ) : null}
    </article>
  );
}
