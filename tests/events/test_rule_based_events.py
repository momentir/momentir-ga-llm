#!/usr/bin/env python3
"""
규칙 기반 이벤트 시스템 테스트 스크립트
"""

import requests
import json
from datetime import datetime, date, timedelta


def create_test_customers():
    """테스트 고객 데이터 생성"""
    print("=== 테스트 고객 데이터 생성 ===")
    
    url = "http://localhost:8000/v1/api/customer/create"
    
    # 테스트 고객들
    test_customers = [
        {
            "name": "김철수",
            "contact": "010-1234-5678",
            "gender": "남성",
            "date_of_birth": "1985-12-25",  # 곧 다가올 생일
            "interests": ["건강관리", "투자"],
            "life_events": ["결혼", "출산"],
            "insurance_products": [
                {
                    "name": "종합보험",
                    "type": "생명보험",
                    "renewal_date": "2025-09-15",  # 갱신 예정
                    "premium": 50000
                },
                {
                    "name": "자동차보험",
                    "type": "손해보험", 
                    "renewal_date": "2025-08-30",
                    "premium": 80000
                }
            ]
        },
        {
            "name": "이영희",
            "contact": "010-9876-5432",
            "gender": "여성",
            "date_of_birth": "1990-03-15",
            "interests": ["여행", "건강"],
            "life_events": ["창업"],
            "insurance_products": [
                {
                    "name": "건강보험",
                    "type": "실손보험",
                    "renewal_date": "2025-10-01",
                    "premium": 30000
                }
            ]
        },
        {
            "name": "박민수",
            "contact": "010-5555-7777",
            "gender": "남성",
            "date_of_birth": "1988-08-10",  # 곧 다가올 생일
            "interests": ["기술", "교육"],
            "life_events": ["이직"],
            "insurance_products": []  # 보험 상품 없음
        }
    ]
    
    created_customers = []
    
    for customer_data in test_customers:
        try:
            response = requests.post(url, json=customer_data)
            
            if response.status_code == 200:
                result = response.json()
                created_customers.append(result)
                print(f"✅ 고객 생성 성공: {customer_data['name']} (ID: {result['customer_id']})")
            else:
                print(f"❌ 고객 생성 실패: {customer_data['name']} - {response.status_code}")
                print(response.text)
        
        except Exception as e:
            print(f"❌ 고객 생성 오류: {customer_data['name']} - {str(e)}")
    
    return created_customers


def test_generate_rule_based_events():
    """규칙 기반 이벤트 생성 테스트"""
    print("\n=== 규칙 기반 이벤트 생성 테스트 ===")
    
    url = "http://localhost:8000/v1/api/events/generate-rule-based"
    params = {"target_days": 365}
    
    try:
        response = requests.post(url, params=params)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 규칙 기반 이벤트 생성 성공!")
            print(f"총 생성된 이벤트: {result['total_events_created']}개")
            print(f"이벤트 유형별:")
            for event_type, count in result['event_counts'].items():
                print(f"  - {event_type}: {count}개")
            print(f"우선순위별:")
            for priority, count in result['events_by_priority'].items():
                print(f"  - {priority}: {count}개")
            print(f"향후 7일간 이벤트: {result['next_7_days_events']}개")
            
            return True
        else:
            print(f"❌ 규칙 기반 이벤트 생성 실패: {response.status_code}")
            print(response.text)
            return False
    
    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        return False


def test_priority_system():
    """우선순위 시스템 테스트"""
    print("\n=== 우선순위 시스템 테스트 ===")
    
    # 1. 우선순위 업데이트
    update_url = "http://localhost:8000/v1/api/events/update-priorities"
    
    try:
        response = requests.put(update_url)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 우선순위 업데이트 성공!")
            print(f"처리된 이벤트: {result['total_events_processed']}개")
            print(f"업데이트된 이벤트: {result['events_updated']}개")
            print(f"우선순위 변경:")
            for change_type, count in result['priority_changes'].items():
                print(f"  - {change_type}: {count}개")
        else:
            print(f"❌ 우선순위 업데이트 실패: {response.status_code}")
            print(response.text)
            return False
    
    except Exception as e:
        print(f"❌ 우선순위 업데이트 오류: {str(e)}")
        return False
    
    # 2. 우선순위별 이벤트 조회
    priorities = ['urgent', 'high', 'medium', 'low']
    
    for priority in priorities:
        priority_url = f"http://localhost:8000/v1/api/events/priority/{priority}"
        
        try:
            response = requests.get(priority_url, params={"days": 30})
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n{priority.upper()} 우선순위 이벤트: {result['total_events']}개")
                
                # 처음 3개만 출력
                for event in result['events'][:3]:
                    scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d %H:%M')
                    print(f"  - {event['event_type']}: {scheduled} - {event['description']}")
            else:
                print(f"❌ {priority} 우선순위 조회 실패: {response.status_code}")
        
        except Exception as e:
            print(f"❌ {priority} 우선순위 조회 오류: {str(e)}")
    
    return True


def test_urgent_events_today():
    """오늘의 긴급 이벤트 테스트"""
    print("\n=== 오늘의 긴급 이벤트 테스트 ===")
    
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


def test_all_events_overview():
    """전체 이벤트 현황 조회"""
    print("\n=== 전체 이벤트 현황 ===")
    
    # 1. 향후 이벤트 조회
    url = "http://localhost:8000/v1/api/events/upcoming"
    params = {"days": 30}
    
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 향후 30일간 총 이벤트: {result['total_events']}개")
            
            for event_type, events in result['events_by_type'].items():
                print(f"\n{event_type.upper()} 이벤트 ({len(events)}개):")
                # 처음 3개만 출력
                for event in events[:3]:
                    scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d')
                    print(f"  - {scheduled} ({event['priority']}) {event['description']}")
                if len(events) > 3:
                    print(f"  ... 및 {len(events) - 3}개 더")
        else:
            print(f"❌ 이벤트 조회 실패: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        return False
    
    # 2. 이벤트 통계
    stats_url = "http://localhost:8000/v1/api/events/statistics"
    
    try:
        response = requests.get(stats_url)
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n📊 이벤트 통계:")
            print(f"전체 이벤트: {result['total_events']}개")
            print(f"타입별: {result['by_type']}")
            print(f"상태별: {result['by_status']}")
            print(f"우선순위별: {result['by_priority']}")
        else:
            print(f"❌ 통계 조회 실패: {response.status_code}")
    
    except Exception as e:
        print(f"❌ 통계 조회 오류: {str(e)}")
    
    return True


def main():
    """메인 테스트 함수"""
    try:
        print("규칙 기반 이벤트 시스템 테스트를 시작합니다.\n")
        
        # 1. 테스트 고객 생성
        customers = create_test_customers()
        
        if not customers:
            print("⚠️  테스트 고객 생성에 실패했습니다. 기존 고객으로 테스트를 진행합니다.")
        
        # 2. 규칙 기반 이벤트 생성
        if test_generate_rule_based_events():
            # 3. 우선순위 시스템 테스트
            test_priority_system()
            
            # 4. 오늘의 긴급 이벤트 테스트
            test_urgent_events_today()
            
            # 5. 전체 이벤트 현황
            test_all_events_overview()
        
        print("\n🎯 규칙 기반 이벤트 시스템 테스트가 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    main()