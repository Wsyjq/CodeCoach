from fastapi import APIRouter, Depends

from app.auth import current_user_id
from app.tools.stats_tool import query_learning_stats

router = APIRouter()


@router.get("/stats/summary")
def stats_summary(limit: int | None = None, user_id: str = Depends(current_user_id)) -> dict:
    return query_learning_stats(user_id=user_id, metric="common_errors", time_range="7d", limit=limit)


@router.get("/reviews/due")
def due_reviews(
    limit: int | None = None,
    date: str | None = None,
    status: str | None = None,
    user_id: str = Depends(current_user_id),
) -> dict:
    return query_learning_stats(
        user_id=user_id,
        metric="today_review",
        time_range="today",
        limit=limit,
        target_date=date,
        status=status,
    )
