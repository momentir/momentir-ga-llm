#!/usr/bin/env python3
"""
이벤트 생성 디버깅 스크립트
"""

import asyncio
import os
from app.services.event_parser import TimeExpressionParser, EventGenerator
from app.database import db_manager
from app.services.memo_refiner import MemoRefinerService


async def debug_time_parsing():
    """시간 파싱 디버깅"""
    print("=== 시간 파싱 디버깅 ===")
    
    parser = TimeExpressionParser()
    
    test_expressions = [
        "다음 주 화요일",
        "1주일 뒤",
        "오후 2시",
        "다음 주 화요일 오후 2시"
    ]
    
    for expr in test_expressions:
        parsed = parser.parse_time_expression(expr)
        print(f"'{expr}' -> {parsed}")


async def debug_memo_refinement():
    """메모 정제에서 시간 표현 추출 디버깅"""
    print("\n=== 메모 정제 시간 표현 추출 디버깅 ===")
    
    refiner = MemoRefinerService()
    
    test_memo = "다음 주 화요일 오후 2시에 박민수 고객과 건강보험 상담 예정. 상담 후 1주일 뒤에 카톡으로 결과 안내하기. 긴급 처리 필요."
    
    try:
        refined = await refiner.refine_memo(test_memo)
        print(f"원본 메모: {test_memo}")
        print(f"정제 결과:")
        print(f"  요약: {refined.get('summary', '')}")
        print(f"  시간 표현: {refined.get('time_expressions', [])}")
        print(f"  필요 조치: {refined.get('required_actions', [])}")
        
        return refined
    except Exception as e:
        print(f"메모 정제 오류: {str(e)}")
        return None


async def debug_event_generation(refined_memo):
    """이벤트 생성 디버깅"""
    print("\n=== 이벤트 생성 디버깅 ===")
    
    if not refined_memo:
        print("정제된 메모가 없어서 이벤트 생성을 건너뜁니다.")
        return
    
    # 데이터베이스 초기화
    await db_manager.init_db()
    
    generator = EventGenerator()
    
    # 가짜 메모 레코드 생성 (테스트용)
    from app.db_models import CustomerMemo
    from datetime import datetime
    import uuid
    
    fake_memo = CustomerMemo(
        id=uuid.uuid4(),
        original_memo="테스트 메모",
        refined_memo=refined_memo,
        status="refined"
    )
    
    async for db_session in db_manager.get_session():
        try:
            # 이벤트 생성 시도
            print("이벤트 생성 시도 중...")
            
            # 1. 시간 표현에서 이벤트 생성
            time_expressions = refined_memo.get('time_expressions', [])
            print(f"시간 표현 수: {len(time_expressions)}")
            
            for time_expr in time_expressions:
                print(f"시간 표현 처리 중: {time_expr}")
                event = await generator._create_event_from_time_expression(fake_memo, time_expr, db_session)
                if event:
                    print(f"  -> 이벤트 생성됨: {event.event_type} at {event.scheduled_date}")
                else:
                    print(f"  -> 이벤트 생성 실패")
            
            # 2. 필요 조치에서 이벤트 생성
            required_actions = refined_memo.get('required_actions', [])
            print(f"\n필요 조치 수: {len(required_actions)}")
            
            for action in required_actions:
                print(f"조치 처리 중: {action}")
                event = await generator._create_event_from_action(fake_memo, action, db_session)
                if event:
                    print(f"  -> 이벤트 생성됨: {event.event_type} at {event.scheduled_date}")
                else:
                    print(f"  -> 이벤트 생성 실패")
            
            # 3. 키워드에서 이벤트 생성
            keywords = refined_memo.get('keywords', [])
            summary = refined_memo.get('summary', '')
            combined_text = ' '.join(keywords) + ' ' + summary
            print(f"\n키워드 텍스트: {combined_text}")
            
            event = await generator._create_event_from_keywords(fake_memo, combined_text, db_session)
            if event:
                print(f"  -> 이벤트 생성됨: {event.event_type} at {event.scheduled_date}")
            else:
                print(f"  -> 이벤트 생성 실패")
            
            break
            
        except Exception as e:
            print(f"이벤트 생성 디버깅 오류: {str(e)}")
            break
    
    await db_manager.close()


async def main():
    """메인 디버깅 함수"""
    try:
        print("이벤트 생성 디버깅을 시작합니다.\n")
        
        # 1. 시간 파싱 디버깅
        await debug_time_parsing()
        
        # 2. 메모 정제 디버깅
        refined_memo = await debug_memo_refinement()
        
        # 3. 이벤트 생성 디버깅
        await debug_event_generation(refined_memo)
        
        print("\n🔍 디버깅이 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 디버깅 중 오류: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())