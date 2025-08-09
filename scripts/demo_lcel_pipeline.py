#!/usr/bin/env python3
"""
LCEL SQL 생성 파이프라인 데모 스크립트

이 스크립트는 LCEL 기반 SQL 생성 파이프라인의 
주요 기능을 시연합니다.
"""

import asyncio
import sys
import os
import time
from typing import List, Dict, Any

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.lcel_sql_pipeline import (
    lcel_sql_pipeline,
    EnhancedSQLGenerationRequest,
    ExecutionStrategy,
    RetryConfig
)

# 테스트 쿼리들
DEMO_QUERIES = [
    {
        "query": "홍길동 고객의 정보를 보여주세요",
        "strategy": ExecutionStrategy.RULE_ONLY,
        "description": "🔍 단순 조회 (규칙 기반)"
    },
    {
        "query": "30대 고객들을 찾아주세요", 
        "strategy": ExecutionStrategy.RULE_ONLY,
        "description": "🔎 필터링 쿼리 (규칙 기반)"
    },
    {
        "query": "고객 수를 계산해주세요",
        "strategy": ExecutionStrategy.RULE_ONLY,
        "description": "📊 집계 쿼리 (규칙 기반)"
    },
    {
        "query": "고객과 관련된 메모를 함께 보여주세요",
        "strategy": ExecutionStrategy.RULE_ONLY,
        "description": "🔗 조인 쿼리 (규칙 기반)"
    },
    {
        "query": "지난 3개월간 가입한 30대 여성 고객들의 평균 보험료를 계산하고, 서울 거주자와 지방 거주자를 분리해서 분석해주세요",
        "strategy": ExecutionStrategy.LLM_FIRST,
        "description": "🧠 복잡한 분석 쿼리 (LLM 우선)"
    }
]

COLORS = {
    'HEADER': '\033[95m',
    'BLUE': '\033[94m',
    'CYAN': '\033[96m',
    'GREEN': '\033[92m',
    'WARNING': '\033[93m',
    'FAIL': '\033[91m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m',
}

def print_colored(text: str, color: str = 'ENDC'):
    """컬러 텍스트 출력"""
    print(f"{COLORS.get(color, COLORS['ENDC'])}{text}{COLORS['ENDC']}")

def print_separator(title: str = ""):
    """구분선 출력"""
    separator = "=" * 80
    if title:
        print_colored(f"\n{separator}", 'CYAN')
        print_colored(f" {title.center(78)} ", 'CYAN')
        print_colored(f"{separator}", 'CYAN')
    else:
        print_colored(f"{separator}", 'CYAN')

async def demo_basic_sql_generation():
    """기본 SQL 생성 데모"""
    print_separator("🚀 LCEL SQL 생성 파이프라인 기본 데모")
    
    for i, demo_query in enumerate(DEMO_QUERIES, 1):
        print_colored(f"\n[{i}/{len(DEMO_QUERIES)}] {demo_query['description']}", 'HEADER')
        print_colored(f"쿼리: {demo_query['query']}", 'BLUE')
        print_colored(f"전략: {demo_query['strategy']}", 'CYAN')
        
        try:
            # 요청 생성
            request = EnhancedSQLGenerationRequest(
                query=demo_query['query'],
                strategy=demo_query['strategy'],
                timeout_seconds=15.0
            )
            
            # 시간 측정 시작
            start_time = time.time()
            
            # SQL 생성 실행
            result = await lcel_sql_pipeline.generate_sql(request)
            
            # 결과 출력
            execution_time = time.time() - start_time
            
            if result.success:
                print_colored("✅ 성공", 'GREEN')
                print_colored(f"생성된 SQL:", 'WARNING')
                print(f"  {result.sql_result.sql}")
                
                if result.sql_result.parameters:
                    print_colored(f"파라미터: {result.sql_result.parameters}", 'CYAN')
                
                print_colored(f"설명: {result.sql_result.explanation}", 'BLUE')
                print_colored(f"신뢰도: {result.sql_result.confidence:.2f}", 'GREEN')
                print_colored(f"복잡도: {result.sql_result.complexity_score:.2f}", 'WARNING')
                print_colored(f"생성 방법: {result.sql_result.generation_method}", 'CYAN')
                print_colored(f"실행 시간: {execution_time:.2f}초", 'BLUE')
                
            else:
                print_colored("❌ 실패", 'FAIL')
                print_colored(f"오류: {result.error_message}", 'FAIL')
        
        except Exception as e:
            print_colored(f"❌ 예외 발생: {e}", 'FAIL')
        
        print_colored("-" * 60, 'CYAN')
        
        # 다음 쿼리 전 잠시 대기
        if i < len(DEMO_QUERIES):
            await asyncio.sleep(1)

