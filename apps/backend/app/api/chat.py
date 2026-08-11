from fastapi import APIRouter, Depends

from app.auth import current_user_id
from app.agents.orchestrator import handle_chat
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user_id: str = Depends(current_user_id)) -> ChatResponse:
    request.user_id = user_id
    return handle_chat(request)
