import { BookMarked, CalendarCheck } from 'lucide-react';
import type { MemoryItem, StatsSummary } from '../lib/types';

export function LearningSnapshot({
  stats,
  memories,
  loading,
  error,
  onOpenMistakes,
  onOpenReviews
}: {
  stats: StatsSummary | null;
  memories: MemoryItem[];
  loading: boolean;
  error: boolean;
  onOpenMistakes: () => void;
  onOpenReviews: () => void;
}) {
  if (loading) {
    return (
      <section className="panel snapshot-panel">
        <div className="panel-heading">学习画像</div>
        <div className="mini-skeleton">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel snapshot-panel">
        <div className="panel-heading">
          <span>学习画像</span>
          <span className="badge error">连接失败</span>
        </div>
        <p className="muted-text">后端启动后会恢复学习统计和错题记忆。</p>
      </section>
    );
  }

  if (!stats) {
    return (
      <section className="panel snapshot-panel">
        <div className="panel-heading">学习画像</div>
        <p className="muted-text">暂无学习统计。</p>
      </section>
    );
  }

  return (
    <section className="panel snapshot-panel">
      <div className="panel-heading">
        <span>学习画像</span>
        <span className="mini-label">{stats.time_range}</span>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <span>错题记录</span>
          <strong>{stats.total_records}</strong>
        </div>
        <div className="metric-card">
          <span>待复习</span>
          <strong>{stats.review_due_count}</strong>
        </div>
        <div className="metric-card">
          <span>掌握度</span>
          <strong>{Math.round(stats.mastery_avg * 100)}%</strong>
        </div>
      </div>

      <div className="weak-tags">
        {(stats.weak_tags.length ? stats.weak_tags : ['暂无薄弱标签']).map((tag) => (
          <span className="tag danger" key={tag}>{tag}</span>
        ))}
      </div>

      {stats.recommended_actions.length ? (
        <div className="snapshot-advice">
          <span className="mini-label">建议动作</span>
          <p>{stats.recommended_actions[0]}</p>
        </div>
      ) : null}

      <div className="snapshot-actions">
        <button className="ghost-button snapshot-link" type="button" onClick={onOpenMistakes}>
          <BookMarked size={16} />
          我的错题
          <span>{memories.length}</span>
        </button>
        <button className="ghost-button snapshot-link" type="button" onClick={onOpenReviews}>
          <CalendarCheck size={16} />
          今日复习
          <span>{stats.review_due_count}</span>
        </button>
      </div>
    </section>
  );
}
