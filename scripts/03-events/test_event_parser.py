#!/usr/bin/env python3
"""
이벤트 파싱 및 생성 기능 테스트 스크립트
"""

import asyncio
import os
from datetime import date, datetime
from app.services.event_parser import TimeExpressionParser, EventGenerator, EventService
from app.database import db_manager, get_db
from app.services.memo_refiner import MemoRefinerService


async def test_time_expression_parser():
    """시간 표현 파싱 테스트"""
    print("=== 시간 표현 파싱 테스트 ===")
    
    parser = TimeExpressionParser()
    
    test_expressions = [
        "2주 후",
        "내일",
        "모레", 
        "다음 주",
        "다음 달",
        "3일 후",
        "이번 주 금요일",
        "다음 주 수요일",
        "12월 25일",
        "2024년 3월 15일",
        "곧",
        "나중에"
    ]
    
    for expression in test_expressions:
        parsed_date = parser.parse_time_expression(expression)
        print(f"'{expression}' -> {parsed_date}")
    
    print()


async def test_memo_with_events():
    """실제 메모 예시로 이벤트 생성 테스트"""
    print("=== 메모 이벤트 생성 테스트 ===")
    
    # 데이터베이스 초기화
    await db_manager.init_db()
    
    memo_refiner = MemoRefinerService()
    
    test_memos = [
        "내일 오후 김철수 고객과 생명보험 상담 예정입니다. 2주 후에 다시 전화 드리기로 했습니다.",
        "이영희 고객이 자동차보험료 인상에 대해 문의했습니다. 다음 주 수요일에 카톡으로 상세 내용 전달하기로 했습니다.",
        "박민수 고객 생일이 다음 달입니다. 축하 메시지와 함께 건강보험 갱신 안내 예정입니다.",
        "최영수 고객이 보험금 청구 관련해서 긴급 상담을 요청했습니다. 오늘 중으로 전화드려야 합니다."
    ]
    
    async for db_session in db_manager.get_session():
        try:
            for i, memo in enumerate(test_memos, 1):
                print(f"\n--- 테스트 메모 {i} ---")
                print(f"원본: {memo}")
                
                # 메모 정제 및 이벤트 자동 생성
                result = await memo_refiner.refine_and_save_memo(
                    memo=memo,
                    db_session=db_session,
                    auto_generate_events=True
                )
                
                print(f"메모 ID: {result['memo_id']}")
                print(f"생성된 이벤트 수: {result['events_created']}")
                
                # 생성된 이벤트 정보
                for event in result.get('events', []):
                    print(f"  - {event['event_type']}: {event['scheduled_date']} ({event['priority']}) - {event['description']}")
                
                print(f"정제된 데이터:")
                refined = result['refined_data']
                print(f"  요약: {refined.get('summary', '')}")
                print(f"  시간 표현: {refined.get('time_expressions', [])}")
                print(f"  필요 조치: {refined.get('required_actions', [])}")
            
            break
            
        except Exception as e:
            print(f"테스트 중 오류: {str(e)}")
            break
    
    await db_manager.close()


async def test_event_service():
    """이벤트 서비스 기능 테스트"""
    print("\n=== 이벤트 서비스 테스트 ===")
    
    await db_manager.init_db()
    
    event_service = EventService()
    
    async for db_session in db_manager.get_session():
        try:
            # 향후 7일간 이벤트 조회
            upcoming_events = await event_service.get_customer_events(
                customer_id=None,  # 전체 고객
                days=7,
                db_session=db_session
            )
            
            print(f"향후 7일간 총 이벤트: {upcoming_events['total_events']}개")
            
            for event_type, events in upcoming_events['events_by_type'].items():
                print(f"\n{event_type} 이벤트 ({len(events)}개):")
                for event in events:
                    scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d %H:%M')
                    print(f"  - {scheduled} ({event['priority']}) {event['description']}")
            
            break
            
        except Exception as e:
            print(f"이벤트 서비스 테스트 중 오류: {str(e)}")
            break
    
    await db_manager.close()


async def main():
    """메인 테스트 함수"""
    try:
        # 환경 변수 확인
        if not os.getenv("DATABASE_URL"):
            print("DATABASE_URL 환경변수가 설정되지 않았습니다.")
            return
        
        print("이벤트 파싱 및 생성 시스템 테스트를 시작합니다.\n")
        
        # 1. 시간 표현 파싱 테스트
        await test_time_expression_parser()
        
        # 2. 실제 메모로 이벤트 생성 테스트
        await test_memo_with_events()
        
        # 3. 이벤트 서비스 테스트
        await test_event_service()
        
        print("\n✅ 모든 테스트가 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())