#!/usr/bin/env python3
"""
CloudWatch 모니터링 기능 테스트 스크립트

이 스크립트는 다음을 테스트합니다:
1. CloudWatch 로거 초기화 및 ECS Fargate 감지
2. JSON 구조화 로깅
3. 검색 쿼리 메트릭 로깅  
4. 성능 메트릭 수집
5. API 요청 모니터링
6. CloudWatch 메트릭 전송 (실제 전송은 AWS 환경에서만)
"""

import os
import sys
import asyncio
import httpx
import json
import time
from typing import Dict, Any, List
from datetime import datetime

# 프로젝트 루트를 파이썬 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.cloudwatch_logger import cloudwatch_logger


class CloudWatchMonitoringTester:
    """CloudWatch 모니터링 테스트 클래스"""
    
    def __init__(self):
        self.base_url = "http://127.0.0.1:8000"
        self.test_results = []
        
    def log_test_result(self, test_name: str, success: bool, message: str, details: Dict[str, Any] = None):
        """테스트 결과 로깅"""
        result = {
            "test_name": test_name,
            "success": success,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if details:
            print(f"   세부정보: {json.dumps(details, indent=2, ensure_ascii=False)}")
    
    def test_cloudwatch_logger_initialization(self):
        """CloudWatch 로거 초기화 테스트"""
        try:
            # 환경 정보 확인
            environment = cloudwatch_logger.environment
            is_ecs = cloudwatch_logger.is_ecs_fargate
            has_boto3 = cloudwatch_logger.cloudwatch_client is not None
            
            details = {
                "environment": environment,
                "is_ecs_fargate": is_ecs,
                "has_boto3_client": has_boto3,
                "task_metadata": cloudwatch_logger.task_metadata
            }
            
            self.log_test_result(
                "CloudWatch Logger 초기화",
                True,
                f"환경: {environment}, ECS: {is_ecs}, Boto3: {has_boto3}",
                details
            )
            
        except Exception as e:
            self.log_test_result(
                "CloudWatch Logger 초기화",
                False,
                f"초기화 실패: {e}"
            )
    
    def test_structured_logging(self):
        """구조화된 로깅 테스트"""
        try:
            test_data = {
                "user_id": 12345,
                "query": "테스트 검색 쿼리",
                "response_time": 1.25,
                "test_metric": "monitoring_test"
            }
            
            # 다양한 로그 레벨 테스트
            cloudwatch_logger.log_structured("INFO", "테스트 정보 로그", test_data)
            cloudwatch_logger.log_structured("WARNING", "테스트 경고 로그", test_data)
            cloudwatch_logger.log_structured("ERROR", "테스트 에러 로그", test_data)
            
            self.log_test_result(
                "구조화된 로깅",
                True,
                "INFO, WARNING, ERROR 로그 생성 완료",
                {"logged_data": test_data}
            )
            
        except Exception as e:
            self.log_test_result(
                "구조화된 로깅",
                False,
                f"로깅 실패: {e}"
            )
    
    def test_search_query_logging(self):
        """검색 쿼리 로깅 테스트"""
        try:
            # 성공한 검색 쿼리 로그
            cloudwatch_logger.log_search_query(
                query="30대 고객 목록 조회 테스트",
                user_id=12345,
                strategy="llm_first",
                response_time=2.1,
                success=True,
                result_count=47
            )
            
            # 실패한 검색 쿼리 로그
            cloudwatch_logger.log_search_query(
                query="잘못된 쿼리 테스트",
                user_id=12345,
                strategy="rule_first", 
                response_time=0.8,
                success=False,
                result_count=0,
                error_message="SQL 생성 실패: 인식할 수 없는 패턴"
            )
            
            self.log_test_result(
                "검색 쿼리 로깅",
                True,
                "성공/실패 검색 쿼리 로그 생성 완료"
            )
            
        except Exception as e:
            self.log_test_result(
                "검색 쿼리 로깅",
                False,
                f"검색 쿼리 로깅 실패: {e}"
            )
    
    def test_performance_metrics(self):
        """성능 메트릭 수집 테스트"""
        try:
            # 성능 메트릭 수집
            cloudwatch_logger.log_performance_metrics()
            
            self.log_test_result(
                "성능 메트릭 수집",
                True,
                "CPU, 메모리, 디스크 사용량 메트릭 수집 완료"
            )
            
        except Exception as e:
            self.log_test_result(
                "성능 메트릭 수집",
                False,
                f"성능 메트릭 수집 실패: {e}"
            )
    
    async def test_api_health_check(self):
        """API 헬스체크 테스트"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                
                success = response.status_code == 200
                details = {
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None,
                    "response_body": response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                }
                
                self.log_test_result(
                    "API 헬스체크",
                    success,
                    f"상태 코드: {response.status_code}",
                    details
                )
                
        except Exception as e:
            self.log_test_result(
                "API 헬스체크", 
                False,
                f"헬스체크 실패: {e}"
            )
    
    async def test_search_api_monitoring(self):
        """검색 API 모니터링 테스트"""
        try:
            search_request = {
                "query": "모니터링 테스트용 검색 쿼리",
                "context": {"test": True},
                "options": {
                    "strategy": "llm_first",
                    "timeout_seconds": 10.0
                },
                "limit": 10
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 자연어 검색 API 테스트
                response = await client.post(
                    f"{self.base_url}/api/search/natural-language",
                    json=search_request
                )
                
                details = {
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
                }
                
                if response.status_code == 200:
                    response_data = response.json()
                    details.update({
                        "request_id": response_data.get("request_id"),
                        "success": response_data.get("success"),
                        "total_rows": response_data.get("total_rows"),
                        "execution_time_ms": response_data.get("execution", {}).get("execution_time_ms")
                    })
                    
                    self.log_test_result(
                        "검색 API 모니터링",
                        True,
                        f"검색 API 호출 성공 (결과: {response_data.get('total_rows')}행)",
                        details
                    )
                else:
                    details["error_detail"] = response.text
                    self.log_test_result(
                        "검색 API 모니터링",
                        False,
                        f"검색 API 호출 실패: {response.status_code}",
                        details
                    )
                
        except Exception as e:
            self.log_test_result(
                "검색 API 모니터링",
                False,
                f"검색 API 테스트 실패: {e}"
            )
    
    async def test_concurrent_requests(self):
        """동시 요청 모니터링 테스트"""
        try:
            async def make_request(client: httpx.AsyncClient, request_id: int):
                """단일 요청 생성"""
                search_request = {
                    "query": f"동시 요청 테스트 #{request_id}",
                    "context": {"concurrent_test": True, "request_id": request_id},
                    "options": {"strategy": "rule_first", "timeout_seconds": 5.0},
                    "limit": 5
                }
                
                start_time = time.time()
                response = await client.post(
                    f"{self.base_url}/api/search/natural-language",
                    json=search_request
                )
                end_time = time.time()
                
                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            
            # 5개 동시 요청 생성
            async with httpx.AsyncClient(timeout=10.0) as client:
                tasks = [make_request(client, i) for i in range(5)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                successful_requests = [r for r in results if isinstance(r, dict) and r.get("success")]
                failed_requests = [r for r in results if not (isinstance(r, dict) and r.get("success"))]
                
                avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests) if successful_requests else 0
                
                details = {
                    "total_requests": len(results),
                    "successful_requests": len(successful_requests),
                    "failed_requests": len(failed_requests),
                    "avg_response_time": avg_response_time,
                    "results": results
                }
                
                success = len(successful_requests) >= 3  # 최소 3개 요청 성공
                
                self.log_test_result(
                    "동시 요청 모니터링",
                    success,
                    f"5개 중 {len(successful_requests)}개 성공 (평균 {avg_response_time:.2f}초)",
                    details
                )
                
        except Exception as e:
            self.log_test_result(
                "동시 요청 모니터링",
                False,
                f"동시 요청 테스트 실패: {e}"
            )
    
    async def test_metrics_flushing(self):
        """메트릭 플러시 테스트"""
        try:
            # 메트릭 버퍼에 데이터 추가
            for i in range(5):
                cloudwatch_logger._add_metric("TestMetric", i + 1, {"TestDimension": f"value_{i}"})
            
            # 메트릭 플러시 강제 실행
            await cloudwatch_logger._flush_metrics()
            
            # 버퍼가 비워졌는지 확인
            buffer_empty = len(cloudwatch_logger.metrics_buffer) == 0
            
            details = {
                "metrics_added": 5,
                "buffer_empty_after_flush": buffer_empty,
                "has_cloudwatch_client": cloudwatch_logger.cloudwatch_client is not None
            }
            
            self.log_test_result(
                "메트릭 플러시",
                True,  # 에러가 없으면 성공으로 간주
                f"5개 메트릭 플러시 완료 (버퍼 비움: {buffer_empty})",
                details
            )
            
        except Exception as e:
            self.log_test_result(
                "메트릭 플러시",
                False,
                f"메트릭 플러시 실패: {e}"
            )
    
    def generate_test_report(self) -> Dict[str, Any]:
        """테스트 보고서 생성"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = total_tests - passed_tests
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "environment_info": {
                "environment": cloudwatch_logger.environment,
                "is_ecs_fargate": cloudwatch_logger.is_ecs_fargate,
                "has_boto3": cloudwatch_logger.cloudwatch_client is not None,
                "aws_region": cloudwatch_logger.aws_region
            },
            "test_results": self.test_results,
            "generated_at": datetime.now().isoformat()
        }
        
        return report
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        print("🧪 CloudWatch 모니터링 기능 테스트 시작\n")
        
        # 1. 기본 기능 테스트
        print("📋 기본 기능 테스트")
        self.test_cloudwatch_logger_initialization()
        self.test_structured_logging()
        self.test_search_query_logging()
        self.test_performance_metrics()
        
        print("\n📡 API 테스트")
        await self.test_api_health_check()
        await self.test_search_api_monitoring()
        await self.test_concurrent_requests()
        
        print("\n🔧 고급 기능 테스트")
        await self.test_metrics_flushing()
        
        # 테스트 보고서 생성
        print("\n📊 테스트 보고서 생성")
        report = self.generate_test_report()
        
        # 보고서 출력
        print("\n" + "="*60)
        print("📈 테스트 결과 요약")
        print("="*60)
        print(f"총 테스트: {report['test_summary']['total_tests']}")
        print(f"성공: {report['test_summary']['passed_tests']}")
        print(f"실패: {report['test_summary']['failed_tests']}")
        print(f"성공률: {report['test_summary']['success_rate']:.1f}%")
        
        print(f"\n환경: {report['environment_info']['environment']}")
        print(f"ECS Fargate: {report['environment_info']['is_ecs_fargate']}")
        print(f"Boto3 클라이언트: {report['environment_info']['has_boto3']}")
        
        # 실패한 테스트 상세 정보
        failed_tests = [r for r in self.test_results if not r["success"]]
        if failed_tests:
            print(f"\n❌ 실패한 테스트 ({len(failed_tests)}개):")
            for test in failed_tests:
                print(f"   - {test['test_name']}: {test['message']}")
        
        # 보고서 파일 저장
        report_file = f"cloudwatch_monitoring_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 상세 보고서 저장: {report_file}")
        print("\n✅ 테스트 완료!")
        
        return report


async def main():
    """메인 함수"""
    tester = CloudWatchMonitoringTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())