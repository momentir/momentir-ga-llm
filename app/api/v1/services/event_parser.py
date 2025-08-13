import re
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db_models import Event, CustomerMemo, Customer
import logging

logger = logging.getLogger(__name__)


class TimeExpressionParser:
    """시간 표현을 파싱하여 구체적인 날짜로 변환하는 클래스"""
    
    def __init__(self):
        # 시간 표현 패턴 정의
        self.patterns = {
            # 상대적 시간 표현
            'days_later': r'(\d+)일?\s*(?:후|뒤)',
            'weeks_later': r'(\d+)주\s*(?:후|뒤)',
            'weeks_later_alt': r'(\d+)주일\s*(?:후|뒤)',
            'months_later': r'(\d+)개?월\s*(?:후|뒤)',
            'tomorrow': r'내일',
            'day_after_tomorrow': r'모레',
            'next_week': r'다음\s*주|담주',
            'next_month': r'다음\s*달|담달',
            'next_year': r'내년|다음\s*해',
            
            # 요일 관련 표현
            'this_monday': r'이번\s*주\s*월요일',
            'this_tuesday': r'이번\s*주\s*화요일',
            'this_wednesday': r'이번\s*주\s*수요일',
            'this_thursday': r'이번\s*주\s*목요일',
            'this_friday': r'이번\s*주\s*금요일',
            'this_saturday': r'이번\s*주\s*토요일',
            'this_sunday': r'이번\s*주\s*일요일',
            
            'next_monday': r'다음\s*주\s*월요일',
            'next_tuesday': r'다음\s*주\s*화요일',
            'next_wednesday': r'다음\s*주\s*수요일',
            'next_thursday': r'다음\s*주\s*목요일',
            'next_friday': r'다음\s*주\s*금요일',
            'next_saturday': r'다음\s*주\s*토요일',
            'next_sunday': r'다음\s*주\s*일요일',
            
            # 구체적 날짜 표현
            'specific_date': r'(\d{4})[-년](\d{1,2})[-월](\d{1,2})일?',
            'month_day': r'(\d{1,2})월\s*(\d{1,2})일',
            
            # 시간 표현
            'morning': r'오전|아침',
            'afternoon': r'오후|점심',
            'evening': r'저녁|밤',
            'time_format': r'(\d{1,2}):(\d{2})|(\d{1,2})시\s*(\d{1,2})?분?',
        }
        
        # 요일 매핑
        self.weekdays = {
            '월요일': 0, '화요일': 1, '수요일': 2, '목요일': 3,
            '금요일': 4, '토요일': 5, '일요일': 6
        }
    
    def parse_time_expression(self, expression: str, base_date: date = None) -> Optional[date]:
        """
        시간 표현을 파싱하여 구체적인 날짜를 반환합니다.
        """
        if base_date is None:
            base_date = date.today()
        
        expression = expression.strip()
        logger.info(f"시간 표현 파싱 시도: '{expression}'")
        
        # 상대적 시간 표현 처리
        for pattern_name, pattern in self.patterns.items():
            match = re.search(pattern, expression)
            if match:
                try:
                    parsed_date = self._handle_pattern(pattern_name, match, base_date)
                    if parsed_date:
                        logger.info(f"파싱 성공: '{expression}' -> {parsed_date}")
                        return parsed_date
                except Exception as e:
                    logger.warning(f"패턴 '{pattern_name}' 처리 중 오류: {e}")
                    continue
        
        logger.warning(f"파싱 실패: '{expression}'")
        return None
    
    def _handle_pattern(self, pattern_name: str, match: re.Match, base_date: date) -> Optional[date]:
        """패턴별 날짜 계산 처리"""
        
        if pattern_name == 'days_later':
            days = int(match.group(1))
            return base_date + timedelta(days=days)
        
        elif pattern_name == 'weeks_later' or pattern_name == 'weeks_later_alt':
            weeks = int(match.group(1))
            return base_date + timedelta(weeks=weeks)
        
        elif pattern_name == 'months_later':
            months = int(match.group(1))
            # 월 계산은 대략적으로 30일로 처리
            return base_date + timedelta(days=months * 30)
        
        elif pattern_name == 'tomorrow':
            return base_date + timedelta(days=1)
        
        elif pattern_name == 'day_after_tomorrow':
            return base_date + timedelta(days=2)
        
        elif pattern_name == 'next_week':
            # 다음 주 월요일 계산
            days_until_next_monday = 7 - base_date.weekday()
            if days_until_next_monday <= 0:
                days_until_next_monday += 7
            return base_date + timedelta(days=days_until_next_monday)
        
        elif pattern_name == 'next_month':
            # 다음 달 1일로 설정
            if base_date.month == 12:
                return date(base_date.year + 1, 1, 1)
            else:
                return date(base_date.year, base_date.month + 1, 1)
        
        elif pattern_name == 'next_year':
            return date(base_date.year + 1, 1, 1)
        
        # 이번 주 요일들
        elif pattern_name.startswith('this_'):
            weekday_name = pattern_name.replace('this_', '')
            return self._get_this_week_date(base_date, weekday_name)
        
        # 다음 주 요일들
        elif pattern_name.startswith('next_'):
            weekday_name = pattern_name.replace('next_', '')
            return self._get_next_week_date(base_date, weekday_name)
        
        elif pattern_name == 'specific_date':
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return date(year, month, day)
        
        elif pattern_name == 'month_day':
            month = int(match.group(1))
            day = int(match.group(2))
            year = base_date.year
            # 해당 날짜가 이미 지났으면 내년으로 설정
            target_date = date(year, month, day)
            if target_date < base_date:
                target_date = date(year + 1, month, day)
            return target_date
        
        return None
    
    def _get_this_week_date(self, base_date: date, weekday_name: str) -> Optional[date]:
        """이번 주의 특정 요일 날짜를 계산"""
        weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if weekday_name not in weekday_names:
            return None
        
        target_weekday = weekday_names.index(weekday_name)
        current_weekday = base_date.weekday()
        
        days_diff = target_weekday - current_weekday
        if days_diff < 0:  # 이미 지난 요일이면 다음 주로
            days_diff += 7
        
        return base_date + timedelta(days=days_diff)
    
    def _get_next_week_date(self, base_date: date, weekday_name: str) -> Optional[date]:
        """다음 주의 특정 요일 날짜를 계산"""
        this_week_date = self._get_this_week_date(base_date, weekday_name)
        if this_week_date:
            return this_week_date + timedelta(days=7)
        return None