async def demo_streaming_response():
    """스트리밍 응답 데모"""
    print_separator("📡 스트리밍 응답 데모")
    
    streaming_query = {
        "query": "최근 1년간 월별 신규 가입 고객 수 추이를 분석해주세요",
        "description": "🌊 스트리밍으로 실시간 처리 과정 확인"
    }
    
    print_colored(f"쿼리: {streaming_query['query']}", 'BLUE')
    print_colored(f"설명: {streaming_query['description']}", 'CYAN')
    print_colored("스트리밍 시작...", 'WARNING')
    
    try:
        request = EnhancedSQLGenerationRequest(
            query=streaming_query['query'],
            strategy=ExecutionStrategy.RULE_ONLY,  # 데모용으로 규칙 기반 사용
            enable_streaming=True,
            timeout_seconds=20.0
        )
        
        start_time = time.time()
        event_count = 0
        
        async for event in lcel_sql_pipeline.generate_sql_streaming(request):
            event_count += 1
            event_type = event.get("type", "unknown")
            timestamp = event.get("timestamp", time.time())
            
            if event_type == "start":
                print_colored(f"🟢 시작: {event['data'].get('query', '')[:50]}...", 'GREEN')
            
            elif event_type == "stage_start":
                stage = event.get("stage", "unknown")
                print_colored(f"🔄 단계 시작: {stage}", 'CYAN')
            
            elif event_type == "token":
                content = event.get("content", "")
                print(f"{content}", end="", flush=True)
            
            elif event_type == "stage_end":
                stage = event.get("stage", "unknown")
                print_colored(f"\n✅ 단계 완료: {stage}", 'GREEN')
            
            elif event_type == "pipeline_complete" or event_type == "complete":
                total_time = time.time() - start_time
                print_colored(f"\n🎉 스트리밍 완료!", 'GREEN')
                print_colored(f"총 이벤트 수: {event_count}", 'BLUE')
                print_colored(f"총 소요 시간: {total_time:.2f}초", 'BLUE')
                
                # 최종 결과 출력
                if "result" in event:
                    result_data = event["result"]
                    if "sql_result" in result_data:
                        sql_data = result_data["sql_result"]
                        print_colored(f"최종 SQL: {sql_data.get('sql', 'N/A')}", 'WARNING')
                        print_colored(f"설명: {sql_data.get('explanation', 'N/A')}", 'CYAN')
                
                break
            
            elif event_type == "error":
                print_colored(f"\n❌ 스트리밍 오류: {event.get('error', 'Unknown')}", 'FAIL')
                break
            
            # 너무 많은 이벤트 방지
            if event_count > 20:
                print_colored(f"\n⏸️ 이벤트 수 제한으로 중단 (최대 20개)", 'WARNING')
                break
    
    except Exception as e:
        print_colored(f"❌ 스트리밍 데모 실패: {e}", 'FAIL')

