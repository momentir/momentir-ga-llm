"""
CloudWatch 통합 로깅 및 메트릭 유틸리티
ECS Fargate 환경 자동 감지 및 구조화된 JSON 로깅
"""

import json
import logging
import os
import time
import asyncio
import psutil
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class CloudWatchLogger:
    """CloudWatch 통합 로거 및 메트릭 관리"""
    
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "local")
        self.ecs_logging_enabled = os.getenv("ECS_ENABLE_LOGGING", "true").lower() == "true"
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
        
        # ECS Fargate 환경 감지
        self.is_ecs_fargate = self._detect_ecs_fargate()
        self.task_metadata = self._get_ecs_task_metadata()
        
        # CloudWatch 클라이언트 초기화
        self.cloudwatch_client = None
        self.logs_client = None
        
        if BOTO3_AVAILABLE and (self.is_ecs_fargate or self.environment == "production"):
            try:
                self.cloudwatch_client = boto3.client('cloudwatch', region_name=self.aws_region)
                self.logs_client = boto3.client('logs', region_name=self.aws_region)
            except (NoCredentialsError, Exception) as e:
                logging.warning(f"CloudWatch 클라이언트 초기화 실패: {e}")
        
        # 로거 설정
        self._setup_logger()
        
        # 메트릭 버퍼
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.buffer_size = 20
        self.last_flush = time.time()
        
    def _detect_ecs_fargate(self) -> bool:
        """ECS Fargate 환경 자동 감지"""
        ecs_indicators = [
            os.path.exists("/proc/1/cgroup"),
            "ECS_CONTAINER_METADATA_URI_V4" in os.environ,
            "AWS_EXECUTION_ENV" in os.environ,
            self.environment == "production"
        ]
        
        if os.path.exists("/proc/1/cgroup"):
            try:
                with open("/proc/1/cgroup", "r") as f:
                    content = f.read()
                    if "ecs" in content.lower():
                        return True
            except Exception:
                pass
                
        return any(ecs_indicators)
    
    def _get_ecs_task_metadata(self) -> Dict[str, Any]:
        """ECS Task 메타데이터 수집"""
        metadata = {
            "environment": self.environment,
            "is_ecs_fargate": self.is_ecs_fargate,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if self.is_ecs_fargate:
            # ECS 메타데이터 URI에서 정보 수집
            metadata_uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4")
            if metadata_uri:
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"{metadata_uri}/task", timeout=2) as response:
                        task_metadata = json.loads(response.read().decode())
                        metadata.update({
                            "cluster": task_metadata.get("Cluster", "unknown"),
                            "task_arn": task_metadata.get("TaskARN", "unknown"),
                            "family": task_metadata.get("Family", "unknown"),
                            "revision": task_metadata.get("Revision", "unknown")
                        })
                except Exception as e:
                    metadata["metadata_error"] = str(e)
        
        return metadata
    
    def _setup_logger(self):
        """구조화된 JSON 로거 설정"""
        self.logger = logging.getLogger("momentir_cloudwatch")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            
            # ECS Fargate용 JSON 포맷터
            if self.is_ecs_fargate:
                formatter = logging.Formatter(
                    '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":%(message)s,"ecs_metadata":' + 
                    json.dumps(self.task_metadata) + '}'
                )
            else:
                formatter = logging.Formatter(
                    '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s","environment":"' + 
                    self.environment + '"}'
                )
            
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_structured(self, level: str, message: str, extra_data: Dict[str, Any] = None):
        """구조화된 로그 메시지 기록"""
        log_data = {
            "message": message,
            "environment": self.environment,
            "is_ecs_fargate": self.is_ecs_fargate
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        # JSON 문자열로 변환하여 로깅
        json_message = json.dumps(log_data, ensure_ascii=False)
        
        if level.upper() == "INFO":
            self.logger.info(json_message)
        elif level.upper() == "WARNING":
            self.logger.warning(json_message)
        elif level.upper() == "ERROR":
            self.logger.error(json_message)
        elif level.upper() == "DEBUG":
            self.logger.debug(json_message)
    
    def log_search_query(self, query: str, user_id: int, strategy: str = None, 
                        response_time: float = None, success: bool = True,
                        result_count: int = None, error_message: str = None):
        """검색 쿼리 로그 기록"""
        log_data = {
            "event_type": "search_query",
            "query": query[:200],  # 쿼리 길이 제한
            "user_id": user_id,
            "strategy": strategy,
            "response_time": response_time,
            "success": success,
            "result_count": result_count,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 성공/실패에 따른 로그 레벨 결정
        level = "INFO" if success else "WARNING"
        self.log_structured(level, "Search query executed", log_data)
        
        # 커스텀 메트릭 추가
        if self.cloudwatch_client:
            self._add_metric("SearchQueries", 1, {"Success": str(success), "Strategy": strategy or "unknown"})
            
            if response_time:
                self._add_metric("SearchResponseTime", response_time, {"Strategy": strategy or "unknown"})
    
    def log_performance_metrics(self):
        """시스템 성능 메트릭 로그 기록"""
        try:
            # CPU 및 메모리 사용량 수집
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics_data = {
                "event_type": "performance_metrics",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_used_percent": disk.percent,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # ECS Fargate 메타데이터가 있다면 추가
            if self.is_ecs_fargate and "task_arn" in self.task_metadata:
                metrics_data["task_arn"] = self.task_metadata["task_arn"]
            
            self.log_structured("INFO", "Performance metrics", metrics_data)
            
            # CloudWatch 커스텀 메트릭으로 전송
            if self.cloudwatch_client:
                self._add_metric("CPUUtilization", cpu_percent)
                self._add_metric("MemoryUtilization", memory.percent)
                
        except Exception as e:
            self.log_structured("ERROR", f"Performance metrics collection failed: {e}")
    
    def _add_metric(self, metric_name: str, value: float, dimensions: Dict[str, str] = None):
        """메트릭을 버퍼에 추가"""
        if not self.cloudwatch_client:
            return
            
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': 'Count' if metric_name in ['SearchQueries'] else 'Seconds' if 'Time' in metric_name else 'Percent',
            'Timestamp': datetime.utcnow(),
            'Dimensions': []
        }
        
        # 기본 차원 추가
        default_dimensions = {
            'Environment': self.environment,
            'Service': 'momentir-cx-llm'
        }
        
        if dimensions:
            default_dimensions.update(dimensions)
        
        for key, value in default_dimensions.items():
            metric_data['Dimensions'].append({'Name': key, 'Value': value})
        
        self.metrics_buffer.append(metric_data)
        
        # 버퍼가 가득 찼거나 일정 시간이 지나면 플러시
        if len(self.metrics_buffer) >= self.buffer_size or (time.time() - self.last_flush) > 60:
            asyncio.create_task(self._flush_metrics())
    
    async def _flush_metrics(self):
        """버퍼된 메트릭을 CloudWatch로 전송"""
        if not self.metrics_buffer or not self.cloudwatch_client:
            return
        
        try:
            # 메트릭을 20개씩 배치로 전송 (CloudWatch 제한)
            batch_size = 20
            for i in range(0, len(self.metrics_buffer), batch_size):
                batch = self.metrics_buffer[i:i + batch_size]
                
                self.cloudwatch_client.put_metric_data(
                    Namespace='MomentirApp/Search',
                    MetricData=batch
                )
            
            self.metrics_buffer.clear()
            self.last_flush = time.time()
            
        except Exception as e:
            self.log_structured("ERROR", f"Failed to flush metrics to CloudWatch: {e}")
    
    @asynccontextmanager
    async def track_request(self, endpoint: str, method: str, user_id: int = None):
        """요청 추적 컨텍스트 매니저"""
        start_time = time.time()
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            response_time = end_time - start_time
            
            # 요청 로그 기록
            request_data = {
                "event_type": "api_request",
                "endpoint": endpoint,
                "method": method,
                "user_id": user_id,
                "response_time": response_time,
                "success": success,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            level = "INFO" if success else "ERROR"
            self.log_structured(level, f"{method} {endpoint}", request_data)
            
            # 메트릭 추가
            if self.cloudwatch_client:
                self._add_metric("APIRequests", 1, {
                    "Endpoint": endpoint,
                    "Method": method,
                    "Success": str(success)
                })
                self._add_metric("APIResponseTime", response_time, {
                    "Endpoint": endpoint
                })


# 글로벌 로거 인스턴스
cloudwatch_logger = CloudWatchLogger()