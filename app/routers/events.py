from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.database import get_db
from app.services.event_parser import EventService
from app.services.rule_based_events import RuleBasedEventGenerator, PriorityManager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/api/events", tags=["events"])


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


# 전역 서비스 인스턴스
event_service = EventService()
rule_based_generator = RuleBasedEventGenerator()
priority_manager = PriorityManager()


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


@router.post("/generate-rule-based", 
             summary="규칙 기반 이벤트 생성",
             description="생일, 기념일, 보험 갱신, 정기 팔로업 등 규칙 기반 이벤트를 자동 생성합니다.")
async def generate_rule_based_events(
    target_days: int = 365,
    db: AsyncSession = Depends(get_db)
):
    """
    규칙 기반 이벤트를 자동 생성합니다.
    
    - **target_days**: 생성할 이벤트의 날짜 범위 (기본값: 365일)
    
    생성되는 이벤트 유형:
    - 생일 이벤트: 30일 전, 7일 전, 1일 전
    - 보험 갱신: 60일 전, 30일 전, 14일 전, 7일 전
    - 정기 팔로업: 고객별 주기에 따라
    - 계절별 안내: 봄, 여름, 가을, 겨울
    """
    try:
        logger.info(f"규칙 기반 이벤트 생성 요청 (범위: {target_days}일)")
        
        result = await rule_based_generator.generate_all_rule_based_events(
            db_session=db,
            target_date_range=target_days
        )
        
        return {
            "success": True,
            "message": f"규칙 기반 이벤트 {result['total_events_created']}개가 생성되었습니다.",
            **result
        }
        
    except Exception as e:
        logger.error(f"규칙 기반 이벤트 생성 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update-priorities", 
            summary="이벤트 우선순위 업데이트",
            description="모든 이벤트의 우선순위를 동적으로 재계산합니다.")
async def update_event_priorities(
    db: AsyncSession = Depends(get_db)
):
    """
    모든 이벤트의 우선순위를 동적으로 재계산합니다.
    
    고려 요소:
    - 고객 중요도 (보험 상품 수, 최근 활동)
    - 시간 긴급도 (이벤트까지 남은 시간)
    - 이벤트 타입 (통화 > 일정 > 알림 > 메시지)
    
    우선순위:
    - urgent: 즉시 처리 필요
    - high: 높은 우선순위
    - medium: 보통 우선순위  
    - low: 낮은 우선순위
    """
    try:
        logger.info("이벤트 우선순위 업데이트 요청")
        
        result = await priority_manager.update_event_priorities(db_session=db)
        
        return {
            "success": True,
            "message": f"{result['events_updated']}개 이벤트의 우선순위가 업데이트되었습니다.",
            **result
        }
        
    except Exception as e:
        logger.error(f"이벤트 우선순위 업데이트 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority/{priority}", 
            summary="우선순위별 이벤트 조회",
            description="특정 우선순위의 이벤트들을 조회합니다.")
async def get_events_by_priority(
    priority: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    특정 우선순위의 이벤트들을 조회합니다.
    
    - **priority**: 우선순위 (urgent, high, medium, low)
    - **days**: 조회할 기간 (기본값: 30일)
    """
    try:
        # 우선순위 유효성 검증
        valid_priorities = ['urgent', 'high', 'medium', 'low']
        if priority not in valid_priorities:
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 우선순위입니다. 유효한 값: {valid_priorities}"
            )
        
        from sqlalchemy import select, and_
        from datetime import datetime, timedelta
        from app.db_models import Event
        
        # 특정 우선순위의 이벤트 조회
        end_date = datetime.now() + timedelta(days=days)
        
        stmt = select(Event).where(
            and_(
                Event.priority == priority,
                Event.status == "pending",
                Event.scheduled_date <= end_date
            )
        ).order_by(Event.scheduled_date.asc())
        
        result = await db.execute(stmt)
        events = result.scalars().all()
        
        return {
            "priority": priority,
            "total_events": len(events),
            "events": [
                {
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                    "scheduled_date": event.scheduled_date.isoformat(),
                    "priority": event.priority,
                    "description": event.description,
                    "status": event.status,
                    "customer_id": str(event.customer_id) if event.customer_id else None
                }
                for event in events
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"우선순위별 이벤트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/urgent-today", 
            summary="오늘의 긴급 이벤트",
            description="오늘 처리해야 할 긴급 및 고우선순위 이벤트를 조회합니다.")
async def get_urgent_events_today(
    db: AsyncSession = Depends(get_db)
):
    """
    오늘 처리해야 할 긴급 및 고우선순위 이벤트를 조회합니다.
    """
    try:
        from sqlalchemy import select, and_, or_
        from datetime import datetime, date, timedelta
        from app.db_models import Event, Customer
        
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # 오늘과 내일의 긴급/높은 우선순위 이벤트 조회
        stmt = select(Event).join(Customer, Event.customer_id == Customer.customer_id, isouter=True).where(
            and_(
                Event.scheduled_date >= datetime.combine(today, datetime.min.time()),
                Event.scheduled_date < datetime.combine(tomorrow, datetime.min.time()),
                or_(Event.priority == "urgent", Event.priority == "high"),
                Event.status == "pending"
            )
        ).order_by(Event.priority.desc(), Event.scheduled_date.asc())
        
        result = await db.execute(stmt)
        events = result.scalars().all()
        
        # 고객 정보와 함께 반환
        urgent_events = []
        for event in events:
            customer_name = "알 수 없음"
            if event.customer_id:
                customer_stmt = select(Customer).where(Customer.customer_id == event.customer_id)
                customer_result = await db.execute(customer_stmt)
                customer = customer_result.scalar_one_or_none()
                if customer:
                    customer_name = customer.name or "고객"
            
            urgent_events.append({
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "scheduled_date": event.scheduled_date.isoformat(),
                "priority": event.priority,
                "description": event.description,
                "status": event.status,
                "customer_name": customer_name,
                "customer_id": str(event.customer_id) if event.customer_id else None
            })
        
        return {
            "date": today.isoformat(),
            "total_urgent_events": len(urgent_events),
            "urgent_count": len([e for e in urgent_events if e["priority"] == "urgent"]),
            "high_count": len([e for e in urgent_events if e["priority"] == "high"]),
            "events": urgent_events
        }
        
    except Exception as e:
        logger.error(f"오늘의 긴급 이벤트 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))