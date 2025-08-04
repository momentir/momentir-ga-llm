#!/usr/bin/env python3
"""
이벤트 생성 전용 테스트 스크립트
"""

import requests
import json
from datetime import datetime


def test_process_memo_for_events(memo_id):
    """특정 메모에서 이벤트 생성 테스트"""
    print(f"=== 메모 {memo_id}에서 이벤트 생성 테스트 ===")
    
    url = "http://localhost:8000/api/events/process-memo"
    data = {"memo_id": memo_id}
    
    try:
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 이벤트 생성 성공: {result['events_created']}개")
            
            for event in result['events']:
                scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d %H:%M')
                print(f"  - {event['event_type']}: {scheduled} ({event['priority']}) - {event['description']}")
            
            return True
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        return False


def test_create_memo_and_events():
    """메모 생성 후 이벤트 생성 전체 플로우 테스트"""
    print("=== 전체 플로우 테스트 ===")
    
    # 1. 먼저 메모 정제
    memo_url = "http://localhost:8000/api/memo/refine"
    test_memo = {
        "memo": "다음 주 화요일 오후 2시에 박민수 고객과 건강보험 상담 예정. 상담 후 1주일 뒤에 카톡으로 결과 안내하기. 긴급 처리 필요."
    }
    
    try:
        print("1. 메모 정제 중...")
        memo_response = requests.post(memo_url, json=test_memo)
        
        if memo_response.status_code == 200:
            memo_result = memo_response.json()
            memo_id = memo_result['memo_id'] 
            print(f"✅ 메모 정제 완료: {memo_id}")
            
            # 정제된 시간 표현 확인
            time_expressions = memo_result.get('time_expressions', [])
            print(f"시간 표현: {time_expressions}")
            
            # 2. 이벤트 생성
            print(f"\n2. 메모 {memo_id}에서 이벤트 생성 중...")
            return test_process_memo_for_events(memo_id)
        else:
            print(f"❌ 메모 정제 실패: {memo_response.status_code}")
            print(memo_response.text)
            return False
            
    except Exception as e:
        print(f"❌ 전체 플로우 테스트 오류: {str(e)}")
        return False


def test_events_after_creation():
    """이벤트 생성 후 조회 테스트"""
    print("\n=== 이벤트 생성 후 조회 테스트 ===")
    
    # 향후 이벤트 조회
    url = "http://localhost:8000/api/events/upcoming"
    params = {"days": 30}
    
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 향후 30일간 총 이벤트: {result['total_events']}개")
            
            for event_type, events in result['events_by_type'].items():
                print(f"\n{event_type} 이벤트 ({len(events)}개):")
                for event in events:
                    scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d %H:%M')
                    print(f"  - {scheduled} ({event['priority']}) {event['description']}")
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def main():
    """메인 테스트 함수"""
    try:
        print("이벤트 생성 전용 테스트를 시작합니다.\n")
        
        # 1. 전체 플로우 테스트 (메모 생성 -> 이벤트 생성)
        success = test_create_memo_and_events()
        
        if success:
            # 2. 생성된 이벤트 조회
            test_events_after_creation()
        
        print("\n🎯 이벤트 생성 테스트가 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    main()