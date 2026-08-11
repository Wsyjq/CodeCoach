from fastapi import APIRouter

from app.tools.knowledge_tool import get_knowledge_source_summary

router = APIRouter()


@router.get("/knowledge/sources")
def knowledge_sources() -> dict:
    return get_knowledge_source_summary()
