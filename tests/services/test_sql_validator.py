"""
SQL 검증기 테스트 케이스 - pytest 기반
"""
import pytest
from app.services.sql_validator import (
    SQLSecurityValidator, ValidationResult, ThreatLevel,
    ValidationIssue, SQLValidationReport
)


class TestSQLSecurityValidator:
    """SQL 보안 검증기 테스트 클래스"""
    
    @pytest.fixture
    def validator(self):
        """검증기 인스턴스 픽스처"""
        return SQLSecurityValidator()
    
    def test_valid_select_query(self, validator):
        """유효한 SELECT 쿼리 테스트"""
        sql = "SELECT id, name, email FROM customers WHERE created_at > :start_date"
        parameters = {"start_date": "2024-01-01"}
        
        report = validator.validate_sql(sql, parameters)
        
        assert report.is_valid is True
        assert report.result == ValidationResult.SAFE
        assert report.execution_allowed is True
        assert len([i for i in report.issues if i.threat_level == ThreatLevel.CRITICAL]) == 0
    
    def test_dangerous_drop_table(self, validator):
        """위험한 DROP TABLE 구문 테스트"""
        sql = "DROP TABLE customers"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert report.result == ValidationResult.BLOCKED
        assert report.execution_allowed is False
        assert any(i.category == "non_select_query" for i in report.issues)
        assert any(i.category == "dangerous_keyword" for i in report.issues)
    
    def test_sql_injection_union_attack(self, validator):
        """SQL Injection UNION 공격 테스트"""
        sql = "SELECT * FROM customers WHERE id = 1 UNION ALL SELECT * FROM users"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert report.result in [ValidationResult.BLOCKED, ValidationResult.DANGEROUS]
        assert report.execution_allowed is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_sql_injection_comment_attack(self, validator):
        """SQL Injection 주석 공격 테스트"""
        sql = "SELECT * FROM customers WHERE id = 1 -- AND deleted = 0"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_sql_injection_boolean_attack(self, validator):
        """SQL Injection Boolean 공격 테스트"""
        sql = "SELECT * FROM customers WHERE id = 1 OR 1=1"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_unauthorized_table_access(self, validator):
        """허용되지 않은 테이블 접근 테스트"""
        sql = "SELECT * FROM sensitive_data"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "unauthorized_table" for i in report.issues)
        assert any("sensitive_data" in i.description for i in report.issues)
    
    def test_dangerous_system_functions(self, validator):
        """위험한 시스템 함수 테스트"""
        sql = "SELECT pg_read_file('/etc/passwd') FROM customers"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert report.result == ValidationResult.BLOCKED
        assert any(i.threat_level == ThreatLevel.CRITICAL for i in report.issues)
    
    def test_time_based_injection(self, validator):
        """Time-based SQL Injection 테스트"""
        sql = "SELECT * FROM customers WHERE id = 1 AND pg_sleep(10)"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_information_schema_access(self, validator):
        """정보 스키마 접근 시도 테스트"""
        sql = "SELECT table_name FROM information_schema.tables"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
        assert any("information_schema" in i.description.lower() for i in report.issues)
    
    def test_complex_valid_query(self, validator):
        """복잡하지만 유효한 쿼리 테스트"""
        sql = """
        SELECT c.id, c.name, COUNT(m.id) as memo_count
        FROM customers c
        LEFT JOIN memos m ON c.id = m.customer_id
        WHERE c.created_at >= :start_date
        GROUP BY c.id, c.name
        ORDER BY memo_count DESC
        LIMIT 100
        """
        parameters = {"start_date": "2024-01-01"}
        
        report = validator.validate_sql(sql, parameters)
        
        # 복잡한 쿼리지만 안전해야 함
        assert report.execution_allowed is True
        critical_issues = [i for i in report.issues if i.threat_level == ThreatLevel.CRITICAL]
        assert len(critical_issues) == 0
    
    def test_query_too_long(self, validator):
        """너무 긴 쿼리 테스트"""
        # 5000자 이상의 긴 쿼리 생성
        long_where_clause = " OR ".join([f"name = 'user{i}'" for i in range(500)])
        sql = f"SELECT * FROM customers WHERE {long_where_clause}"
        
        report = validator.validate_sql(sql)
        
        assert any(i.category == "query_too_long" for i in report.issues)
    
    def test_empty_query(self, validator):
        """빈 쿼리 테스트"""
        sql = "   "
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "empty_query" for i in report.issues)
    
    def test_parameter_validation(self, validator):
        """파라미터 검증 테스트"""
        sql = "SELECT * FROM customers WHERE id = :user_id"
        parameters = {
            "user_id": 123,
            "invalid-key!": "value",  # 유효하지 않은 키
            "long_param": "x" * 1001  # 너무 긴 값
        }
        
        report = validator.validate_sql(sql, parameters)
        
        assert any(i.category == "invalid_parameter_key" for i in report.issues)
        assert any(i.category == "parameter_too_long" for i in report.issues)
    
    def test_suspicious_comments(self, validator):
        """의심스러운 주석 테스트"""
        sql = "SELECT * FROM customers /* union select * from users */"
        
        report = validator.validate_sql(sql)
        
        assert any(i.category == "suspicious_comment" for i in report.issues)
    
    def test_multiple_statements(self, validator):
        """다중 구문 테스트"""
        sql = "SELECT * FROM customers; DROP TABLE customers;"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert report.result == ValidationResult.BLOCKED
        # DROP 키워드로 인해 위험한 것으로 분류되어야 함
        assert any(i.category == "dangerous_keyword" for i in report.issues)
    
    def test_version_function_access(self, validator):
        """버전 정보 접근 시도 테스트"""
        sql = "SELECT version(), current_user FROM customers"
        
        report = validator.validate_sql(sql)
        
        assert report.is_valid is False
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_concat_injection_attempt(self, validator):
        """문자열 연결을 이용한 인젝션 시도 테스트"""
        sql = "SELECT * FROM customers WHERE name = 'admin' + '' AND password = 'secret'"
        
        report = validator.validate_sql(sql)
        
        # 문자열 조작 패턴으로 탐지되어야 함
        assert any(i.category == "sql_injection_pattern" for i in report.issues)
    
    def test_whitelist_allowed_tables(self, validator):
        """화이트리스트에 허용된 모든 테이블 테스트"""
        allowed_tables = ['customers', 'memos', 'events', 'users', 'prompts']
        
        for table in allowed_tables:
            sql = f"SELECT * FROM {table}"
            report = validator.validate_sql(sql)
            
            # 테이블 자체는 허용되어야 함 (다른 이슈가 없다면)
            table_issues = [i for i in report.issues if i.category == "unauthorized_table"]
            assert len(table_issues) == 0, f"테이블 {table}이 부당하게 차단됨"
    
    def test_case_insensitive_detection(self, validator):
        """대소문자 구분 없는 탐지 테스트"""
        sqls = [
            "DROP TABLE customers",
            "drop table customers",
            "Drop Table Customers",
            "DrOp TaBlE cUsToMeRs"
        ]
        
        for sql in sqls:
            report = validator.validate_sql(sql)
            assert report.is_valid is False
            assert any(i.category == "dangerous_keyword" for i in report.issues)
    
    def test_performance_with_complex_query(self, validator):
        """복잡한 쿼리에서의 성능 테스트"""
        import time
        
        # 복잡한 JOIN과 서브쿼리가 포함된 쿼리
        sql = """
        SELECT 
            c.id, c.name, c.email,
            m.refined_content,
            e.event_type, e.priority,
            COUNT(m2.id) as total_memos
        FROM customers c
        LEFT JOIN memos m ON c.id = m.customer_id
        LEFT JOIN events e ON c.id = e.customer_id
        LEFT JOIN memos m2 ON c.id = m2.customer_id
        WHERE c.created_at >= :start_date
            AND c.email LIKE :email_pattern
            AND e.priority IN ('high', 'medium')
        GROUP BY c.id, c.name, c.email, m.refined_content, e.event_type, e.priority
        HAVING COUNT(m2.id) > 0
        ORDER BY total_memos DESC, c.created_at ASC
        LIMIT 50
        """
        parameters = {
            "start_date": "2024-01-01",
            "email_pattern": "%@company.com"
        }
        
        start_time = time.time()
        report = validator.validate_sql(sql, parameters)
        end_time = time.time()
        
        # 검증 시간이 1초를 넘지 않아야 함
        assert (end_time - start_time) < 1.0
        assert report.execution_allowed is True or len([i for i in report.issues if i.threat_level == ThreatLevel.CRITICAL]) == 0