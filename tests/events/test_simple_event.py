#!/usr/bin/env python3
"""
간단한 이벤트 파싱 테스트 스크립트
"""

import asyncio
import os
from datetime import date, datetime
from app.services.event_parser import TimeExpressionParser


async def test_time_parser_only():
    """시간 파싱만 테스트"""
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
        "2024년 3월 15일"
    ]
    
    for expression in test_expressions:
        parsed_date = parser.parse_time_expression(expression)
        print(f"'{expression}' -> {parsed_date}")
    
    print("\n✅ 시간 파싱 테스트 완료!")


async def test_event_keywords():
    """이벤트 키워드 매칭 테스트"""
    print("=== 이벤트 키워드 매칭 테스트 ===")
    
    from app.services.event_parser import EventGenerator
    
    generator = EventGenerator()
    
    test_texts = [
        "고객에게 전화 드리기",
        "카톡으로 안내 메시지 보내기", 
        "미팅 일정 잡기",
        "알림 설정하기",
        "긴급 상담 요청",
        "다음 주 수요일 상담 예정"
    ]
    
    for text in test_texts:
        event_type = generator._determine_event_type_from_text(text)
        priority = generator._determine_priority(text)
        print(f"'{text}' -> 타입: {event_type}, 우선순위: {priority}")
    
    print("\n✅ 이벤트 키워드 매칭 테스트 완료!")


async def main():
    """메인 테스트 함수"""
    try:
        print("간단한 이벤트 파싱 테스트를 시작합니다.\n")
        
        # 1. 시간 표현 파싱 테스트
        await test_time_parser_only()
        
        # 2. 이벤트 키워드 매칭 테스트
        await test_event_keywords()
        
        print("\n🎯 모든 테스트가 성공적으로 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())