import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.db_models import Event, Customer, CustomerMemo
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """이벤트 우선순위 열거형"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RuleType(Enum):
    """규칙 유형 열거형"""
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    POLICY_RENEWAL = "policy_renewal"
    PREMIUM_DUE = "premium_due"
    FOLLOW_UP = "follow_up"
    SEASONAL = "seasonal"


class RuleBasedEventGenerator:
    """규칙 기반 이벤트 생성기"""
    
    def __init__(self):
        # 이벤트 규칙 정의
        self.event_rules = {
            RuleType.BIRTHDAY: {
                "advance_days": [30, 7, 1],  # 30일 전, 7일 전, 1일 전
                "event_type": "call",
                "priority": EventPriority.MEDIUM,
                "description_template": "{customer_name} 고객 생일 ({days}일 {timing})"
            },
            RuleType.ANNIVERSARY: {
                "advance_days": [30, 14, 3],  # 30일 전, 14일 전, 3일 전
                "event_type": "message",
                "priority": EventPriority.MEDIUM,
                "description_template": "{customer_name} 고객 {anniversary_type} 기념일 ({days}일 {timing})"
            },
            RuleType.POLICY_RENEWAL: {
                "advance_days": [60, 30, 14, 7],  # 60일 전, 30일 전, 14일 전, 7일 전
                "event_type": "call",
                "priority": EventPriority.HIGH,
                "description_template": "{customer_name} 고객 {policy_name} 갱신 예정 ({days}일 {timing})"
            },
            RuleType.PREMIUM_DUE: {
                "advance_days": [14, 7, 3, 1],  # 14일 전, 7일 전, 3일 전, 1일 전
                "event_type": "reminder",
                "priority": EventPriority.HIGH,
                "description_template": "{customer_name} 고객 보험료 납부 예정 ({days}일 {timing})"
            },
            RuleType.FOLLOW_UP: {
                "advance_days": [0],  # 당일
                "event_type": "call",
                "priority": EventPriority.MEDIUM,
                "description_template": "{customer_name} 고객 정기 연락 ({interval} 주기)"
            },
            RuleType.SEASONAL: {
                "advance_days": [14, 7],  # 14일 전, 7일 전
                "event_type": "message",
                "priority": EventPriority.LOW,
                "description_template": "{season} 시즌 고객 안내 메시지"
            }
        }
        
        # 계절별 이벤트 일정
        self.seasonal_events = {
            "spring": {"month": 3, "day": 1, "message": "봄철 건강관리"},
            "summer": {"month": 6, "day": 1, "message": "여름휴가철 여행보험"},
            "autumn": {"month": 9, "day": 1, "message": "가을철 건강검진"},
            "winter": {"month": 12, "day": 1, "message": "연말정산 및 세무상담"}
        }
        
        # 우선순위 점수 (높을수록 중요)
        self.priority_scores = {
            EventPriority.LOW: 1,
            EventPriority.MEDIUM: 2,
            EventPriority.HIGH: 3,
            EventPriority.URGENT: 4
        }
    
    async def generate_birthday_events(self, 
                                     customer: Customer, 
                                     db_session: AsyncSession,
                                     target_date_range: int = 365) -> List[Event]:
        """생일 기반 이벤트 생성"""
        events = []
        
        if not customer.date_of_birth:
            return events
        
        try:
            # 올해와 내년 생일 확인
            today = date.today()
            birth_date = customer.date_of_birth.date() if hasattr(customer.date_of_birth, 'date') else customer.date_of_birth
            
            for year_offset in [0, 1]:  # 올해, 내년
                birthday_this_year = birth_date.replace(year=today.year + year_offset)
                
                # 생일이 이미 지났으면 내년으로
                if birthday_this_year < today and year_offset == 0:
                    continue
                
                rule = self.event_rules[RuleType.BIRTHDAY]
                
                for days_before in rule["advance_days"]:
                    event_date = birthday_this_year - timedelta(days=days_before)
                    
                    # 타겟 날짜 범위 내인지 확인
                    if event_date <= today or (event_date - today).days > target_date_range:
                        continue
                    
                    # 중복 이벤트 확인
                    if await self._event_exists(customer.customer_id, RuleType.BIRTHDAY, event_date, db_session):
                        continue
                    
                    timing = "전" if days_before > 0 else "당일"
                    description = rule["description_template"].format(
                        customer_name=customer.name or "고객",
                        days=days_before if days_before > 0 else "",
                        timing=timing
                    ).strip()
                    
                    event = Event(
                        event_id=uuid.uuid4(),
                        customer_id=customer.customer_id,
                        memo_id=None,
                        event_type=rule["event_type"],
                        scheduled_date=datetime.combine(event_date, datetime.min.time()),
                        priority=rule["priority"].value,
                        status="pending",
                        description=description
                    )
                    
                    events.append(event)
                    logger.info(f"생일 이벤트 생성: {customer.name} - {event_date}")
        
        except Exception as e:
            logger.error(f"생일 이벤트 생성 중 오류: {str(e)}")
        
        return events
    
    async def generate_policy_renewal_events(self, 
                                           customer: Customer, 
                                           db_session: AsyncSession,
                                           target_date_range: int = 365) -> List[Event]:
        """보험 갱신 기반 이벤트 생성"""
        events = []
        
        if not customer.insurance_products:
            return events
        
        try:
            today = date.today()
            rule = self.event_rules[RuleType.POLICY_RENEWAL]
            
            for product in customer.insurance_products:
                if not isinstance(product, dict) or 'renewal_date' not in product:
                    continue
                
                try:
                    # 갱신일 파싱
                    renewal_date_str = product['renewal_date']
                    if isinstance(renewal_date_str, str):
                        renewal_date = datetime.strptime(renewal_date_str, '%Y-%m-%d').date()
                    else:
                        continue
                    
                    # 갱신일이 과거인 경우 내년으로 조정
                    if renewal_date < today:
                        renewal_date = renewal_date.replace(year=today.year + 1)
                    
                    policy_name = product.get('name', '보험')
                    
                    for days_before in rule["advance_days"]:
                        event_date = renewal_date - timedelta(days=days_before)
                        
                        # 타겟 날짜 범위 내인지 확인
                        if event_date <= today or (event_date - today).days > target_date_range:
                            continue
                        
                        # 중복 이벤트 확인
                        if await self._event_exists(customer.customer_id, RuleType.POLICY_RENEWAL, event_date, db_session):
                            continue
                        
                        timing = "전" if days_before > 0 else "당일"
                        description = rule["description_template"].format(
                            customer_name=customer.name or "고객",
                            policy_name=policy_name,
                            days=days_before if days_before > 0 else "",
                            timing=timing
                        ).strip()
                        
                        event = Event(
                            event_id=uuid.uuid4(),
                            customer_id=customer.customer_id,
                            memo_id=None,
                            event_type=rule["event_type"],
                            scheduled_date=datetime.combine(event_date, datetime.min.time()),
                            priority=rule["priority"].value,
                            status="pending",
                            description=description
                        )
                        
                        events.append(event)
                        logger.info(f"갱신 이벤트 생성: {customer.name} - {policy_name} - {event_date}")
                
                except Exception as e:
                    logger.warning(f"보험상품 갱신일 파싱 실패: {product} - {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"보험 갱신 이벤트 생성 중 오류: {str(e)}")
        
        return events
    
    async def generate_follow_up_events(self, 
                                      customer: Customer, 
                                      db_session: AsyncSession,
                                      target_date_range: int = 90) -> List[Event]:
        """정기 팔로업 이벤트 생성"""
        events = []
        
        try:
            today = date.today()
            
            # 마지막 연락 날짜 확인
            last_contact_stmt = select(CustomerMemo).where(
                CustomerMemo.customer_id == customer.customer_id
            ).order_by(CustomerMemo.created_at.desc()).limit(1)
            
            result = await db_session.execute(last_contact_stmt)
            last_memo = result.scalar_one_or_none()
            
            if last_memo:
                last_contact_date = last_memo.created_at.date()
                days_since_contact = (today - last_contact_date).days
            else:
                # 고객 생성일로부터 계산
                last_contact_date = customer.created_at.date()
                days_since_contact = (today - last_contact_date).days
            
            # 팔로업 주기 결정 (고객 중요도에 따라)
            follow_up_interval = self._determine_follow_up_interval(customer)
            
            # 다음 팔로업 날짜 계산
            if days_since_contact >= follow_up_interval:
                next_follow_up = today + timedelta(days=1)  # 내일
            else:
                next_follow_up = last_contact_date + timedelta(days=follow_up_interval)
            
            # 타겟 날짜 범위 내인지 확인
            if (next_follow_up - today).days <= target_date_range:
                # 중복 이벤트 확인
                if not await self._event_exists(customer.customer_id, RuleType.FOLLOW_UP, next_follow_up, db_session):
                    rule = self.event_rules[RuleType.FOLLOW_UP]
                    
                    description = rule["description_template"].format(
                        customer_name=customer.name or "고객",
                        interval=f"{follow_up_interval}일"
                    )
                    
                    event = Event(
                        event_id=uuid.uuid4(),
                        customer_id=customer.customer_id,
                        memo_id=None,
                        event_type=rule["event_type"],
                        scheduled_date=datetime.combine(next_follow_up, datetime.min.time()),
                        priority=rule["priority"].value,
                        status="pending",
                        description=description
                    )
                    
                    events.append(event)
                    logger.info(f"팔로업 이벤트 생성: {customer.name} - {next_follow_up}")
        
        except Exception as e:
            logger.error(f"팔로업 이벤트 생성 중 오류: {str(e)}")
        
        return events
    
    async def generate_seasonal_events(self, 
                                     db_session: AsyncSession,
                                     target_date_range: int = 365) -> List[Event]:
        """계절별 이벤트 생성"""
        events = []
        
        try:
            today = date.today()
            
            # 모든 고객 조회
            customers_stmt = select(Customer)
            result = await db_session.execute(customers_stmt)
            customers = result.scalars().all()
            
            for season, season_info in self.seasonal_events.items():
                # 올해와 내년 계절 이벤트 확인
                for year_offset in [0, 1]:
                    season_date = date(today.year + year_offset, season_info["month"], season_info["day"])
                    
                    if season_date < today and year_offset == 0:
                        continue
                    
                    rule = self.event_rules[RuleType.SEASONAL]
                    
                    for days_before in rule["advance_days"]:
                        event_date = season_date - timedelta(days=days_before)
                        
                        # 타겟 날짜 범위 내인지 확인
                        if event_date <= today or (event_date - today).days > target_date_range:
                            continue
                        
                        # 계절 이벤트는 고객별로 생성
                        for customer in customers[:10]:  # 처음 10명만 (테스트용)
                            # 중복 이벤트 확인
                            if await self._event_exists(customer.customer_id, RuleType.SEASONAL, event_date, db_session):
                                continue
                            
                            timing = "전" if days_before > 0 else "당일"
                            description = rule["description_template"].format(
                                season=season_info["message"]
                            )
                            
                            event = Event(
                                event_id=uuid.uuid4(),
                                customer_id=customer.customer_id,
                                memo_id=None,
                                event_type=rule["event_type"],
                                scheduled_date=datetime.combine(event_date, datetime.min.time()),
                                priority=rule["priority"].value,
                                status="pending",
                                description=f"{customer.name or '고객'} - {description}"
                            )
                            
                            events.append(event)
                        
                        logger.info(f"계절 이벤트 생성: {season} - {event_date}")
        
        except Exception as e:
            logger.error(f"계절 이벤트 생성 중 오류: {str(e)}")
        
        return events
    
    def _determine_follow_up_interval(self, customer: Customer) -> int:
        """고객별 팔로업 주기 결정"""
        # 보험 상품 수에 따른 주기 조정
        if customer.insurance_products:
            product_count = len(customer.insurance_products)
            if product_count >= 3:
                return 30  # 30일 주기
            elif product_count >= 2:
                return 45  # 45일 주기
            else:
                return 60  # 60일 주기
        else:
            return 90  # 90일 주기 (보험 상품 없음)
    
    async def _event_exists(self, 
                          customer_id: uuid.UUID, 
                          rule_type: RuleType, 
                          event_date: date, 
                          db_session: AsyncSession) -> bool:
        """중복 이벤트 확인"""
        try:
            # 같은 날짜, 같은 고객, 비슷한 설명을 가진 이벤트 확인
            stmt = select(Event).where(
                and_(
                    Event.customer_id == customer_id,
                    Event.scheduled_date >= datetime.combine(event_date, datetime.min.time()),
                    Event.scheduled_date < datetime.combine(event_date + timedelta(days=1), datetime.min.time()),
                    Event.description.contains(rule_type.value.replace('_', ' '))
                )
            )
            
            result = await db_session.execute(stmt)
            existing_event = result.scalar_one_or_none()
            
            return existing_event is not None
        
        except Exception as e:
            logger.warning(f"이벤트 중복 확인 중 오류: {str(e)}")
            return False
    
    async def generate_all_rule_based_events(self, 
                                           db_session: AsyncSession,
                                           target_date_range: int = 365) -> Dict[str, Any]:
        """모든 규칙 기반 이벤트 생성"""
        try:
            logger.info("규칙 기반 이벤트 생성 시작")
            
            all_events = []
            event_counts = {
                "birthday": 0,
                "policy_renewal": 0,
                "follow_up": 0,
                "seasonal": 0
            }
            
            # 모든 고객 조회
            customers_stmt = select(Customer)
            result = await db_session.execute(customers_stmt)
            customers = result.scalars().all()
            
            logger.info(f"총 {len(customers)}명의 고객에 대해 규칙 기반 이벤트 생성")
            
            # 각 고객별로 이벤트 생성
            for customer in customers:
                # 1. 생일 이벤트
                birthday_events = await self.generate_birthday_events(customer, db_session, target_date_range)
                all_events.extend(birthday_events)
                event_counts["birthday"] += len(birthday_events)
                
                # 2. 보험 갱신 이벤트
                renewal_events = await self.generate_policy_renewal_events(customer, db_session, target_date_range)
                all_events.extend(renewal_events)
                event_counts["policy_renewal"] += len(renewal_events)
                
                # 3. 팔로업 이벤트
                follow_up_events = await self.generate_follow_up_events(customer, db_session, target_date_range // 4)  # 90일
                all_events.extend(follow_up_events)
                event_counts["follow_up"] += len(follow_up_events)
            
            # 4. 계절별 이벤트 (전체 고객 대상)
            seasonal_events = await self.generate_seasonal_events(db_session, target_date_range)
            all_events.extend(seasonal_events)
            event_counts["seasonal"] += len(seasonal_events)
            
            # 우선순위별 정렬
            all_events.sort(key=lambda e: (self.priority_scores.get(EventPriority(e.priority), 0), e.scheduled_date), reverse=True)
            
            # 데이터베이스에 저장
            for event in all_events:
                db_session.add(event)
            
            await db_session.commit()
            
            logger.info(f"규칙 기반 이벤트 생성 완료: 총 {len(all_events)}개")
            
            return {
                "total_events_created": len(all_events),
                "event_counts": event_counts,
                "events_by_priority": self._group_events_by_priority(all_events),
                "next_7_days_events": len([e for e in all_events if (e.scheduled_date.date() - date.today()).days <= 7])
            }
        
        except Exception as e:
            await db_session.rollback()
            logger.error(f"규칙 기반 이벤트 생성 중 오류: {str(e)}")
            raise Exception(f"규칙 기반 이벤트 생성 중 오류가 발생했습니다: {str(e)}")
    
    def _group_events_by_priority(self, events: List[Event]) -> Dict[str, int]:
        """이벤트를 우선순위별로 그룹화"""
        priority_counts = {"urgent": 0, "high": 0, "medium": 0, "low": 0}
        
        for event in events:
            priority_counts[event.priority] += 1
        
        return priority_counts


class PriorityManager:
    """이벤트 우선순위 관리 시스템"""
    
    def __init__(self):
        self.priority_weights = {
            "urgent": 4,
            "high": 3,
            "medium": 2,
            "low": 1
        }
        
        # 이벤트 타입별 기본 우선순위
        self.event_type_priorities = {
            "call": "medium",
            "message": "low",
            "reminder": "medium",
            "calendar": "high"
        }
    
    async def calculate_dynamic_priority(self, 
                                       event: Event, 
                                       customer: Customer,
                                       db_session: AsyncSession) -> str:
        """동적 우선순위 계산"""
        try:
            base_priority = event.priority
            priority_score = self.priority_weights.get(base_priority, 2)
            
            # 1. 고객 중요도 가중치
            customer_weight = await self._calculate_customer_importance(customer, db_session)
            priority_score += customer_weight
            
            # 2. 시간 긴급도 가중치
            time_weight = self._calculate_time_urgency(event.scheduled_date)
            priority_score += time_weight
            
            # 3. 이벤트 타입 가중치
            type_weight = self._calculate_event_type_weight(event.event_type)
            priority_score += type_weight
            
            # 4. 최종 우선순위 결정
            if priority_score >= 7:
                return "urgent"
            elif priority_score >= 5:
                return "high"
            elif priority_score >= 3:
                return "medium"
            else:
                return "low"
        
        except Exception as e:
            logger.warning(f"동적 우선순위 계산 실패: {str(e)}")
            return event.priority
    
    async def _calculate_customer_importance(self, customer: Customer, db_session: AsyncSession) -> float:
        """고객 중요도 계산"""
        importance_score = 0.0
        
        # 보험 상품 수
        if customer.insurance_products:
            importance_score += len(customer.insurance_products) * 0.3
        
        # 최근 활동 여부
        recent_activity_stmt = select(CustomerMemo).where(
            and_(
                CustomerMemo.customer_id == customer.customer_id,
                CustomerMemo.created_at >= datetime.now() - timedelta(days=30)
            )
        )
        result = await db_session.execute(recent_activity_stmt)
        recent_memos = result.scalars().all()
        
        if len(recent_memos) > 0:
            importance_score += len(recent_memos) * 0.2
        
        return min(importance_score, 2.0)  # 최대 2점
    
    def _calculate_time_urgency(self, scheduled_date: datetime) -> float:
        """시간 긴급도 계산"""
        today = datetime.now()
        days_until = (scheduled_date - today).days
        
        if days_until <= 0:
            return 2.0  # 당일/지난 이벤트
        elif days_until <= 1:
            return 1.5  # 내일
        elif days_until <= 3:
            return 1.0  # 3일 이내
        elif days_until <= 7:
            return 0.5  # 일주일 이내
        else:
            return 0.0  # 일주일 이후
    
    def _calculate_event_type_weight(self, event_type: str) -> float:
        """이벤트 타입 가중치 계산"""
        type_weights = {
            "call": 0.5,
            "calendar": 1.0,
            "reminder": 0.3,
            "message": 0.2
        }
        
        return type_weights.get(event_type, 0.0)
    
    async def update_event_priorities(self, db_session: AsyncSession) -> Dict[str, Any]:
        """모든 이벤트의 우선순위 업데이트"""
        try:
            # 대기 중인 모든 이벤트 조회
            events_stmt = select(Event).where(Event.status == "pending")
            events_result = await db_session.execute(events_stmt)
            events = events_result.scalars().all()
            
            updated_count = 0
            priority_changes = {"increased": 0, "decreased": 0, "unchanged": 0}
            
            for event in events:
                if not event.customer_id:
                    continue
                
                # 고객 정보 조회
                customer_stmt = select(Customer).where(Customer.customer_id == event.customer_id)
                customer_result = await db_session.execute(customer_stmt)
                customer = customer_result.scalar_one_or_none()
                
                if not customer:
                    continue
                
                old_priority = event.priority
                new_priority = await self.calculate_dynamic_priority(event, customer, db_session)
                
                if old_priority != new_priority:
                    event.priority = new_priority
                    updated_count += 1
                    
                    old_score = self.priority_weights.get(old_priority, 2)
                    new_score = self.priority_weights.get(new_priority, 2)
                    
                    if new_score > old_score:
                        priority_changes["increased"] += 1
                    else:
                        priority_changes["decreased"] += 1
                else:
                    priority_changes["unchanged"] += 1
            
            await db_session.commit()
            
            return {
                "total_events_processed": len(events),
                "events_updated": updated_count,
                "priority_changes": priority_changes
            }
        
        except Exception as e:
            await db_session.rollback()
            logger.error(f"이벤트 우선순위 업데이트 중 오류: {str(e)}")
            raise Exception(f"이벤트 우선순위 업데이트 중 오류가 발생했습니다: {str(e)}")