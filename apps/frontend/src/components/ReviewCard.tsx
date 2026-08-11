import type { KnowledgeType, ReviewCard } from '../lib/types';

const knowledgeLabels: Record<KnowledgeType, string> = {
  MEMORIZE: '记忆型',
  UNDERSTAND: '理解型',
  MIXED: '混合型',
  UNKNOWN: '待分类'
};

export function ReviewCardView({
  card,
  knowledgeType,
  knowledgeTags
}: {
  card: ReviewCard;
  knowledgeType: KnowledgeType;
  knowledgeTags: string[];
}) {
  const hasCard = Boolean(card.id || card.title || card.error_type);
  const cardKnowledgeType = card.knowledge_type ?? knowledgeType;
  const cardTags = card.knowledge_tags?.length ? card.knowledge_tags : knowledgeTags;
  const rememberPoints = card.remember_points?.length ? card.remember_points : card.review_tip ? [card.review_tip] : [];
  const understandPoints = card.understand_points?.length ? card.understand_points : [];
  const commonMistakes = card.common_mistakes?.length ? card.common_mistakes : card.mistake_summary ? [card.mistake_summary] : [];

  if (!hasCard) {
    return (
      <section className="panel review-card empty-review">
        <div className="panel-heading">
          <span>错题复盘卡片</span>
          <span className="badge">等待生成</span>
        </div>
        <p className="muted-text">本次分析完成后，复盘卡片会在这里形成学习档案。</p>
      </section>
    );
  }

  return (
    <section className="panel review-card">
      <div className="panel-heading">
        <span>错题复盘卡片</span>
        <span className="badge saved">已准备写入记忆库</span>
      </div>
      <div className="review-grid">
        <div>
          <span className="mini-label">标题</span>
          <strong>{card.title || '本次错题复盘'}</strong>
        </div>
        <div>
          <span className="mini-label">错误类型</span>
          <strong>{card.error_type || '待识别'}</strong>
        </div>
        <div>
          <span className="mini-label">知识类型</span>
          <strong>{knowledgeLabels[cardKnowledgeType]}</strong>
        </div>
        <div>
          <span className="mini-label">下次复习</span>
          <strong className="review-date">{card.next_review_at || '待安排'}</strong>
        </div>
      </div>

      {cardTags.length ? (
        <div className="tag-row">
          {cardTags.map((tag) => (
            <span className="tag" key={tag}>{tag}</span>
          ))}
        </div>
      ) : null}

      <div className="review-notes">
        <ReviewNote title="需要记忆" items={rememberPoints} fallback="先记录本次最小错误规则。" />
        <ReviewNote title="需要理解" items={understandPoints} fallback="复述为什么会错，以及下次怎么检查。" />
        <ReviewNote title="易错点" items={commonMistakes} fallback="普通变量、数组名、边界条件容易混淆。" />
      </div>
    </section>
  );
}

function ReviewNote({ title, items, fallback }: { title: string; items: string[]; fallback: string }) {
  return (
    <div className="review-note">
      <span className="mini-label">{title}</span>
      <p>{items.length ? items.join('；') : fallback}</p>
    </div>
  );
}
