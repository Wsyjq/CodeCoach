from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user_id
from app.config import settings
from app.tools.trace_tool import list_tool_traces

router = APIRouter()


@router.get("/traces")
def traces(session_id: str = "", turn_id: str = "", user_id: str = Depends(current_user_id)) -> dict:
    if not settings.expose_traces:
        raise HTTPException(status_code=404, detail="Not found")
    return {"items": list_tool_traces(user_id=user_id, session_id=session_id, turn_id=turn_id)}
