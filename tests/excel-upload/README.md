# 보험설계사 엑셀 업로드 시스템 API 테스트

이 디렉토리는 보험설계사 엑셀 업로드 시스템의 모든 API 기능을 종합적으로 테스트하는 Python 스크립트들을 포함합니다.

## 📁 테스트 파일 구조

```
tests/
├── README.md                           # 이 파일
├── run_all_tests.py                   # 통합 테스트 실행기
├── test_enhanced_excel_upload.py      # 엑셀 업로드 API 테스트
├── test_customer_products_api.py      # 고객 상품 API 테스트
└── test_user_permissions.py           # 사용자 권한 테스트
```

## 🧪 테스트 스크립트 개요

### 1. `test_enhanced_excel_upload.py`
**Enhanced Excel Upload API 종합 테스트**

#### 테스트 범위:
- ✅ 기본 엑셀 업로드 (다양한 고객 데이터)
- ✅ 복잡한 컬럼 매핑 (한국어/영어 혼용, 동의어 인식)
- ✅ 고객당 여러 상품 처리 (동일 고객 여러 행 처리)
- ✅ 데이터 검증 (전화번호 포맷팅, 주민번호 마스킹, 날짜 파싱)
- ✅ 오류 시나리오 (잘못된 파일 형식, 빈 파일, 잘못된 사용자 ID)
- ✅ 대용량 파일 처리 (1000행 데이터, 성능 테스트)

#### 검증 항목:
- LLM 매핑 정확도 (80% 이상 목표)
- 데이터 처리 성공률
- 처리 시간 및 성능 지표
- 오류 처리 및 복구 능력

### 2. `test_customer_products_api.py`
**Customer Products API CRUD 테스트**

#### 테스트 범위:
- ✅ 가입상품 생성 (Create)
- ✅ 가입상품 조회 (Read - 목록/개별)
- ✅ 가입상품 수정 (Update - 부분 업데이트)
- ✅ 가입상품 삭제 (Delete)
- ✅ 여러 상품 동시 생성
- ✅ 관계 데이터 무결성 검증
- ✅ 오류 시나리오 (존재하지 않는 ID, 잘못된 형식)

#### 검증 항목:
- CRUD 작업 완전성
- 고객-상품 관계 무결성
- 외래 키 제약조건 준수
- API 응답 데이터 일치성

### 3. `test_user_permissions.py`
**User Permissions 보안 테스트**

#### 테스트 범위:
- ✅ 사용자 본인 데이터 접근 권한
- ✅ 크로스 유저 접근 방지 (403 오류)
- ✅ user_id 파라미터 없이 접근
- ✅ 잘못된 user_id 처리
- ✅ 엑셀 업로드 권한 검증
- ✅ 설계사별 데이터 격리

#### 검증 항목:
- 권한 체크 완전성 (100% 차단 목표)
- 데이터 격리 보안
- 인증/인가 메커니즘
- 보안 오류 처리

## 🚀 실행 방법

### 전체 테스트 실행 (권장)
```bash
# 기본 실행 (localhost:8000)
python tests/run_all_tests.py

# 커스텀 URL로 실행
python tests/run_all_tests.py --base-url http://your-api-server:8000

# 특정 사용자 ID로 테스트
python tests/run_all_tests.py --user-id 3 --user-ids 3 4
```

### 개별 테스트 실행
```bash
# Excel Upload API 테스트만
python tests/run_all_tests.py --excel-only

# Customer Products API 테스트만  
python tests/run_all_tests.py --products-only

# User Permissions 테스트만
python tests/run_all_tests.py --permissions-only
```

### 직접 개별 스크립트 실행
```bash
# Excel Upload 테스트
python tests/test_enhanced_excel_upload.py --user-id 1

# Customer Products 테스트
python tests/test_customer_products_api.py --user-id 1

# User Permissions 테스트
python tests/test_user_permissions.py --user-ids 1 2
```

## 📋 명령줄 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--base-url` | API 서버 URL | `http://localhost:8000` |
| `--user-id` | 주 테스트용 사용자 ID | `1` |
| `--user-ids` | 권한 테스트용 사용자 ID 목록 | `[1, 2]` |
| `--excel-only` | Excel 업로드 테스트만 실행 | False |
| `--products-only` | Customer Products 테스트만 실행 | False |
| `--permissions-only` | User Permissions 테스트만 실행 | False |

## 📊 테스트 결과 파일

테스트 실행 후 다음 파일들이 생성됩니다:

### 개별 테스트 결과
- `excel_upload_test_results.json` - Excel 업로드 테스트 상세 결과
- `customer_products_api_test_results.json` - Customer Products API 테스트 결과  
- `user_permissions_test_results.json` - User Permissions 테스트 결과

### 통합 테스트 결과
- `integrated_test_results_YYYYMMDD_HHMMSS.json` - 전체 테스트 통합 결과
- `test_report_YYYYMMDD_HHMMSS.md` - Markdown 형식 테스트 보고서

### 로그 파일
- `excel_upload_test.log` - Excel 업로드 테스트 로그
- `customer_products_api_test.log` - Customer Products API 테스트 로그
- `user_permissions_test.log` - User Permissions 테스트 로그

## 🔧 테스트 환경 요구사항

### Python 패키지
```bash
pip install aiohttp pandas openpyxl
```

### 시스템 요구사항
- **Python**: 3.8 이상
- **API 서버**: 실행 중인 FastAPI 서버
- **데이터베이스**: PostgreSQL (테스트용 사용자 및 데이터)
- **메모리**: 최소 512MB (대용량 파일 테스트용)
- **디스크**: 임시 파일용 100MB

### 테스트용 사용자 데이터
테스트를 위해 다음 사용자가 데이터베이스에 존재해야 합니다:
- **사용자 ID 1**: 기본 테스트용 설계사
- **사용자 ID 2**: 권한 테스트용 설계사

## 📈 성공 기준

### 전체 시스템
- **전체 성공률**: 80% 이상
- **핵심 기능 성공률**: 90% 이상 (Excel 업로드, CRUD 작업)
- **보안 테스트 성공률**: 95% 이상 (권한 차단)

### Excel Upload API
- **매핑 정확도**: 80% 이상
- **데이터 처리 성공률**: 95% 이상
- **대용량 처리**: 1000행 80% 이상 처리

### Customer Products API  
- **CRUD 완전성**: 100%
- **데이터 무결성**: 100%
- **관계 일치성**: 100%

### User Permissions
- **접근 권한 차단률**: 95% 이상
- **데이터 격리**: 100%
- **보안 오류 처리**: 90% 이상

## 🐛 문제 해결

### 일반적인 문제들

#### 1. 연결 오류 (Connection Error)
```bash
# API 서버가 실행 중인지 확인
curl http://localhost:8000/docs

# 다른 포트 사용 시
python tests/run_all_tests.py --base-url http://localhost:8080
```

#### 2. 사용자 ID 오류 (User Not Found)
```sql
-- 데이터베이스에서 사용자 확인
SELECT id, name FROM users WHERE id IN (1, 2);

-- 테스트용 사용자가 없는 경우 다른 ID 사용
python tests/run_all_tests.py --user-id 3 --user-ids 3 4
```

#### 3. 권한 오류 (Permission Denied)
- 테스트용 사용자에 충분한 권한이 있는지 확인
- 데이터베이스 연결 권한 확인
- API 인증 설정 확인

#### 4. 메모리 부족 (Out of Memory)
```bash
# 대용량 테스트 비활성화
# test_enhanced_excel_upload.py의 test_large_file_handling 주석 처리
```

#### 5. 타임아웃 오류 (Timeout)
- API 서버 성능 확인
- 데이터베이스 성능 확인
- 네트워크 연결 확인

## 📞 지원 및 문의

테스트 관련 문제가 발생하면:

1. **로그 파일 확인**: `*.log` 파일에서 상세 오류 정보 확인
2. **JSON 결과 확인**: `*_results.json` 파일에서 실패 원인 분석
3. **API 서버 로그 확인**: FastAPI 서버의 로그 확인
4. **데이터베이스 상태 확인**: PostgreSQL 연결 및 데이터 확인

## 📝 테스트 추가 및 수정

새로운 테스트를 추가하려면:

1. 해당 테스트 클래스에 새 메서드 추가
2. `log_test_result()` 메서드로 결과 기록
3. `run_all_tests()` 메서드에 새 테스트 호출 추가
4. README 업데이트

예시:
```python
async def test_new_feature(self, user_id: int = 1):
    """새 기능 테스트"""
    test_name = "새 기능"
    
    try:
        # 테스트 로직
        result = await some_api_call()
        
        if result.status == 200:
            self.log_test_result(test_name, True, "성공 메시지")
        else:
            self.log_test_result(test_name, False, "실패 메시지")
            
    except Exception as e:
        self.log_test_result(test_name, False, f"예외 발생: {str(e)}")
```