async def demo_different_strategies():
    """다양한 전략 비교 데모"""
    print_separator("🎯 다양한 실행 전략 비교")
    
    test_query = "고객들의 평균 나이를 계산해주세요"
    strategies = [
        (ExecutionStrategy.RULE_ONLY, "규칙 기반만"),
        (ExecutionStrategy.LLM_FIRST, "LLM 우선 (Fallback 포함)"),
    ]
    
    print_colored(f"테스트 쿼리: {test_query}", 'BLUE')
    print_colored("-" * 60, 'CYAN')
    
    results = {}
    
    for strategy, description in strategies:
        print_colored(f"\n📋 전략: {description}", 'HEADER')
        
        try:
            request = EnhancedSQLGenerationRequest(
                query=test_query,
                strategy=strategy,
                timeout_seconds=10.0
            )
            
            start_time = time.time()
            result = await lcel_sql_pipeline.generate_sql(request)
            execution_time = time.time() - start_time
            
            results[strategy] = {
                'success': result.success,
                'time': execution_time,
                'method': result.sql_result.generation_method if result.success else 'failed',
                'confidence': result.sql_result.confidence if result.success else 0.0,
                'sql': result.sql_result.sql if result.success else 'N/A'
            }
            
            if result.success:
                print_colored(f"✅ 성공 ({execution_time:.2f}초)", 'GREEN')
                print_colored(f"생성 방법: {result.sql_result.generation_method}", 'CYAN')
                print_colored(f"신뢰도: {result.sql_result.confidence:.2f}", 'WARNING')
                print_colored(f"SQL: {result.sql_result.sql[:100]}...", 'BLUE')
            else:
                print_colored(f"❌ 실패 ({execution_time:.2f}초)", 'FAIL')
                print_colored(f"오류: {result.error_message}", 'FAIL')
        
        except Exception as e:
            print_colored(f"❌ 예외: {e}", 'FAIL')
            results[strategy] = {
                'success': False,
                'time': 0.0,
                'method': 'exception',
                'confidence': 0.0,
                'sql': 'N/A'
            }
    
    # 결과 비교 표
    print_colored(f"\n📊 전략별 성능 비교", 'HEADER')
    print_colored("+" + "-" * 78 + "+", 'CYAN')
    print_colored(f"| {'전략':<20} | {'성공':<8} | {'시간(초)':<10} | {'방법':<15} | {'신뢰도':<8} |", 'CYAN')
    print_colored("+" + "-" * 78 + "+", 'CYAN')
    
    for strategy, description in strategies:
        if strategy in results:
            r = results[strategy]
            success_str = "✅" if r['success'] else "❌"
            print_colored(f"| {description:<20} | {success_str:<8} | {r['time']:<10.2f} | {r['method']:<15} | {r['confidence']:<8.2f} |", 'BLUE')
    
    print_colored("+" + "-" * 78 + "+", 'CYAN')

async def demo_retry_mechanism():
    """재시도 메커니즘 데모"""
    print_separator("🔄 재시도 메커니즘 데모")
    
    print_colored("재시도 설정을 통한 안정성 향상 시연", 'BLUE')
    
    # 재시도 설정
    retry_config = RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=5.0,
        exponential_base=2.0,
        jitter=True
    )
    
    request = EnhancedSQLGenerationRequest(
        query="재시도 테스트 쿼리",
        strategy=ExecutionStrategy.RULE_ONLY,
        retry_config=retry_config,
        timeout_seconds=15.0
    )
    
    print_colored(f"재시도 설정:", 'CYAN')
    print_colored(f"  - 최대 시도 횟수: {retry_config.max_attempts}", 'BLUE')
    print_colored(f"  - 기본 지연 시간: {retry_config.base_delay}초", 'BLUE')
    print_colored(f"  - 최대 지연 시간: {retry_config.max_delay}초", 'BLUE')
    print_colored(f"  - 지수 백오프 기수: {retry_config.exponential_base}", 'BLUE')
    print_colored(f"  - 지터 사용: {retry_config.jitter}", 'BLUE')
    
    try:
        start_time = time.time()
        result = await lcel_sql_pipeline.generate_sql(request)
        execution_time = time.time() - start_time
        
        if result.success:
            print_colored(f"✅ 성공 ({execution_time:.2f}초)", 'GREEN')
            print_colored(f"재시도 설정이 올바르게 적용됨", 'GREEN')
        else:
            print_colored(f"❌ 실패 ({execution_time:.2f}초)", 'FAIL')
            print_colored(f"오류: {result.error_message}", 'FAIL')
    
    except Exception as e:
        print_colored(f"❌ 예외: {e}", 'FAIL')