class EventGenerator:
    """메모 분석 결과에서 이벤트를 생성하는 클래스"""
    
    def __init__(self):
        self.time_parser = TimeExpressionParser()
        
        # 이벤트 타입별 키워드 매핑
        self.event_keywords = {
            'call': [
                '전화', '통화', '연락', '콜', '전화드리기', '전화하기', 
                '전화 드리겠습니다', '전화드릴게요', '연락드리겠습니다'
            ],
            'message': [
                '문자', '메시지', '카톡', '카카오톡', 'SMS', '메일', '이메일',
                '문자 보내기', '메시지 전송', '카톡 보내기'
            ],
            'reminder': [
                '알림', '리마인드', '확인', '체크', '점검', '모니터링',
                '알려드리기', '알림 설정', '리마인더'
            ],
            'calendar': [
                '일정', '미팅', '약속', '상담', '면담', '방문', '만남',
                '스케줄', '예약', '약속 잡기', '일정 관리'
            ]
        }
        
        # 우선순위 결정 키워드
        self.priority_keywords = {
            'high': [
                '긴급', '급함', '시급', '중요', '핫한', '우선', '빨리',
                'asap', '즉시', '당장', '오늘 중', '내일까지'
            ],
            'medium': [
                '보통', '일반', '평상시', '정기', '루틴', '주기적',
                '이번 주', '다음 주', '월례'
            ],
            'low': [
                '나중에', '여유', '천천히', '언제든', '편한 시간',
                '다음 달', '추후', '향후'
            ]
        }
    
    async def generate_events_from_memo(self, 
                                      memo_record: CustomerMemo, 
                                      db_session: AsyncSession) -> List[Event]:
        """
        메모 분석 결과에서 이벤트들을 생성합니다.
        """
        try:
            logger.info(f"메모 {memo_record.id}에서 이벤트 생성 시작")
            
            events = []
            refined_memo = memo_record.refined_memo or {}
            
            # 1. 시간 표현에서 이벤트 생성
            time_expressions = refined_memo.get('time_expressions', [])
            for time_expr in time_expressions:
                event = await self._create_event_from_time_expression(
                    memo_record, time_expr, db_session
                )
                if event:
                    events.append(event)
            
            # 2. 필요 조치에서 이벤트 생성
            required_actions = refined_memo.get('required_actions', [])
            for action in required_actions:
                event = await self._create_event_from_action(
                    memo_record, action, db_session
                )
                if event:
                    events.append(event)
            
            # 3. 키워드 기반 이벤트 생성
            keywords = refined_memo.get('keywords', [])
            summary = refined_memo.get('summary', '')
            combined_text = ' '.join(keywords) + ' ' + summary
            
            event = await self._create_event_from_keywords(
                memo_record, combined_text, db_session
            )
            if event:
                events.append(event)
            
            # 데이터베이스에 저장
            for event in events:
                db_session.add(event)
            
            await db_session.commit()
            
            logger.info(f"메모 {memo_record.id}에서 {len(events)}개 이벤트 생성 완료")
            return events
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"이벤트 생성 중 오류: {str(e)}")
            raise Exception(f"이벤트 생성 중 오류가 발생했습니다: {str(e)}")
    
    async def _create_event_from_time_expression(self, 
                                               memo_record: CustomerMemo, 
                                               time_expr: Dict[str, Any],
                                               db_session: AsyncSession) -> Optional[Event]:
        """시간 표현에서 이벤트를 생성합니다."""
        try:
            expression = time_expr.get('expression', '')
            parsed_date_str = time_expr.get('parsed_date')
            
            # 날짜 파싱
            scheduled_date = None
            if parsed_date_str:
                try:
                    scheduled_date = datetime.strptime(parsed_date_str, '%Y-%m-%d').date()
                except:
                    pass
            
            if not scheduled_date:
                # 시간 파서로 다시 시도
                scheduled_date = self.time_parser.parse_time_expression(expression)
            
            if not scheduled_date:
                return None
            
            # 이벤트 타입 결정 (시간 표현의 맥락에서)
            event_type = self._determine_event_type_from_text(expression)
            if not event_type:
                event_type = 'reminder'  # 기본값
            
            # 우선순위 결정
            priority = self._determine_priority(expression)
            
            # 이벤트 생성
            event = Event(
                event_id=uuid.uuid4(),
                customer_id=memo_record.customer_id,
                memo_id=memo_record.id,
                event_type=event_type,
                scheduled_date=datetime.combine(scheduled_date, datetime.min.time()),
                priority=priority,
                status='pending',
                description=f"시간 표현 기반: {expression}"
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"시간 표현 이벤트 생성 실패: {str(e)}")
            return None
    
    async def _create_event_from_action(self, 
                                      memo_record: CustomerMemo, 
                                      action: str,
                                      db_session: AsyncSession) -> Optional[Event]:
        """필요 조치에서 이벤트를 생성합니다."""
        try:
            # 이벤트 타입 결정
            event_type = self._determine_event_type_from_text(action)
            if not event_type:
                return None
            
            # 우선순위 결정
            priority = self._determine_priority(action)
            
            # 기본 스케줄 날짜 (내일)
            scheduled_date = date.today() + timedelta(days=1)
            
            # 조치 내용에서 시간 표현 찾기
            parsed_date = self.time_parser.parse_time_expression(action)
            if parsed_date:
                scheduled_date = parsed_date
            
            # 이벤트 생성
            event = Event(
                event_id=uuid.uuid4(),
                customer_id=memo_record.customer_id,
                memo_id=memo_record.id,
                event_type=event_type,
                scheduled_date=datetime.combine(scheduled_date, datetime.min.time()),
                priority=priority,
                status='pending',
                description=f"필요 조치 기반: {action}"
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"조치 기반 이벤트 생성 실패: {str(e)}")
            return None
    
    async def _create_event_from_keywords(self, 
                                        memo_record: CustomerMemo, 
                                        text: str,
                                        db_session: AsyncSession) -> Optional[Event]:
        """키워드에서 이벤트를 생성합니다."""
        try:
            # 이벤트 타입 결정
            event_type = self._determine_event_type_from_text(text)
            if not event_type:
                return None
            
            # 우선순위 결정
            priority = self._determine_priority(text)
            
            # 기본 스케줄 날짜 (3일 후)
            scheduled_date = date.today() + timedelta(days=3)
            
            # 텍스트에서 시간 표현 찾기
            parsed_date = self.time_parser.parse_time_expression(text)
            if parsed_date:
                scheduled_date = parsed_date
            
            # 이벤트 생성
            event = Event(
                event_id=uuid.uuid4(),
                customer_id=memo_record.customer_id,
                memo_id=memo_record.id,
                event_type=event_type,
                scheduled_date=datetime.combine(scheduled_date, datetime.min.time()),
                priority=priority,
                status='pending',
                description=f"키워드 기반: {text[:100]}..."
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"키워드 기반 이벤트 생성 실패: {str(e)}")
            return None
    
    def _determine_event_type_from_text(self, text: str) -> Optional[str]:
        """텍스트에서 이벤트 타입을 결정합니다."""
        text_lower = text.lower()
        
        # 각 이벤트 타입별 키워드 매칭
        for event_type, keywords in self.event_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return event_type
        
        return None
    
    def _determine_priority(self, text: str) -> str:
        """텍스트에서 우선순위를 결정합니다."""
        text_lower = text.lower()
        
        # 우선순위별 키워드 매칭
        for priority, keywords in self.priority_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return priority
        
        return 'medium'  # 기본값
    
    async def get_upcoming_events(self, 
                                customer_id: Optional[str] = None,
                                days: int = 7,
                                db_session: AsyncSession = None) -> List[Event]:
        """
        향후 N일간의 예정된 이벤트를 조회합니다.
        """
        try:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days)
            
            # 쿼리 구성
            stmt = select(Event).where(
                Event.scheduled_date >= start_date,
                Event.scheduled_date <= end_date,
                Event.status == 'pending'
            )
            
            if customer_id:
                stmt = stmt.where(Event.customer_id == uuid.UUID(customer_id))
            
            # 날짜순으로 정렬
            stmt = stmt.order_by(Event.scheduled_date.asc(), Event.priority.desc())
            
            result = await db_session.execute(stmt)
            events = result.scalars().all()
            
            logger.info(f"향후 {days}일간 이벤트 {len(events)}개 조회")
            return events
            
        except Exception as e:
            logger.error(f"예정 이벤트 조회 중 오류: {str(e)}")
            return []
    
    async def update_event_status(self, 
                                event_id: str, 
                                status: str,
                                db_session: AsyncSession) -> Event:
        """
        이벤트 상태를 업데이트합니다.
        """
        try:
            stmt = select(Event).where(Event.event_id == uuid.UUID(event_id))
            result = await db_session.execute(stmt)
            event = result.scalar_one_or_none()
            
            if not event:
                raise Exception(f"이벤트 ID {event_id}를 찾을 수 없습니다.")
            
            event.status = status
            await db_session.commit()
            await db_session.refresh(event)
            
            logger.info(f"이벤트 {event_id} 상태를 {status}로 업데이트")
            return event
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"이벤트 상태 업데이트 중 오류가 발생했습니다: {str(e)}")


