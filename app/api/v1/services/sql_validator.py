"""
SQL 보안 검증 서비스 - OWASP 가이드라인 기반 SQL Injection 방지
"""
import re
import logging
from typing import Dict, List, Set, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

import sqlparse
from sqlparse import sql, tokens as T
from sqlparse.keywords import KEYWORDS
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ValidationResult(str, Enum):
    """검증 결과 열거형"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    BLOCKED = "blocked"


class ThreatLevel(str, Enum):
    """위협 수준 열거형"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """검증 이슈 정보"""
    threat_level: ThreatLevel
    category: str
    description: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


class SQLValidationReport(BaseModel):
    """SQL 검증 보고서"""
    is_valid: bool = Field(..., description="검증 통과 여부")
    result: ValidationResult = Field(..., description="검증 결과")
    issues: List[ValidationIssue] = Field(default_factory=list, description="발견된 이슈들")
    sanitized_sql: Optional[str] = Field(default=None, description="정제된 SQL (가능한 경우)")
    execution_allowed: bool = Field(..., description="실행 허용 여부")
    
    class Config:
        arbitrary_types_allowed = True


class SQLSecurityValidator:
    """SQL 보안 검증기 - OWASP SQL Injection 방지 가이드라인 적용"""
    
    def __init__(self):
        """검증기 초기화"""
        # 화이트리스트 기반 허용된 테이블과 컬럼
        self.allowed_tables = {
            'users', 'customers', 'customer_memos', 'customer_products', 
            'events', 'prompt_templates'
        }
        
        self.allowed_columns = {
            'users': {'id', 'name', 'email', 'phone', 'created_at', 'updated_at'},
            'customers': {'customer_id', 'name', 'affiliation', 'gender', 'date_of_birth', 'phone', 'address', 'job_title', 'user_id', 'created_at', 'updated_at'},
            'customer_memos': {'id', 'customer_id', 'original_memo', 'refined_memo', 'status', 'author', 'created_at'},
            'customer_products': {'product_id', 'customer_id', 'product_name', 'coverage_amount', 'subscription_date', 'created_at', 'updated_at'},
            'events': {'event_id', 'customer_id', 'memo_id', 'event_type', 'scheduled_date', 'priority', 'status', 'description', 'created_at'},
            'prompt_templates': {'id', 'name', 'description', 'category', 'template_content', 'variables', 'is_active', 'created_at', 'updated_at'}
        }
        
        # OWASP 기반 위험한 키워드 패턴들
        self.dangerous_keywords = {
            # DDL (Data Definition Language) - 매우 위험
            'drop', 'create', 'alter', 'truncate', 'rename',
            # DML (Data Manipulation Language) - 쓰기 작업
            'insert', 'update', 'delete', 'merge', 'replace',
            # DCL (Data Control Language) - 권한 관련
            'grant', 'revoke', 'commit', 'rollback',
            # 시스템 함수들 - 위험
            'exec', 'execute', 'eval', 'load_file', 'into_outfile',
            'load_data', 'bulk', 'openquery', 'openrowset',
            # PostgreSQL 특정 위험 함수들
            'pg_read_file', 'pg_ls_dir', 'pg_stat_file', 'copy',
            'lo_import', 'lo_export'
        }
        
        # SQL Injection 패턴들 (OWASP 기준)
        self.injection_patterns = [
            # 주석 기반 공격
            r'--[\s\S]*',
            r'/\*[\s\S]*?\*/',
            r'#.*',
            
            # Union 기반 공격
            r'\bunion\s+(?:all\s+)?select\b',
            
            # Boolean 기반 공격
            r'\b(?:and|or)\s+[\'"]?[^\'"\s]+[\'"]?\s*=\s*[\'"]?[^\'"\s]+[\'"]?',
            r'\b(?:and|or)\s+\d+\s*=\s*\d+',
            
            # Time 기반 공격
            r'\bsleep\s*\(\s*\d+\s*\)',
            r'\bwaitfor\s+delay\s+[\'"][^\'"]+[\'"]',
            r'\bpg_sleep\s*\(\s*\d+\s*\)',
            
            # 문자열 조작 공격
            r'[\'"][\s]*\+[\s]*[\'"]',
            r'[\'"][\s]*\|\|[\s]*[\'"]',
            r'[\'"][\s]*concat\s*\(',
            
            # 시스템 정보 탐색
            r'\bversion\s*\(\s*\)',
            r'\bdatabase\s*\(\s*\)',
            r'\buser\s*\(\s*\)',
            r'\bcurrent_user\s*(?:\(\s*\))?',
            r'\bsystem_user\s*(?:\(\s*\))?',
            
            # 메타데이터 접근
            r'\binformation_schema\b',
            r'\bpg_catalog\b',
            r'\bsysobjects\b',
            r'\bsyscolumns\b'
        ]
        
        # 컴파일된 정규식 패턴들
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                                for pattern in self.injection_patterns]
        
        logger.info("✅ SQLSecurityValidator 초기화 완료")
    
    def validate_sql(self, sql_query: str, parameters: Optional[Dict] = None) -> SQLValidationReport:
        """
        SQL 쿼리를 종합적으로 검증합니다.
        
        Args:
            sql_query: 검증할 SQL 쿼리
            parameters: SQL 파라미터 (선택사항)
        
        Returns:
            SQLValidationReport: 검증 결과 보고서
        """
        try:
            logger.info(f"SQL 검증 시작: {sql_query[:100]}...")
            
            issues = []
            
            # 1. 기본 안전성 검사
            basic_issues = self._check_basic_safety(sql_query)
            issues.extend(basic_issues)
            
            # 2. SQL Injection 패턴 검사
            injection_issues = self._check_injection_patterns(sql_query)
            issues.extend(injection_issues)
            
            # 3. SQLparse를 이용한 구문 분석
            parse_issues = self._analyze_with_sqlparse(sql_query)
            issues.extend(parse_issues)
            
            # 4. SQLAlchemy text() 검증
            sqlalchemy_issues = self._validate_with_sqlalchemy(sql_query, parameters)
            issues.extend(sqlalchemy_issues)
            
            # 5. 화이트리스트 검증
            whitelist_issues = self._validate_whitelist(sql_query)
            issues.extend(whitelist_issues)
            
            # 6. 결과 종합
            report = self._compile_validation_report(sql_query, issues)
            
            logger.info(f"SQL 검증 완료: {report.result}, 이슈 {len(issues)}개")
            return report
            
        except Exception as e:
            logger.error(f"SQL 검증 중 오류 발생: {e}")
            return SQLValidationReport(
                is_valid=False,
                result=ValidationResult.BLOCKED,
                issues=[ValidationIssue(
                    threat_level=ThreatLevel.HIGH,
                    category="validation_error",
                    description=f"검증 과정에서 오류 발생: {str(e)}"
                )],
                execution_allowed=False
            )
    
    def _check_basic_safety(self, sql_query: str) -> List[ValidationIssue]:
        """기본 안전성 검사"""
        issues = []
        sql_lower = sql_query.lower().strip()
        
        # 1. 빈 쿼리 검사
        if not sql_lower:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.MEDIUM,
                category="empty_query",
                description="빈 SQL 쿼리입니다."
            ))
            return issues
        
        # 2. SELECT 문만 허용 (읽기 전용)
        if not sql_lower.startswith('select'):
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.HIGH,
                category="non_select_query",
                description="SELECT 문만 허용됩니다.",
                suggestion="읽기 전용 쿼리만 사용하세요."
            ))
        
        # 3. 위험한 키워드 검사
        for keyword in self.dangerous_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', sql_lower):
                issues.append(ValidationIssue(
                    threat_level=ThreatLevel.CRITICAL,
                    category="dangerous_keyword",
                    description=f"위험한 키워드 발견: {keyword}",
                    location=keyword,
                    suggestion="허용된 SELECT 쿼리만 사용하세요."
                ))
        
        # 4. 쿼리 길이 검사 (DoS 방지)
        if len(sql_query) > 5000:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.MEDIUM,
                category="query_too_long",
                description=f"쿼리가 너무 깁니다 ({len(sql_query)}자). 최대 5000자까지 허용됩니다.",
                suggestion="쿼리를 간단하게 줄여주세요."
            ))
        
        return issues
    
    def _check_injection_patterns(self, sql_query: str) -> List[ValidationIssue]:
        """SQL Injection 패턴 검사"""
        issues = []
        
        for i, pattern in enumerate(self.compiled_patterns):
            matches = pattern.findall(sql_query)
            if matches:
                issues.append(ValidationIssue(
                    threat_level=ThreatLevel.CRITICAL,
                    category="sql_injection_pattern",
                    description=f"SQL Injection 패턴 감지: {matches[0][:50]}...",
                    location=f"패턴 #{i+1}",
                    suggestion="파라미터 바인딩을 사용하세요."
                ))
        
        return issues
    
    def _analyze_with_sqlparse(self, sql_query: str) -> List[ValidationIssue]:
        """sqlparse를 이용한 구문 분석"""
        issues = []
        
        try:
            # SQL 파싱
            parsed = sqlparse.parse(sql_query)
            
            if not parsed:
                issues.append(ValidationIssue(
                    threat_level=ThreatLevel.HIGH,
                    category="parse_error",
                    description="SQL 구문 파싱에 실패했습니다."
                ))
                return issues
            
            # 각 statement 검사
            for statement in parsed:
                statement_issues = self._analyze_statement(statement)
                issues.extend(statement_issues)
        
        except Exception as e:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.MEDIUM,
                category="sqlparse_error",
                description=f"sqlparse 분석 중 오류: {str(e)}"
            ))
        
        return issues
    
    def _analyze_statement(self, statement: sql.Statement) -> List[ValidationIssue]:
        """개별 SQL 구문 분석"""
        issues = []
        
        # 토큰별 분석
        for token in statement.flatten():
            # 주석 검사
            if token.ttype in (T.Comment.Single, T.Comment.Multiline):
                if self._is_suspicious_comment(token.value):
                    issues.append(ValidationIssue(
                        threat_level=ThreatLevel.HIGH,
                        category="suspicious_comment",
                        description=f"의심스러운 주석 발견: {token.value[:50]}",
                        suggestion="주석을 제거하세요."
                    ))
            
            # 문자열 리터럴 검사
            elif token.ttype in (T.Literal.String.Single, T.Literal.String.Symbol):
                if self._is_suspicious_string(token.value):
                    issues.append(ValidationIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        category="suspicious_string",
                        description=f"의심스러운 문자열 발견: {token.value[:50]}",
                        suggestion="파라미터 바인딩을 사용하세요."
                    ))
        
        return issues
    
    def _validate_with_sqlalchemy(self, sql_query: str, parameters: Optional[Dict] = None) -> List[ValidationIssue]:
        """SQLAlchemy text()를 이용한 기본 검증"""
        issues = []
        
        try:
            # text() 객체 생성 시도
            textual_query = text(sql_query)
            
            # 파라미터 검증
            if parameters:
                param_issues = self._validate_parameters(parameters)
                issues.extend(param_issues)
                
        except SQLAlchemyError as e:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.HIGH,
                category="sqlalchemy_error",
                description=f"SQLAlchemy 검증 실패: {str(e)}",
                suggestion="SQL 구문을 확인하세요."
            ))
        except Exception as e:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.MEDIUM,
                category="sql_validation_error",
                description=f"SQL 검증 실패: {str(e)}"
            ))
        
        return issues
    
    def _validate_whitelist(self, sql_query: str) -> List[ValidationIssue]:
        """화이트리스트 기반 테이블/컬럼 검증"""
        issues = []
        
        try:
            # 간단한 테이블 추출 (더 정교한 파싱이 필요할 수 있음)
            table_pattern = r'\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            join_pattern = r'\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            
            # FROM 절에서 테이블 추출
            from_tables = re.findall(table_pattern, sql_query, re.IGNORECASE)
            join_tables = re.findall(join_pattern, sql_query, re.IGNORECASE)
            
            all_tables = set(from_tables + join_tables)
            
            # 허용되지 않은 테이블 검사
            for table in all_tables:
                if table.lower() not in self.allowed_tables:
                    issues.append(ValidationIssue(
                        threat_level=ThreatLevel.HIGH,
                        category="unauthorized_table",
                        description=f"허용되지 않은 테이블 접근: {table}",
                        location=table,
                        suggestion=f"허용된 테이블만 사용하세요: {', '.join(self.allowed_tables)}"
                    ))
            
            # 컬럼 검증 (기본적인 패턴만)
            column_issues = self._validate_columns(sql_query, all_tables)
            issues.extend(column_issues)
            
        except Exception as e:
            issues.append(ValidationIssue(
                threat_level=ThreatLevel.LOW,
                category="whitelist_validation_error",
                description=f"화이트리스트 검증 중 오류: {str(e)}"
            ))
        
        return issues
    
    def _validate_columns(self, sql_query: str, tables: Set[str]) -> List[ValidationIssue]:
        """컬럼 화이트리스트 검증 (기본적인 구현)"""
        issues = []
        
        # 이는 매우 기본적인 구현입니다. 실제로는 더 정교한 SQL 파싱이 필요합니다.
        # 여기서는 간단한 패턴 매칭만 수행합니다.
        
        for table in tables:
            if table.lower() in self.allowed_columns:
                allowed_cols = self.allowed_columns[table.lower()]
                
                # SELECT 절에서 컬럼명 추출 (매우 기본적)
                select_pattern = r'select\s+([^from]+)\s+from'
                match = re.search(select_pattern, sql_query, re.IGNORECASE | re.DOTALL)
                
                if match:
                    select_clause = match.group(1).strip()
                    
                    # * 는 허용
                    if select_clause == '*':
                        continue
                    
                    # 개별 컬럼 검사 (간단한 파싱)
                    columns = [col.strip() for col in select_clause.split(',')]
                    for col in columns:
                        # 함수나 별칭 제거
                        clean_col = re.sub(r'\s+as\s+\w+', '', col, flags=re.IGNORECASE)
                        clean_col = re.sub(r'\w+\s*\(.*?\)', '', clean_col)
                        clean_col = clean_col.strip()
                        
                        if clean_col and clean_col not in allowed_cols:
                            issues.append(ValidationIssue(
                                threat_level=ThreatLevel.MEDIUM,
                                category="unauthorized_column",
                                description=f"테이블 {table}에서 허용되지 않은 컬럼: {clean_col}",
                                suggestion=f"허용된 컬럼만 사용하세요: {', '.join(allowed_cols)}"
                            ))
        
        return issues
    
    def _validate_parameters(self, parameters: Dict) -> List[ValidationIssue]:
        """파라미터 검증"""
        issues = []
        
        for key, value in parameters.items():
            # 파라미터 키 검증
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                issues.append(ValidationIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    category="invalid_parameter_key",
                    description=f"유효하지 않은 파라미터 키: {key}"
                ))
            
            # 파라미터 값 검증
            if isinstance(value, str) and len(value) > 1000:
                issues.append(ValidationIssue(
                    threat_level=ThreatLevel.LOW,
                    category="parameter_too_long",
                    description=f"파라미터 값이 너무 깁니다: {key} ({len(value)}자)"
                ))
        
        return issues
    
    def _is_suspicious_comment(self, comment: str) -> bool:
        """의심스러운 주석 검사"""
        suspicious_patterns = [
            r'union', r'select', r'drop', r'insert', r'update', r'delete',
            r'exec', r'script', r'eval', r'<script>', r'javascript:'
        ]
        
        comment_lower = comment.lower()
        return any(re.search(pattern, comment_lower) for pattern in suspicious_patterns)
    
    def _is_suspicious_string(self, string_value: str) -> bool:
        """의심스러운 문자열 검사"""
        # 따옴표 제거
        clean_string = string_value.strip('\'"')
        
        # SQL 키워드가 포함된 문자열 검사
        sql_keywords = ['union', 'select', 'drop', 'exec', 'script']
        return any(keyword in clean_string.lower() for keyword in sql_keywords)
    
    def _compile_validation_report(self, sql_query: str, issues: List[ValidationIssue]) -> SQLValidationReport:
        """검증 결과를 종합하여 최종 보고서 생성"""
        
        # 위협 수준별 이슈 분류
        critical_issues = [i for i in issues if i.threat_level == ThreatLevel.CRITICAL]
        high_issues = [i for i in issues if i.threat_level == ThreatLevel.HIGH]
        medium_issues = [i for i in issues if i.threat_level == ThreatLevel.MEDIUM]
        low_issues = [i for i in issues if i.threat_level == ThreatLevel.LOW]
        
        # 결과 결정
        if critical_issues:
            result = ValidationResult.BLOCKED
            is_valid = False
            execution_allowed = False
        elif high_issues:
            result = ValidationResult.DANGEROUS
            is_valid = False
            execution_allowed = False
        elif medium_issues:
            result = ValidationResult.SUSPICIOUS
            is_valid = len(medium_issues) <= 2  # 중간 위험도 2개까지는 허용
            execution_allowed = is_valid
        else:
            result = ValidationResult.SAFE
            is_valid = True
            execution_allowed = True
        
        return SQLValidationReport(
            is_valid=is_valid,
            result=result,
            issues=issues,
            execution_allowed=execution_allowed
        )


# 싱글톤 인스턴스
sql_validator = SQLSecurityValidator()