async def demo_performance_test():
    """간단한 성능 테스트"""
    print_separator("⚡ 성능 테스트")
    
    print_colored("동시 요청 처리 성능 측정", 'BLUE')
    
    # 테스트 쿼리들
    test_queries = [
        "고객 목록 조회",
        "30대 고객 수",
        "최근 가입 고객",
        "평균 보험료",
        "지역별 고객 분포"
    ]
    
    num_concurrent = len(test_queries)
    print_colored(f"동시 요청 수: {num_concurrent}", 'CYAN')
    
    # 동시 요청 생성
    requests = [
        EnhancedSQLGenerationRequest(
            query=query,
            strategy=ExecutionStrategy.RULE_ONLY,
            timeout_seconds=10.0
        )
        for query in test_queries
    ]
    
    try:
        start_time = time.time()
        
        # 동시 실행
        results = await asyncio.gather(
            *[lcel_sql_pipeline.generate_sql(req) for req in requests],
            return_exceptions=True
        )
        
        total_time = time.time() - start_time
        
        # 결과 분석
        successful = sum(1 for r in results if hasattr(r, 'success') and r.success)
        failed = len(results) - successful
        
        print_colored(f"📊 성능 테스트 결과:", 'HEADER')
        print_colored(f"  - 총 요청 수: {len(requests)}", 'BLUE')
        print_colored(f"  - 성공: {successful}개", 'GREEN')
        print_colored(f"  - 실패: {failed}개", 'FAIL' if failed > 0 else 'BLUE')
        print_colored(f"  - 총 시간: {total_time:.2f}초", 'CYAN')
        print_colored(f"  - 평균 시간: {total_time/len(requests):.2f}초/요청", 'CYAN')
        print_colored(f"  - 처리량: {len(requests)/total_time:.2f}요청/초", 'WARNING')
        
        # 성공률 기반 평가
        success_rate = successful / len(requests) * 100
        if success_rate >= 90:
            print_colored(f"🎉 성공률 {success_rate:.1f}% - 우수함!", 'GREEN')
        elif success_rate >= 70:
            print_colored(f"⚠️ 성공률 {success_rate:.1f}% - 양호함", 'WARNING')
        else:
            print_colored(f"❌ 성공률 {success_rate:.1f}% - 개선 필요", 'FAIL')
    
    except Exception as e:
        print_colored(f"❌ 성능 테스트 실패: {e}", 'FAIL')

async def main():
    """메인 데모 실행"""
    print_colored("LCEL SQL 생성 파이프라인 종합 데모", 'HEADER')
    print_colored("이 데모는 LCEL 기반 SQL 생성 파이프라인의 주요 기능을 시연합니다.", 'BLUE')
    
    demos = [
        ("기본 SQL 생성", demo_basic_sql_generation),
        ("스트리밍 응답", demo_streaming_response),
        ("전략 비교", demo_different_strategies), 
        ("재시도 메커니즘", demo_retry_mechanism),
        ("성능 테스트", demo_performance_test)
    ]
    
    try:
        for i, (name, demo_func) in enumerate(demos, 1):
            print_colored(f"\n\n🎬 데모 {i}/{len(demos)}: {name}", 'HEADER')
            
            try:
                await demo_func()
            except KeyboardInterrupt:
                print_colored("\n\n⏸️ 사용자가 데모를 중단했습니다.", 'WARNING')
                break
            except Exception as e:
                print_colored(f"❌ 데모 '{name}' 실행 중 오류: {e}", 'FAIL')
                import traceback
                traceback.print_exc()
            
            # 다음 데모 전 잠시 대기
            if i < len(demos):
                print_colored("\n⏳ 3초 후 다음 데모를 시작합니다... (Ctrl+C로 중단)", 'WARNING')
                try:
                    await asyncio.sleep(3)
                except KeyboardInterrupt:
                    print_colored("\n\n⏸️ 데모를 중단합니다.", 'WARNING')
                    break
    
    except KeyboardInterrupt:
        print_colored("\n\n⏸️ 전체 데모가 중단되었습니다.", 'WARNING')
    
    print_separator("🎉 데모 완료")
    print_colored("LCEL SQL 생성 파이프라인 데모가 완료되었습니다!", 'GREEN')
    print_colored("자세한 사용법은 documents/guide/LCEL_SQL_PIPELINE_GUIDE.md를 참고하세요.", 'BLUE')

if __name__ == "__main__":
    try:
        print_colored("LCEL SQL 파이프라인 데모를 시작합니다...", 'CYAN')
        asyncio.run(main())
    except KeyboardInterrupt:
        print_colored("\n데모가 중단되었습니다.", 'WARNING')
    except Exception as e:
        print_colored(f"데모 실행 중 오류가 발생했습니다: {e}", 'FAIL')
        import traceback
        traceback.print_exc()
        sys.exit(1)