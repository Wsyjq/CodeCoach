import type { SimilarMemory } from '../lib/types';

export function SimilarMemoryBanner({ memory }: { memory: SimilarMemory }) {
  if (!memory.matched) return null;
  const seenAt = memory.first_seen_at || memory.last_seen_at;
  return (
    <section className="memory-banner">
      <span>{memory.exact_match ? '历史重复提醒' : '历史相似提醒'}</span>
      <p>
        {memory.exact_match
          ? `这道题你${seenAt ? `在 ${seenAt} ` : ''}已经问过一模一样的了，不会重复加入错题本。`
          : `这道题和你之前的「${memory.title || '相似错题'}」很像。`}
      </p>
      {memory.mistake_summary ? <p>上次你错在：{memory.mistake_summary}</p> : null}
      {memory.review_tip ? <p>这次请重点检查：{memory.review_tip}</p> : null}
    </section>
  );
}
