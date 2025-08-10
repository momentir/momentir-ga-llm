"""
FastAPI 모니터링 미들웨어
자동 요청/응답 추적, 에러율 모니터링, 성능 메트릭 수집
"""

import time
import json
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.utils.cloudwatch_logger import cloudwatch_logger


class CloudWatchMonitoringMiddleware(BaseHTTPMiddleware):
    """CloudWatch 통합 모니터링 미들웨어"""
    
    def __init__(self, app: FastAPI, enable_detailed_logging: bool = True):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging
        self.excluded_paths = {
            "/health", 
            "/metrics", 
            "/docs", 
            "/openapi.json",
            "/favicon.ico"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """미들웨어 핵심 로직"""
        start_time = time.time()
        
        # 요청 정보 수집
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "unknown")
        client_ip = self._get_client_ip(request)
        
        # 제외 경로 확인
        if path in self.excluded_paths:
            return await call_next(request)
        
        # 요청 본문 크기 측정 (가능한 경우)
        content_length = request.headers.get("content-length")
        request_size = int(content_length) if content_length else 0
        
        # 사용자 ID 추출 (인증 헤더나 세션에서)
        user_id = self._extract_user_id(request)
        
        response = None
        status_code = 500
        error_message = None
        
        try:
            # 요청 처리
            response = await call_next(request)
            status_code = response.status_code
            
        except Exception as e:
            error_message = str(e)
            cloudwatch_logger.log_structured(
                "ERROR",
                f"Request processing failed: {method} {path}",
                {
                    "event_type": "request_error",
                    "method": method,
                    "path": path,
                    "error": error_message,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "user_id": user_id
                }
            )
            raise
        
        finally:
            # 응답 시간 계산
            end_time = time.time()
            response_time = end_time - start_time
            
            # 응답 크기 측정 (가능한 경우)
            response_size = 0
            if response and hasattr(response, 'headers'):
                content_length = response.headers.get("content-length")
                response_size = int(content_length) if content_length else 0
            
            # 상세 로깅 (선택적)
            if self.enable_detailed_logging:
                await self._log_request_details(
                    method, path, status_code, response_time,
                    client_ip, user_agent, user_id, request_size, 
                    response_size, error_message
                )
            
            # CloudWatch 메트릭 전송
            await self._send_cloudwatch_metrics(
                method, path, status_code, response_time, user_id
            )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출 (프록시 고려)"""
        # ECS ALB의 경우 X-Forwarded-For 헤더 사용
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # 직접 연결의 경우
        return request.client.host if request.client else "unknown"
    
    def _extract_user_id(self, request: Request) -> int:
        """요청에서 사용자 ID 추출"""
        # Authorization 헤더에서 추출
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # JWT 토큰이나 API 키에서 사용자 ID 추출
            # 실제 구현은 인증 방식에 따라 달라짐
            pass
        
        # 쿠키나 세션에서 추출
        # session_cookie = request.cookies.get("session_id")
        
        # 개발 환경에서는 더미 사용자 ID 사용
        if cloudwatch_logger.environment == "local":
            return 1
        
        return None
    
    async def _log_request_details(self, method: str, path: str, status_code: int, 
                                  response_time: float, client_ip: str, user_agent: str,
                                  user_id: int, request_size: int, response_size: int,
                                  error_message: str = None):
        """상세한 요청 로그 기록"""
        
        log_data = {
            "event_type": "api_request_detailed",
            "method": method,
            "path": path,
            "status_code": status_code,
            "response_time": round(response_time, 4),
            "client_ip": client_ip,
            "user_agent": user_agent[:200],  # User agent 길이 제한
            "user_id": user_id,
            "request_size": request_size,
            "response_size": response_size,
            "success": status_code < 400,
            "error_message": error_message
        }
        
        # 성능 기준에 따른 로그 레벨
        if response_time > 3.0:
            level = "WARNING"
            log_data["performance_alert"] = "Slow response time"
        elif status_code >= 500:
            level = "ERROR"
        elif status_code >= 400:
            level = "WARNING"
        else:
            level = "INFO"
        
        cloudwatch_logger.log_structured(
            level,
            f"{method} {path} - {status_code} - {response_time:.3f}s",
            log_data
        )
    
    async def _send_cloudwatch_metrics(self, method: str, path: str, status_code: int,
                                     response_time: float, user_id: int):
        """CloudWatch 커스텀 메트릭 전송"""
        
        if not cloudwatch_logger.cloudwatch_client:
            return
        
        # 기본 차원
        dimensions = {
            "Method": method,
            "StatusCode": str(status_code),
            "Success": str(status_code < 400)
        }
        
        # 경로별 메트릭 (일반화)
        normalized_path = self._normalize_path(path)
        dimensions["Endpoint"] = normalized_path
        
        # 요청 수 메트릭
        cloudwatch_logger._add_metric("RequestCount", 1, dimensions)
        
        # 응답 시간 메트릭
        cloudwatch_logger._add_metric(
            "ResponseTime", 
            response_time, 
            {"Endpoint": normalized_path, "Method": method}
        )
        
        # 에러율 메트릭
        if status_code >= 400:
            error_dimensions = {
                "Endpoint": normalized_path,
                "StatusCode": str(status_code),
                "ErrorType": "ClientError" if status_code < 500 else "ServerError"
            }
            cloudwatch_logger._add_metric("ErrorCount", 1, error_dimensions)
        
        # 특별한 엔드포인트별 메트릭
        if "search" in normalized_path.lower():
            search_dimensions = {
                "SearchType": "NaturalLanguage" if "natural-language" in path else "Regular"
            }
            cloudwatch_logger._add_metric("SearchRequestCount", 1, search_dimensions)
    
    def _normalize_path(self, path: str) -> str:
        """경로 정규화 (동적 매개변수 제거)"""
        # ID나 UUID 패턴 제거
        import re
        
        # UUID 패턴 제거
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        
        # 숫자 ID 패턴 제거
        path = re.sub(r'/\d+', '/{id}', path)
        
        # 쿼리 매개변수 제거
        path = path.split('?')[0]
        
        return path


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """성능 모니터링 전용 미들웨어 (가벼운 버전)"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.performance_threshold = 3.0  # 3초
        self.last_performance_log = 0
        self.performance_log_interval = 60  # 1분마다 성능 로그
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """성능 중심 모니터링"""
        current_time = time.time()
        
        # 주기적으로 시스템 성능 메트릭 로그
        if current_time - self.last_performance_log > self.performance_log_interval:
            cloudwatch_logger.log_performance_metrics()
            self.last_performance_log = current_time
        
        # 요청 처리
        start_time = time.time()
        response = await call_next(request)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # 성능 임계값 초과 시 알림
        if response_time > self.performance_threshold:
            cloudwatch_logger.log_structured(
                "WARNING",
                f"Slow response detected: {request.method} {request.url.path}",
                {
                    "event_type": "performance_alert",
                    "response_time": response_time,
                    "threshold": self.performance_threshold,
                    "path": request.url.path,
                    "method": request.method
                }
            )
        
        return response


# 미들웨어 설정 함수
def setup_monitoring_middleware(app: FastAPI, enable_detailed: bool = True):
    """FastAPI 앱에 모니터링 미들웨어 추가"""
    
    # 환경에 따른 모니터링 레벨 결정
    environment = cloudwatch_logger.environment
    
    if environment == "production" or cloudwatch_logger.is_ecs_fargate:
        # 프로덕션: 상세 모니터링
        app.add_middleware(CloudWatchMonitoringMiddleware, enable_detailed_logging=enable_detailed)
        cloudwatch_logger.log_structured("INFO", "CloudWatch detailed monitoring enabled")
        
    elif environment == "local" and enable_detailed:
        # 로컬 개발: 간단한 모니터링
        app.add_middleware(PerformanceMonitoringMiddleware)
        cloudwatch_logger.log_structured("INFO", "Performance monitoring enabled")
        
    else:
        # 모니터링 비활성화
        cloudwatch_logger.log_structured("INFO", "Monitoring disabled")