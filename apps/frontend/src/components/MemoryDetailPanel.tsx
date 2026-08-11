import { X } from 'lucide-react';
import { formatMasteryStatus, formatReviewState } from '../lib/reviewState';
import type { MemoryItem } from '../lib/types';

const knowledgeLabels = {
  MEMORIZE: '先记住',
  UNDERSTAND: '要理解',
  MIXED: '先记再懂',
  UNKNOWN: '待判断'
};

export function MemoryDetailPanel({
  memory,
  loading,
  error,
  reviewCompleting = false,
  onClose,
  onCompleteReview
}: {
  memory: MemoryItem | null;
  loading: boolean;
  error: string;
  reviewCompleting?: boolean;
  onClose: () => void;
  onCompleteReview?: (memoryId: string) => void | Promise<void>;
}) {
  if (!memory && !loading && !error) {
    return (
      <section className="panel memory-detail-panel empty-detail">
        <div className="panel-heading">
          <span>详情</span>
          <span className="mini-label">等待选择</span>
        </div>
        <p className="muted-text">点击卡片上的“查看详情”，这里会展开完整错因和复习内容。</p>
      </section>
    );
  }

  return (
    <section className="panel memory-detail-panel">
      <div className="panel-heading">
        <span>错题详情</span>
        <button className="icon-ghost-button" type="button" aria-label="关闭详情" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      {loading ? (
        <div className="mini-skeleton">
          <span />
          <span />
          <span />
        </div>
      ) : memory ? (
        <div className="memory-detail-content">
          {error ? <div className="form-error">{error}</div> : null}

          <div className="memory-detail-title">
            <span className="mini-label">{memory.error_type || '错题档案'}</span>
            <h3>{memory.title}</h3>
          </div>

          <div className="tag-row compact-tags">
            {(memory.knowledge_tags.length ? memory.knowledge_tags : ['待补充标签']).map((tag) => (
              <span className="tag" key={`${memory.id}-${tag}`}>{tag}</span>
            ))}
          </div>

          <div className="memory-detail-grid">
            <DetailBlock title="学习策略" body={memory.knowledge_type ? knowledgeLabels[memory.knowledge_type] : '待判断'} />
            <DetailBlock title="掌握度" body={`${Math.round(memory.mastery * 100)}%`} highlight />
            <DetailBlock title="复习状态" body={formatMasteryStatus(memory.mastery_status)} />
            <DetailBlock title="下次复习" body={memory.next_review_at || '待安排'} />
          </div>

          <DetailBlock title="错因摘要" body={memory.mistake_summary || '这条错题还在整理中。'} />
          <DetailBlock title="复习建议" body={memory.review_tip || '先复述错误原因，再做一道同类小题。'} />
          <DetailBlock title="需要记忆" body={joinItems(memory.remember_points, '先记录本次最小错误规则。')} />
          <DetailBlock title="需要理解" body={joinItems(memory.understand_points, '复述为什么会错，以及下次怎么检查。')} />
          <DetailBlock title="易错点" body={joinItems(memory.common_mistakes, '普通变量、数组名、边界条件容易混淆。')} />

          {onCompleteReview ? (
            <div className="memory-review-footer">
              <div>
                <span className="mini-label">复习进度</span>
                <p>{formatReviewProgress(memory)}</p>
              </div>
              <button className="primary-button review-complete-button" type="button" onClick={() => onCompleteReview(memory.id)} disabled={reviewCompleting}>
                {reviewCompleting ? '更新中...' : '已复习完成'}
              </button>
            </div>
          ) : null}
        </div>
      ) : error ? (
        <div className="form-error">{error}</div>
      ) : null}
    </section>
  );
}

function DetailBlock({ title, body, highlight = false }: { title: string; body: string; highlight?: boolean }) {
  return (
    <div className={`memory-detail-block ${highlight ? 'highlight' : ''}`}>
      <span className="mini-label">{title}</span>
      <p>{body}</p>
    </div>
  );
}

function joinItems(items: string[] | undefined, fallback: string) {
  return items?.length ? items.join('；') : fallback;
}

function formatReviewProgress(memory: MemoryItem) {
  return formatReviewState(memory);
}
