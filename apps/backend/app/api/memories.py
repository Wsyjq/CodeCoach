from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_user_id
from app.tools.memory_tool import get_memory_by_id, list_demo_memories, mark_memory_reviewed

router = APIRouter()


class ReviewOutcomeRequest(BaseModel):
    user_id: str = "demo_user"
    outcome: Literal["again", "reviewed", "mastered"] = "reviewed"


@router.get("/memories")
def memories(user_id: str = Depends(current_user_id)) -> dict:
    return {"items": list_demo_memories(user_id)}


@router.get("/memories/{memory_id}")
def memory_detail(memory_id: str, user_id: str = Depends(current_user_id)) -> dict:
    memory = get_memory_by_id(user_id, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.post("/memories/{memory_id}/review")
def review_memory(memory_id: str, request: ReviewOutcomeRequest, user_id: str = Depends(current_user_id)) -> dict:
    memory = mark_memory_reviewed(user_id, memory_id, request.outcome)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory
