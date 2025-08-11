# Natural Language Search Testing Guide

## 📋 Overview

Comprehensive test suite for the Natural Language Search functionality with PostgreSQL test environment, SQL injection defense, and performance validation.

## 🏗️ Test Architecture

```
tests/
├── test_nl_search.py          # Main test suite (10 scenarios + security + performance)
scripts/
├── test_db_seeder.py          # Test data generation
├── run_nl_search_tests.sh     # Full test execution
└── simple_nl_test.py          # Quick validation
docker-compose.test.yml        # PostgreSQL test environment
```

## 🚀 Quick Start

### Prerequisites
```bash
# 1. Make sure main server is running
./scripts/02-environment/02-start-local.sh

# 2. Verify Docker is running
docker --version
```

### Simple Test (30 seconds)
```bash
# Quick functionality check
python scripts/simple_nl_test.py
```

### Full Test Suite (5-10 minutes)
```bash
# Comprehensive testing with PostgreSQL environment
./scripts/run_nl_search_tests.sh
```

## 📊 Test Scenarios Covered

### 1. Basic Search Scenarios (10 tests)
- **Customer name search**: "홍길동 고객 정보"
- **Insurance product search**: "화재보험 가입 고객"
- **Policy expiry search**: "이번달 만기 고객" 
- **Demographics**: "30세 이상 남성 고객"
- **Job-based search**: "의사 직업 고객 목록"
- **Contact channel**: "지역마케팅으로 유입된 고객"
- **Date ranges**: "최근 3개월 가입 고객"
- **Policy status**: "증권교부 완료 고객"
- **Coverage ordering**: "가입금액 높은 고객 순으로"
- **Multi-conditions**: "여성이면서 건강보험 가입한 고객"

### 2. SQL Injection Defense (3 tests)
- **Basic injection**: `'; DROP TABLE customers; --`
- **Union-based attack**: `' UNION SELECT password FROM users --`
- **Comment-based injection**: `/* comment */ WHERE 1=1`

### 3. Performance Tests
- **Response time**: < 3 seconds per query
- **Concurrency**: 5 simultaneous requests
- **Error handling**: Graceful failure modes

## 🗄️ Test Database

### Automatic Setup
- PostgreSQL 16 with pgvector extension
- Isolated test environment (port 5433)
- 100 realistic customers, 50 insurance products, 200 memos
- Korean names and addresses for realistic testing

### Test Data Includes
```sql
-- Customers with varied profiles
INSERT INTO customers (name, gender, customer_type, contact_channel, job_title, ...)
VALUES ('홍길동', '남성', '가입', '지역', '회사원', ...);

-- Insurance products with expiry dates
INSERT INTO customer_products (product_name, coverage_amount, expiry_renewal_date, ...)
VALUES ('화재보험', '5000만원', '2025-09-15', ...);
```

## 📈 Expected Results

### ✅ Success Criteria
- All 10 basic scenarios pass
- SQL injection attempts blocked
- Response times < 3 seconds
- 5 concurrent requests handled
- No security vulnerabilities

### 📊 Performance Benchmarks
```
Query Type              | Target Time | Typical Results
--------------------|-------------|----------------
Simple name search     | < 1.5s      | 0.8-1.2s
Complex joins          | < 2.5s      | 1.5-2.0s  
Date range filtering   | < 2.0s      | 1.0-1.8s
Multi-condition        | < 3.0s      | 2.0-2.5s
```

## 🛡️ Security Testing

### SQL Injection Prevention
```python
# These malicious inputs should be safely handled:
"고객 정보'; DROP TABLE customers; --"
"홍길동' UNION SELECT password FROM users --"  
"고객 /* comment */ WHERE 1=1 OR '1'='1"
```

### Expected Behavior
- No database structure modification
- No unauthorized data access
- Graceful error responses (400/422)
- Logging of suspicious attempts

## 🔧 Manual Testing

### Individual Test Execution
```bash
# Run specific test
python -m pytest tests/test_nl_search.py::TestNLSearch::test_customer_name_search -v

# Run only security tests
python -m pytest tests/test_nl_search.py -k "injection" -v

# Run only performance tests  
python -m pytest tests/test_nl_search.py -k "performance" -v
```

### Database Inspection
```bash
# Connect to test database
docker-compose -f docker-compose.test.yml exec postgres-test psql -U test_user -d momentir_test

# Check test data
SELECT COUNT(*) FROM customers;
SELECT name, customer_type FROM customers WHERE name LIKE '홍%';
```

## 🚨 Troubleshooting

### Common Issues

**Test Database Won't Start**
```bash
# Check Docker status
docker ps -a
# Cleanup and retry
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

**Server Connection Failed**
```bash
# Verify main server is running
curl http://127.0.0.1:8000/health
# Restart if needed
./scripts/02-environment/02-start-local.sh
```

**Slow Test Performance**
- Check database connection latency
- Ensure adequate system resources
- Consider running fewer concurrent tests

### Debug Mode
```bash
# Run tests with detailed output
python -m pytest tests/test_nl_search.py -v -s --tb=long
```

## 📝 Test Maintenance

### Adding New Test Scenarios
1. Add test method to `TestNLSearch` class
2. Follow naming convention: `test_description_search`
3. Include performance assertion: `< TestConfig.MAX_RESPONSE_TIME`
4. Validate both SQL generation and result accuracy

### Updating Test Data
1. Modify `scripts/test_db_seeder.py`
2. Add new customer profiles or product types
3. Ensure data supports new test scenarios

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Run NL Search Tests
  run: |
    ./scripts/run_nl_search_tests.sh
  env:
    ENVIRONMENT: test
    DISABLE_KONLPY: true
```

## 🎯 ECS Fargate Optimization

### Resource Requirements
- Memory: 512MB minimum for test execution
- CPU: 256 CPU units adequate
- Ephemeral storage: 21GB (default sufficient)

### Environment Variables
```bash
ENVIRONMENT=test
DISABLE_KONLPY=true
DATABASE_URL=postgresql://test_user:test_password@localhost:5433/momentir_test
```

### AWS CloudWatch Integration
- Test execution metrics automatically collected
- Performance thresholds monitored
- Failed test alerts configured