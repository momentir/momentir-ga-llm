# 테스트 실행 가이드

## 개요

이 문서는 Momentir CX LLM 프로젝트의 테스트 실행 방법을 설명합니다.

## 테스트 환경 설정

### 1. 의존성 설치

```bash
# 가상환경 활성화
source venv/bin/activate

# pytest 및 관련 패키지 설치
pip install -r requirements.txt
```

### 2. 프로젝트 구조

```
tests/
├── services/
│   ├── __init__.py
│   └── test_sql_validator.py          # SQL 보안 검증기 테스트
├── events/
│   ├── test_api_events.py
│   ├── test_event_generation.py
│   └── ...
├── excel-upload/
│   └── ...
└── memo/
    └── ...
```

## 테스트 실행 방법

### 1. 전체 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 상세한 출력과 함께 실행
pytest -v

# 테스트 커버리지와 함께 실행 (pytest-cov 필요)
pytest --cov=app
```

### 2. 특정 테스트 실행

```bash
# SQL 검증기 테스트만 실행
pytest tests/services/test_sql_validator.py

# 특정 테스트 클래스 실행
pytest tests/services/test_sql_validator.py::TestSQLSecurityValidator

# 특정 테스트 메서드 실행
pytest tests/services/test_sql_validator.py::TestSQLSecurityValidator::test_valid_select_query

# 패턴으로 테스트 실행 (키워드 매칭)
pytest -k "sql_injection"
```

### 3. 마커를 이용한 테스트 실행

```bash
# 보안 관련 테스트만 실행
pytest -m security

# 느린 테스트 제외하고 실행
pytest -m "not slow"

# 단위 테스트만 실행
pytest -m unit

# 통합 테스트만 실행
pytest -m integration
```

### 4. 실패한 테스트만 재실행

```bash
# 마지막 실행에서 실패한 테스트만 다시 실행
pytest --lf

# 실패한 테스트를 먼저 실행
pytest --ff
```

## SQL 검증기 테스트 상세

### 테스트 케이스 목록

1. **기본 검증 테스트**
   - `test_valid_select_query` - 유효한 SELECT 쿼리
   - `test_empty_query` - 빈 쿼리 처리

2. **보안 위협 탐지 테스트**
   - `test_dangerous_drop_table` - DROP TABLE 차단
   - `test_sql_injection_union_attack` - UNION 공격 탐지
   - `test_sql_injection_comment_attack` - 주석 공격 탐지
   - `test_sql_injection_boolean_attack` - Boolean 공격 탐지
   - `test_time_based_injection` - Time-based 공격 탐지

3. **시스템 보안 테스트**
   - `test_dangerous_system_functions` - 위험한 시스템 함수 차단
   - `test_information_schema_access` - 스키마 정보 접근 차단
   - `test_version_function_access` - 버전 정보 접근 차단

4. **화이트리스트 검증 테스트**
   - `test_unauthorized_table_access` - 비허용 테이블 접근 차단
   - `test_whitelist_allowed_tables` - 허용된 테이블 접근 허용

5. **성능 및 안정성 테스트**
   - `test_query_too_long` - 긴 쿼리 제한
   - `test_performance_with_complex_query` - 복잡한 쿼리 성능 테스트

### 실행 예시

```bash
# SQL 검증기 테스트 실행
pytest tests/services/test_sql_validator.py -v

# 보안 위협 탐지 테스트만 실행
pytest tests/services/test_sql_validator.py -k "injection" -v

# 성능 테스트만 실행
pytest tests/services/test_sql_validator.py -k "performance" -v
```

### 예상 결과

```
tests/services/test_sql_validator.py::TestSQLSecurityValidator::test_valid_select_query PASSED
tests/services/test_sql_validator.py::TestSQLSecurityValidator::test_dangerous_drop_table PASSED
tests/services/test_sql_validator.py::TestSQLSecurityValidator::test_sql_injection_union_attack PASSED
...
====================== 20 passed in 2.34s ======================
```

## 테스트 작성 가이드

### 1. 새로운 테스트 파일 생성

```python
"""
새로운 서비스 테스트 예시
"""
import pytest
from app.services.your_service import YourService

class TestYourService:
    @pytest.fixture
    def service(self):
        return YourService()
    
    def test_your_feature(self, service):
        # Given
        input_data = "test input"
        
        # When
        result = service.process(input_data)
        
        # Then
        assert result == "expected output"
```

### 2. 비동기 테스트 작성

```python
import pytest

class TestAsyncService:
    @pytest.mark.asyncio
    async def test_async_function(self):
        # Given
        service = AsyncService()
        
        # When
        result = await service.async_process()
        
        # Then
        assert result is not None
```

### 3. 픽스처 활용

```python
@pytest.fixture
def mock_database():
    # 테스트용 데이터베이스 설정
    return MockDatabase()

def test_with_fixture(mock_database):
    # 픽스처 사용
    result = some_function(mock_database)
    assert result == expected_value
```

## 문제 해결

### 1. 모듈 import 오류

```bash
# PYTHONPATH 설정
export PYTHONPATH=$PYTHONPATH:/path/to/project

# 또는 프로젝트 루트에서 실행
cd /Users/chris/developer/momentir/momentir-ga-llm
pytest
```

### 2. 데이터베이스 연결 오류

테스트에서는 실제 데이터베이스 대신 SQLite 메모리 DB를 사용합니다:

```python
# conftest.py에서 설정됨
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_momentir.db"
```

### 3. 환경변수 관련 오류

```bash
# 테스트용 환경변수 설정
export TESTING=true
export OPENAI_API_KEY=test-key-for-testing
```

## 연속 통합 (CI) 설정

GitHub Actions나 다른 CI 도구에서 테스트를 자동화하려면:

```yaml
# .github/workflows/test.yml 예시
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app
```

## 참고 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [pytest-asyncio 문서](https://pytest-asyncio.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

---

**주의사항:**
- 테스트는 실제 데이터베이스나 외부 서비스에 영향을 주지 않도록 격리된 환경에서 실행됩니다.
- 민감한 정보(API 키 등)는 테스트용 더미 값을 사용합니다.
- 테스트 실행 전에 항상 가상환경이 활성화되어 있는지 확인하세요.