"""
AWS CloudWatch 메트릭 전송 유틸리티
ECS Fargate 환경에서 커스텀 메트릭 모니터링
"""

import boto3
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class CloudWatchMetricsService:
    """CloudWatch 커스텀 메트릭 서비스"""
    
    def __init__(self):
        self.namespace = "MomentirCX/SearchAnalytics"
        self.cloudwatch = None
        self.enabled = self._init_cloudwatch()
    
    def _init_cloudwatch(self) -> bool:
        """CloudWatch 클라이언트 초기화"""
        try:
            # ECS Fargate에서는 IAM 역할을 통해 자동 인증
            self.cloudwatch = boto3.client('cloudwatch')
            
            # 연결 테스트
            self.cloudwatch.list_metrics(Namespace=self.namespace, MaxRecords=1)
            logger.info("✅ CloudWatch 메트릭 서비스 초기화 완료")
            return True
            
        except NoCredentialsError:
            logger.warning("⚠️ AWS 자격증명이 설정되지 않았습니다. CloudWatch 메트릭이 비활성화됩니다.")
            return False
        except ClientError as e:
            logger.warning(f"⚠️ CloudWatch 초기화 실패: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ CloudWatch 연결 오류: {str(e)}")
            return False
    
    async def put_search_metrics(
        self,
        search_count: int = 1,
        success_count: int = 0,
        failure_count: int = 0,
        response_time: Optional[float] = None,
        strategy: Optional[str] = None,
        user_id: Optional[int] = None
    ):
        """검색 관련 메트릭 전송"""
        if not self.enabled:
            return
        
        try:
            metric_data = []
            
            # 기본 검색 메트릭
            metric_data.extend([
                {
                    'MetricName': 'SearchCount',
                    'Value': search_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': 'SearchSuccess',
                    'Value': success_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': 'SearchFailure',
                    'Value': failure_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ])
            
            # 성공률 메트릭
            if search_count > 0:
                success_rate = (success_count / search_count) * 100
                metric_data.append({
                    'MetricName': 'SearchSuccessRate',
                    'Value': success_rate,
                    'Unit': 'Percent',
                    'Timestamp': datetime.utcnow()
                })
            
            # 응답 시간 메트릭
            if response_time is not None:
                metric_data.append({
                    'MetricName': 'SearchResponseTime',
                    'Value': response_time,
                    'Unit': 'Seconds',
                    'Timestamp': datetime.utcnow()
                })
            
            # 전략별 메트릭
            if strategy:
                metric_data.append({
                    'MetricName': 'SearchByStrategy',
                    'Value': search_count,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'Strategy',
                            'Value': strategy
                        }
                    ],
                    'Timestamp': datetime.utcnow()
                })
            
            # CloudWatch로 메트릭 전송
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.debug(f"CloudWatch 메트릭 전송 완료: {len(metric_data)}개")
            
        except Exception as e:
            logger.error(f"CloudWatch 메트릭 전송 실패: {str(e)}")
    
    async def put_performance_alert(
        self,
        alert_type: str,
        severity: str,
        metric_value: float,
        threshold: float
    ):
        """성능 알림 메트릭 전송"""
        if not self.enabled:
            return
        
        try:
            severity_value = {
                'low': 1,
                'medium': 2, 
                'high': 3
            }.get(severity, 1)
            
            metric_data = [
                {
                    'MetricName': 'PerformanceAlert',
                    'Value': severity_value,
                    'Unit': 'Count',
                    'Dimensions': [
                        {
                            'Name': 'AlertType',
                            'Value': alert_type
                        },
                        {
                            'Name': 'Severity',
                            'Value': severity
                        }
                    ],
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': f'{alert_type}Value',
                    'Value': metric_value,
                    'Unit': 'None',
                    'Timestamp': datetime.utcnow()
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.info(f"성능 알림 메트릭 전송: {alert_type} ({severity})")
            
        except Exception as e:
            logger.error(f"성능 알림 메트릭 전송 실패: {str(e)}")
    
    async def put_failure_pattern_metrics(
        self,
        pattern_count: int,
        high_failure_rate_patterns: int,
        avg_failure_rate: float
    ):
        """실패 패턴 메트릭 전송"""
        if not self.enabled:
            return
        
        try:
            metric_data = [
                {
                    'MetricName': 'FailurePatternCount',
                    'Value': pattern_count,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': 'HighFailureRatePatterns',
                    'Value': high_failure_rate_patterns,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                },
                {
                    'MetricName': 'AvgFailureRate',
                    'Value': avg_failure_rate * 100,  # 백분율로 변환
                    'Unit': 'Percent',
                    'Timestamp': datetime.utcnow()
                }
            ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            logger.debug("실패 패턴 메트릭 전송 완료")
            
        except Exception as e:
            logger.error(f"실패 패턴 메트릭 전송 실패: {str(e)}")
    
    def create_dashboard_config(self) -> Dict:
        """CloudWatch 대시보드 설정 생성"""
        return {
            "widgets": [
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [self.namespace, "SearchCount"],
                            [self.namespace, "SearchSuccess"],
                            [self.namespace, "SearchFailure"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": "ap-northeast-2",
                        "title": "검색 요청 통계"
                    }
                },
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [self.namespace, "SearchSuccessRate"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": "ap-northeast-2",
                        "title": "검색 성공률",
                        "yAxis": {"left": {"min": 0, "max": 100}}
                    }
                },
                {
                    "type": "metric",
                    "properties": {
                        "metrics": [
                            [self.namespace, "SearchResponseTime"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": "ap-northeast-2",
                        "title": "평균 응답 시간"
                    }
                },
                {
                    "type": "metric", 
                    "properties": {
                        "metrics": [
                            [self.namespace, "FailurePatternCount"],
                            [self.namespace, "HighFailureRatePatterns"]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": "ap-northeast-2",
                        "title": "실패 패턴 분석"
                    }
                }
            ]
        }


# 싱글톤 인스턴스
cloudwatch_metrics = CloudWatchMetricsService()