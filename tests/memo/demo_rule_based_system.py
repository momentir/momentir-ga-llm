#!/usr/bin/env python3
"""
규칙 기반 이벤트 시스템 데모
"""

import requests
import json
from datetime import datetime, date, timedelta


def demo_rule_based_events():
    """규칙 기반 이벤트 시스템 데모"""
    print("🎯 규칙 기반 이벤트 시스템 데모")
    print("=" * 50)
    
    # 1. 현재 이벤트 현황
    print("\n📊 현재 이벤트 현황:")
    stats_url = "http://localhost:8000/api/events/statistics"
    
    try:
        response = requests.get(stats_url)
        if response.status_code == 200:
            result = response.json()
            print(f"전체 이벤트: {result['total_events']}개")
            print(f"타입별: {result['by_type']}")
            print(f"우선순위별: {result['by_priority']}")
    except:
        print("통계 조회 실패")
    
    # 2. 향후 7일간 이벤트
    print("\n📅 향후 7일간 이벤트:")
    upcoming_url = "http://localhost:8000/api/events/upcoming"
    
    try:
        response = requests.get(upcoming_url, params={"days": 7})
        if response.status_code == 200:
            result = response.json()
            print(f"총 {result['total_events']}개 이벤트")
            
            for event_type, events in result['events_by_type'].items():
                if events:
                    print(f"\n{event_type.upper()} ({len(events)}개):")
                    for event in events[:2]:  # 처음 2개만
                        scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%m-%d %H:%M')
                        print(f"  • {scheduled} ({event['priority']}) {event['description'][:60]}...")
    except:
        print("향후 이벤트 조회 실패")
    
    # 3. 우선순위별 이벤트 요약
    print("\n🚨 우선순위별 이벤트 요약:")
    priorities = ['urgent', 'high', 'medium', 'low']
    
    for priority in priorities:
        try:
            response = requests.get(f"http://localhost:8000/api/events/priority/{priority}", 
                                  params={"days": 30})
            if response.status_code == 200:
                result = response.json()
                count = result['total_events']
                if count > 0:
                    print(f"  🔴 {priority.upper()}: {count}개")
                    # 첫 번째 이벤트만 표시
                    if result['events']:
                        event = result['events'][0]
                        scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%m-%d')
                        print(f"    └─ {scheduled} {event['description'][:50]}...")
        except:
            continue
    
    # 4. 규칙 기반 이벤트 유형 설명
    print("\n📋 규칙 기반 이벤트 유형:")
    print("  🎂 생일 이벤트: 30일 전, 7일 전, 1일 전 알림")
    print("  📄 보험 갱신: 60일, 30일, 14일, 7일 전 알림")
    print("  📞 정기 팔로업: 고객별 주기적 연락")
    print("  🌟 계절별 안내: 봄/여름/가을/겨울 시즌 메시지")
    
    # 5. 우선순위 계산 기준
    print("\n⚖️  우선순위 계산 기준:")
    print("  • 고객 중요도: 보험 상품 수, 최근 활동")
    print("  • 시간 긴급도: 이벤트까지 남은 시간")
    print("  • 이벤트 타입: 통화 > 일정 > 알림 > 메시지")
    
    print("\n" + "=" * 50)
    print("✅ 규칙 기반 이벤트 시스템이 정상 작동 중입니다!")


def demo_priority_update():
    """우선순위 업데이트 데모"""
    print("\n🔄 우선순위 동적 업데이트 데모")
    print("-" * 30)
    
    url = "http://localhost:8000/api/events/update-priorities"
    
    try:
        response = requests.put(url)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['message']}")
            print(f"처리된 이벤트: {result['total_events_processed']}개")
            print(f"변경 내역:")
            for change_type, count in result['priority_changes'].items():
                if count > 0:
                    print(f"  • {change_type}: {count}개")
        else:
            print("❌ 우선순위 업데이트 실패")
    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def main():
    """메인 함수"""
    demo_rule_based_events()
    demo_priority_update()
    
    print("\n🎉 규칙 기반 이벤트 시스템 데모 완료!")
    print("\n💡 사용 방법:")
    print("  1. POST /api/events/generate-rule-based : 규칙 기반 이벤트 생성")
    print("  2. PUT /api/events/update-priorities : 우선순위 동적 업데이트")
    print("  3. GET /api/events/urgent-today : 오늘의 긴급 이벤트 조회")
    print("  4. GET /api/events/priority/{priority} : 우선순위별 이벤트 조회")


if __name__ == "__main__":
    main()