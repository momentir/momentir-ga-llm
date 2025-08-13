#!/usr/bin/env python3
"""
오늘의 긴급 이벤트 테스트
"""

import requests
from datetime import datetime


def test_urgent_events_today():
    """오늘의 긴급 이벤트 테스트"""
    print("=== 오늘의 긴급 이벤트 테스트 ===")
    
    url = "http://localhost:8000/v1/api/events/urgent-today"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 오늘({result['date']})의 긴급 이벤트 조회 성공!")
            print(f"총 긴급 이벤트: {result['total_urgent_events']}개")
            print(f"  - urgent: {result['urgent_count']}개")
            print(f"  - high: {result['high_count']}개")
            
            for event in result['events']:
                scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%H:%M')
                print(f"  - [{event['priority'].upper()}] {scheduled} {event['customer_name']}: {event['description']}")
            
            return True
        else:
            print(f"❌ 오늘의 긴급 이벤트 조회 실패: {response.status_code}")
            print(response.text)
            return False
    
    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        return False


if __name__ == "__main__":
    test_urgent_events_today()