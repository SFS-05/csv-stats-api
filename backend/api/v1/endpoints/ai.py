"""
AI analysis endpoints: dataset summary, recommendations, conversational chat.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.ai.analyzer import DatasetAnalyzer
from backend.api.v1.dependencies import CurrentUser, DBSession
from backend.core.exceptions import AIGroundingError, AIServiceError
from backend.repositories.dataset_repo import DatasetRepository

router = APIRouter(prefix="/datasets/{dataset_id}/ai", tags=["AI Analysis"])


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


async def _get_ready_dataset_with_profiling(dataset_id, current_user, session):
    """Shared helper: fetch dataset and verify profiling is complete."""
    repo = DatasetRepository(session)
    dataset = await repo.get_by_id_and_owner(dataset_id, current_user.id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.profiling_summary:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Dataset profiling must complete before AI analysis",
        )
    return dataset


@router.get(
    "/summary",
    summary="Get AI-generated dataset summary grounded in profiling statistics",
)
async def get_ai_summary(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> dict:
    """
    Generate an AI-powered dataset summary.
    The AI is grounded in actual computed statistics — no hallucination.
    Results are cached in the dataset record after first generation.
    """
    dataset = await _get_ready_dataset_with_profiling(dataset_id, current_user, session)

    # Return cached summary if available
    if dataset.ai_summary and dataset.ai_summary.get("summary"):
        return dataset.ai_summary

    profiling_summary = dataset.profiling_summary or {}
    column_profiles = (dataset.column_profiles or {}).get("profiles", [])

    try:
        analyzer = DatasetAnalyzer()
        result = analyzer.generate_summary(
            profiling_summary=profiling_summary,
            column_profiles=column_profiles,
            schema_info=dataset.schema_info,
        )
    except (AIServiceError, AIGroundingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # Cache the result
    repo = DatasetRepository(session)
    await repo.save_ai_summary(dataset_id, result)

    return result


@router.get(
    "/recommendations",
    summary="Get AI-generated preprocessing and ML recommendations",
)
async def get_recommendations(
    dataset_id: UUID,
    current_user: CurrentUser,
    session: DBSession,
) -> dict:
    """
    Generate preprocessing and ML readiness recommendations.
    Grounded in actual profiling statistics.
    """
    dataset = await _get_ready_dataset_with_profiling(dataset_id, current_user, session)

    profiling_summary = dataset.profiling_summary or {}
    column_profiles = (dataset.column_profiles or {}).get("profiles", [])

    try:
        analyzer = DatasetAnalyzer()
        return analyzer.generate_recommendations(
            profiling_summary=profiling_summary,
            column_profiles=column_profiles,
        )
    except (AIServiceError, AIGroundingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.post(
    "/chat",
    summary="Conversational dataset assistant",
)
async def chat_with_dataset(
    dataset_id: UUID,
    request: ChatRequest,
    current_user: CurrentUser,
    session: DBSession,
) -> dict:
    """
    Ask questions about the dataset in natural language.
    The assistant uses real profiling statistics to answer.

    Example questions:
    - "What does this dataset contain?"
    - "Which columns have the most missing values?"
    - "What should I clean before training an ML model?"
    - "Which numeric columns are highly skewed?"
    """
    dataset = await _get_ready_dataset_with_profiling(dataset_id, current_user, session)

    profiling_summary = dataset.profiling_summary or {}
    column_profiles = (dataset.column_profiles or {}).get("profiles", [])

    # Convert history to OpenAI message format
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in request.history
        if msg.role in ("user", "assistant")
    ]

    try:
        analyzer = DatasetAnalyzer()
        response = analyzer.chat(
            profiling_summary=profiling_summary,
            column_profiles=column_profiles,
            conversation_history=history,
            user_message=request.message,
        )
    except (AIServiceError, AIGroundingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return {
        "message": response,
        "role": "assistant",
        "dataset_id": str(dataset_id),
    }
