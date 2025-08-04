#!/usr/bin/env python3
"""
이벤트 API 테스트 스크립트
"""

import requests
import json
from datetime import datetime


def test_memo_refine_with_events():
    """메모 정제 및 이벤트 자동 생성 테스트"""
    print("=== 메모 정제 및 이벤트 자동 생성 테스트 ===")
    
    url = "http://localhost:8000/api/memo/refine"
    
    test_memo = {
        "memo": "내일 오후 김철수 고객과 생명보험 상담 예정입니다. 2주 후에 다시 전화 드리기로 했습니다. 긴급하게 처리해야 합니다."
    }
    
    try:
        response = requests.post(url, json=test_memo)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 메모 정제 성공!")
            print(f"메모 ID: {result['memo_id']}")
            print(f"이벤트 생성 수: {result.get('events_created', 0)}")
            
            # 정제된 데이터 출력 (안전하게 처리)
            if 'refined_data' in result:
                refined = result['refined_data']
                print(f"\n정제된 데이터:")
                print(f"  요약: {refined.get('summary', '')}")
                print(f"  시간 표현: {refined.get('time_expressions', [])}")
                print(f"  필요 조치: {refined.get('required_actions', [])}")
            else:
                print(f"\n응답 내용: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # 생성된 이벤트 출력
            for event in result.get('events', []):
                scheduled = datetime.fromisoformat(event['scheduled_date']).strftime('%Y-%m-%d %H:%M')
                print(f"  이벤트: {event['event_type']} - {scheduled} ({event['priority']}) - {event['description']}")
            
            return result['memo_id']
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ 오류: {str(e)}")
        return None


def test_events_upcoming():
    """향후 이벤트 조회 테스트"""
    print("\n=== 향후 이벤트 조회 테스트 ===")
    
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


def test_events_statistics():
    """이벤트 통계 조회 테스트"""
    print("\n=== 이벤트 통계 조회 테스트 ===")
    
    url = "http://localhost:8000/api/events/statistics"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 전체 이벤트: {result['total_events']}개")
            print(f"타입별: {result['by_type']}")
            print(f"상태별: {result['by_status']}")
            print(f"우선순위별: {result['by_priority']}")
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def test_process_memo_for_events(memo_id):
    """특정 메모에서 이벤트 생성 테스트"""
    if not memo_id:
        print("\n⚠️  메모 ID가 없어서 이벤트 처리 테스트를 건너뜁니다.")
        return
        
    print(f"\n=== 메모 {memo_id}에서 이벤트 생성 테스트 ===")
    
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
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ 오류: {str(e)}")


def main():
    """메인 테스트 함수"""
    try:
        print("이벤트 API 테스트를 시작합니다.\n")
        
        # 1. 메모 정제 및 이벤트 자동 생성
        memo_id = test_memo_refine_with_events()
        
        # 2. 향후 이벤트 조회
        test_events_upcoming()
        
        # 3. 이벤트 통계 조회
        test_events_statistics()
        
        # 4. 특정 메모에서 이벤트 생성 (중복 테스트)
        # test_process_memo_for_events(memo_id)
        
        print("\n🎯 모든 API 테스트가 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {str(e)}")


if __name__ == "__main__":
    main()