export interface ReviewStateSource {
  review_count?: number;
  last_reviewed_at?: string;
  mastery_status?: string;
}

export function getReviewCount(item: ReviewStateSource) {
  if (typeof item.review_count === 'number' && item.review_count > 0) return item.review_count;
  if (item.last_reviewed_at || item.mastery_status === 'mastered') return 1;
  return 0;
}

export function isReviewDone(item: ReviewStateSource) {
  return getReviewCount(item) > 0 || item.mastery_status === 'mastered';
}

export function formatReviewState(item: ReviewStateSource) {
  const count = getReviewCount(item);
  return count > 0 ? `已复习 ${count} 遍` : '未复习';
}

export function formatMasteryStatus(status?: string) {
  if (status === 'mastered') return '已掌握';
  if (status === 'reviewing') return '复习中';
  return '待确认';
}
