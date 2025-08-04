from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.database import get_db
from app.services.event_parser import EventService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


class EventProcessRequest(BaseModel):
    memo_id: str = Field(description="이벤트를 생성할 메모 ID")


class EventStatusUpdateRequest(BaseModel):
    event_id: str = Field(description="상태를 업데이트할 이벤트 ID")
    status: str = Field(description="새로운 상태 값 (pending, completed, cancelled)")


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    scheduled_date: str
    priority: str
    description: str
    status: str


class EventsResponse(BaseModel):
    customer_id: Optional[str] = None
    total_events: int
    events_by_type: Dict[str, List[EventResponse]]


class EventProcessResponse(BaseModel):
    memo_id: str
    events_created: int
    events: List[EventResponse]


# 전역 이벤트 서비스 인스턴스
event_service = EventService()


@router.post("/process-memo", 
             response_model=EventProcessResponse,
             summary="메모에서 이벤트 생성",
             description="메모 분석 결과에서 시간 표현과 필요 조치를 파싱하여 이벤트를 생성합니다.")
async def process_memo_for_events(
    request: EventProcessRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    메모를 분석하여 이벤트를 자동 생성합니다.
    
    - **memo_id**: 이벤트를 생성할 메모의 ID
    
    메모의 refined_memo에서 다음 정보를 추출하여 이벤트를 생성합니다:
    - time_expressions: 시간 관련 표현들
    - required_actions: 필요한 후속 조치들  
    - keywords: 주요 키워드들
    
    생성되는 이벤트 타입:
    - call: 전화 관련
    - message: 메시지/문자 관련
    - reminder: 알림/리마인더
    - calendar: 일정/미팅 관련
    """
    try:
        logger.info(f"메모 {request.memo_id}에서 이벤트 생성 요청")
        
        result = await event_service.process_memo_for_events(
            memo_id=request.memo_id,
            db_session=db
        )
        
        return EventProcessResponse(**result)
        
    except Exception as e:
        logger.error(f"메모 이벤트 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming", 
            response_model=EventsResponse,
            summary="향후 예정 이벤트 조회",
            description="향후 N일간의 예정된 이벤트를 조회합니다.")
async def get_upcoming_events(
    customer_id: Optional[str] = None,
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """
    향후 예정된 이벤트들을 조회합니다.
    
    - **customer_id**: 특정 고객의 이벤트만 조회 (선택사항)
    - **days**: 조회할 기간 (기본값: 7일)
    
    반환되는 이벤트는 날짜순으로 정렬되며, 우선순위별로 분류됩니다.
    """
    try:
        logger.info(f"향후 {days}일간 이벤트 조회 (고객: {customer_id or '전체'})")
        
        result = await event_service.get_customer_events(
            customer_id=customer_id,
            days=days,
            db_session=db
        )
        
        return EventsResponse(**result)
        
    except Exception as e:
        logger.error(f"예정 이벤트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/status", 
            response_model=Dict[str, Any],
            summary="이벤트 상태 업데이트",
            description="이벤트의 상태를 변경합니다.")
async def update_event_status(
    request: EventStatusUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    이벤트 상태를 업데이트합니다.
    
    - **event_id**: 상태를 변경할 이벤트의 ID
    - **status**: 새로운 상태 값
      - pending: 대기 중
      - completed: 완료
      - cancelled: 취소
    """
    try:
        logger.info(f"이벤트 {request.event_id} 상태를 {request.status}로 변경")
        
        # 상태 유효성 검증
        valid_statuses = ['pending', 'completed', 'cancelled']
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"유효하지 않은 상태입니다. 유효한 상태: {valid_statuses}"
            )
        
        updated_event = await event_service.event_generator.update_event_status(
            event_id=request.event_id,
            status=request.status,
            db_session=db
        )
        
        return {
            "event_id": str(updated_event.event_id),
            "status": updated_event.status,
            "updated_at": updated_event.scheduled_date.isoformat(),
            "message": f"이벤트 상태가 {request.status}로 업데이트되었습니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이벤트 상태 업데이트 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer/{customer_id}", 
            response_model=EventsResponse,
            summary="고객별 이벤트 조회",
            description="특정 고객의 모든 이벤트를 조회합니다.")
async def get_customer_events(
    customer_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 고객의 이벤트를 조회합니다.
    
    - **customer_id**: 조회할 고객의 ID
    - **days**: 조회할 기간 (기본값: 30일)
    
    해당 고객과 관련된 모든 유형의 이벤트를 반환합니다.
    """
    try:
        logger.info(f"고객 {customer_id}의 향후 {days}일간 이벤트 조회")
        
        result = await event_service.get_customer_events(
            customer_id=customer_id,
            days=days,
            db_session=db
        )
        
        return EventsResponse(**result)
        
    except Exception as e:
        logger.error(f"고객 이벤트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", 
            summary="이벤트 통계 조회",
            description="전체 이벤트 통계를 조회합니다.")
async def get_event_statistics(
    db: AsyncSession = Depends(get_db)
):
    """
    전체 이벤트 통계를 조회합니다.
    
    다음 정보를 포함합니다:
    - 이벤트 타입별 개수
    - 상태별 개수  
    - 우선순위별 개수
    - 최근 생성된 이벤트들
    """
    try:
        from sqlalchemy import select, func
        from app.db_models import Event
        
        # 이벤트 타입별 통계
        type_stats = await db.execute(
            select(Event.event_type, func.count(Event.event_id))
            .group_by(Event.event_type)
        )
        type_counts = dict(type_stats.all())
        
        # 상태별 통계
        status_stats = await db.execute(
            select(Event.status, func.count(Event.event_id))
            .group_by(Event.status)
        )
        status_counts = dict(status_stats.all())
        
        # 우선순위별 통계
        priority_stats = await db.execute(
            select(Event.priority, func.count(Event.event_id))
            .group_by(Event.priority)
        )
        priority_counts = dict(priority_stats.all())
        
        # 전체 이벤트 수
        total_events = await db.execute(select(func.count(Event.event_id)))
        total_count = total_events.scalar()
        
        return {
            "total_events": total_count,
            "by_type": type_counts,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "generated_at": "이벤트 통계"
        }
        
    except Exception as e:
        logger.error(f"이벤트 통계 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))