class EventService:
    """이벤트 관련 통합 서비스 클래스"""
    
    def __init__(self):
        self.event_generator = EventGenerator()
    
    async def process_memo_for_events(self, 
                                    memo_id: str, 
                                    db_session: AsyncSession) -> Dict[str, Any]:
        """
        메모를 처리하여 이벤트를 생성합니다.
        """
        try:
            # 메모 조회
            stmt = select(CustomerMemo).where(CustomerMemo.id == uuid.UUID(memo_id))
            result = await db_session.execute(stmt)
            memo_record = result.scalar_one_or_none()
            
            if not memo_record:
                raise Exception(f"메모 ID {memo_id}를 찾을 수 없습니다.")
            
            # 이벤트 생성
            events = await self.event_generator.generate_events_from_memo(
                memo_record, db_session
            )
            
            return {
                "memo_id": memo_id,
                "events_created": len(events),
                "events": [
                    {
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "scheduled_date": event.scheduled_date.isoformat(),
                        "priority": event.priority,
                        "description": event.description,
                        "status": event.status
                    }
                    for event in events
                ]
            }
            
        except Exception as e:
            raise Exception(f"메모 이벤트 처리 중 오류가 발생했습니다: {str(e)}")
    
    async def get_customer_events(self, 
                                customer_id: str, 
                                days: int = 7,
                                db_session: AsyncSession = None) -> Dict[str, Any]:
        """
        특정 고객의 향후 이벤트를 조회합니다.
        """
        try:
            events = await self.event_generator.get_upcoming_events(
                customer_id=customer_id,
                days=days,
                db_session=db_session
            )
            
            # 이벤트 타입별 분류
            events_by_type = {}
            for event in events:
                if event.event_type not in events_by_type:
                    events_by_type[event.event_type] = []
                events_by_type[event.event_type].append(event)
            
            return {
                "customer_id": customer_id,
                "total_events": len(events),
                "events_by_type": {
                    event_type: [
                        {
                            "event_id": str(event.event_id),
                            "event_type": event.event_type,
                            "scheduled_date": event.scheduled_date.isoformat(),
                            "priority": event.priority,
                            "description": event.description,
                            "status": event.status
                        }
                        for event in event_list
                    ]
                    for event_type, event_list in events_by_type.items()
                }
            }
            
        except Exception as e:
            raise Exception(f"고객 이벤트 조회 중 오류가 발생했습니다: {str(e)}")