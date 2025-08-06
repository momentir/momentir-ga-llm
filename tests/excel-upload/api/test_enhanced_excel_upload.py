#!/usr/bin/env python3
"""
Enhanced Excel Upload API 테스트 스크립트
- 다양한 형태의 엑셀 파일 업로드 테스트
- LLM 매핑 정확도 검증  
- 오류 시나리오 테스트
"""

import asyncio
import aiohttp
import pandas as pd
import io
import json
import logging
import os
import sys
from datetime import datetime, date
from typing import Dict, List, Any
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('excel_upload_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExcelUploadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def log_test_result(self, test_name: str, success: bool, message: str, details: Dict = None):
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
        logger.info(f"{status} - {test_name}: {message}")
        if details:
            logger.info(f"    Details: {details}")

    def create_test_excel(self, data: List[Dict], filename: str) -> bytes:
        """테스트용 엑셀 파일 생성"""
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='고객데이터')
        buffer.seek(0)
        return buffer.getvalue()

    async def test_basic_excel_upload(self, user_id: int = 1):
        """기본 엑셀 업로드 테스트"""
        test_name = "기본 엑셀 업로드"
        
        try:
            # 테스트 데이터 생성
            test_data = [
                {
                    "고객명": "홍길동",
                    "전화번호": "010-1234-5678",
                    "고객유형": "가입",
                    "접점": "소개",
                    "주소": "서울시 강남구",
                    "직업": "회사원",
                    "상품명": "종합보험",
                    "가입금액": "100만원",
                    "가입일자": "2024-01-15",
                    "증권교부": "Y"
                },
                {
                    "고객명": "김영희",
                    "전화번호": "010-9876-5432",
                    "고객유형": "미가입",
                    "접점": "지역",
                    "주소": "서울시 서초구",
                    "직업": "자영업",
                    "상품명": "건강보험",
                    "가입금액": "200만원",
                    "가입일자": "2024-02-01",
                    "증권교부": "N"
                }
            ]
            
            excel_data = self.create_test_excel(test_data, "basic_test.xlsx")
            
            # API 호출
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='basic_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 결과 검증
                    expected_customers = 2
                    if result.get("created_customers", 0) >= expected_customers:
                        self.log_test_result(
                            test_name, True, 
                            f"성공: {result['created_customers']}명 고객 생성, {result['created_products']}개 상품 생성",
                            {
                                "processed_rows": result.get("processed_rows", 0),
                                "processing_time": f"{result.get('processing_time_seconds', 0):.2f}초",
                                "mapping_success_rate": result.get("mapping_success_rate", {})
                            }
                        )
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"예상보다 적은 고객 생성: {result.get('created_customers', 0)}/{expected_customers}",
                            result
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"HTTP {response.status} 오류: {error_text}"
                    )
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_complex_column_mapping(self, user_id: int = 1):
        """복잡한 컬럼 매핑 테스트"""
        test_name = "복잡한 컬럼 매핑"
        
        try:
            # 다양한 컬럼명을 가진 테스트 데이터
            test_data = [
                {
                    "성명": "박철수",  # name 매핑
                    "핸드폰": "01055556666",  # phone 매핑
                    "분류": "가입고객",  # customer_type 매핑
                    "경로": "가족추천",  # contact_channel 매핑
                    "거주지": "부산시 해운대구",  # address 매핑
                    "직장": "삼성전자",  # job_title 매핑
                    "보험상품": "자동차보험",  # product_name 매핑
                    "보장액": "500만원",  # coverage_amount 매핑
                    "계약일": "2024-03-01",  # subscription_date 매핑
                    "증권발급": "완료"  # policy_issued 매핑
                }
            ]
            
            excel_data = self.create_test_excel(test_data, "complex_mapping_test.xlsx")
            
            # API 호출
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='complex_mapping_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 매핑 정확도 검증
                    mapping = result.get("column_mapping", {})
                    expected_mappings = {
                        "성명": "name",
                        "핸드폰": "phone", 
                        "분류": "customer_type",
                        "경로": "contact_channel",
                        "거주지": "address",
                        "직장": "job_title",
                        "보험상품": "product_name",
                        "보장액": "coverage_amount",
                        "계약일": "subscription_date",
                        "증권발급": "policy_issued"
                    }
                    
                    correct_mappings = 0
                    for excel_col, expected_field in expected_mappings.items():
                        if mapping.get(excel_col) == expected_field:
                            correct_mappings += 1
                    
                    mapping_accuracy = correct_mappings / len(expected_mappings)
                    
                    if mapping_accuracy >= 0.8:  # 80% 이상 정확도
                        self.log_test_result(
                            test_name, True,
                            f"매핑 정확도 {mapping_accuracy*100:.1f}% (목표: 80% 이상)",
                            {
                                "correct_mappings": f"{correct_mappings}/{len(expected_mappings)}",
                                "actual_mapping": mapping,
                                "created_customers": result.get("created_customers", 0),
                                "created_products": result.get("created_products", 0)
                            }
                        )
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"매핑 정확도 부족: {mapping_accuracy*100:.1f}% (목표: 80% 이상)",
                            {
                                "expected_mapping": expected_mappings,
                                "actual_mapping": mapping
                            }
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(test_name, False, f"HTTP {response.status} 오류: {error_text}")
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_multiple_products_per_customer(self, user_id: int = 1):
        """고객당 여러 상품 처리 테스트"""
        test_name = "고객당 여러 상품 처리"
        
        try:
            # 동일 고객의 여러 상품 데이터
            test_data = [
                {
                    "고객명": "이순신",
                    "전화번호": "010-1111-2222",
                    "고객유형": "가입",
                    "상품명": "생명보험",
                    "가입금액": "1000만원",
                    "가입일자": "2024-01-01"
                },
                {
                    "고객명": "이순신",  # 동일 고객
                    "전화번호": "010-1111-2222",  # 동일 전화번호
                    "고객유형": "가입",
                    "상품명": "건강보험",  # 다른 상품
                    "가입금액": "500만원",
                    "가입일자": "2024-01-15"
                },
                {
                    "고객명": "이순신",  # 동일 고객
                    "전화번호": "010-1111-2222",
                    "고객유형": "가입", 
                    "상품명": "자동차보험",  # 또 다른 상품
                    "가입금액": "300만원",
                    "가입일자": "2024-02-01"
                }
            ]
            
            excel_data = self.create_test_excel(test_data, "multiple_products_test.xlsx")
            
            # API 호출
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='multiple_products_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 1명의 고객과 3개의 상품이 생성되어야 함
                    created_customers = result.get("created_customers", 0)
                    created_products = result.get("created_products", 0)
                    
                    if created_customers == 1 and created_products == 3:
                        self.log_test_result(
                            test_name, True,
                            f"성공: 1명 고객에 대해 3개 상품 생성",
                            {
                                "processed_rows": result.get("processed_rows", 0),
                                "created_customers": created_customers,
                                "created_products": created_products
                            }
                        )
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"예상과 다른 결과: 고객 {created_customers}명, 상품 {created_products}개 (예상: 고객 1명, 상품 3개)",
                            result
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(test_name, False, f"HTTP {response.status} 오류: {error_text}")
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_data_validation(self, user_id: int = 1):
        """데이터 검증 기능 테스트"""
        test_name = "데이터 검증 기능"
        
        try:
            # 다양한 형식의 데이터 포함
            test_data = [
                {
                    "고객명": "검증테스트",
                    "전화번호": "01012345678",  # 하이픈 없는 전화번호
                    "주민번호": "8901011234567",  # 마스킹되어야 함
                    "가입일자": "2024/03/15",  # 다른 날짜 형식
                    "증권교부": "예",  # 한글 불린 값
                    "상품명": "테스트보험"
                }
            ]
            
            excel_data = self.create_test_excel(test_data, "validation_test.xlsx")
            
            # API 호출
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='validation_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 데이터가 생성되었고 오류가 없다면 검증 성공
                    created_customers = result.get("created_customers", 0)
                    errors = result.get("errors", [])
                    
                    if created_customers > 0 and len(errors) == 0:
                        # 생성된 고객 데이터 확인
                        async with self.session.get(
                            f"{self.base_url}/api/customer/?user_id={user_id}&search=검증테스트"
                        ) as customer_response:
                            if customer_response.status == 200:
                                customers = await customer_response.json()
                                if customers and len(customers) > 0:
                                    customer = customers[0]
                                    
                                    # 검증 결과 확인
                                    validations = []
                                    if customer.get("phone") and "-" in customer["phone"]:
                                        validations.append("전화번호 형식화 성공")
                                    if customer.get("resident_number") and "*" in customer["resident_number"]:
                                        validations.append("주민번호 마스킹 성공")
                                    
                                    self.log_test_result(
                                        test_name, True,
                                        f"데이터 검증 성공: {', '.join(validations)}",
                                        {
                                            "formatted_phone": customer.get("phone"),
                                            "masked_resident_number": customer.get("resident_number"),
                                            "created_customers": created_customers
                                        }
                                    )
                                else:
                                    self.log_test_result(test_name, False, "생성된 고객 데이터를 찾을 수 없음")
                            else:
                                self.log_test_result(test_name, False, "고객 조회 API 오류")
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"데이터 검증 실패: 생성된 고객 {created_customers}명, 오류 {len(errors)}개",
                            {"errors": errors}
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(test_name, False, f"HTTP {response.status} 오류: {error_text}")
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_error_scenarios(self, user_id: int = 1):
        """오류 시나리오 테스트"""
        test_name = "오류 시나리오"
        
        error_tests = [
            {
                "name": "잘못된 파일 형식",
                "filename": "test.txt",
                "data": b"This is not an excel file",
                "content_type": "text/plain",
                "expected_status": 400
            },
            {
                "name": "빈 엑셀 파일", 
                "filename": "empty.xlsx",
                "data": self.create_test_excel([], "empty.xlsx"),
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "expected_status": 400
            },
            {
                "name": "잘못된 사용자 ID",
                "filename": "test.xlsx",
                "data": self.create_test_excel([{"고객명": "테스트"}], "test.xlsx"),
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "user_id": 99999,  # 존재하지 않는 사용자
                "expected_status": 404
            }
        ]
        
        passed_tests = 0
        
        for error_test in error_tests:
            try:
                form_data = aiohttp.FormData()
                form_data.add_field('user_id', str(error_test.get("user_id", user_id)))
                form_data.add_field('file', error_test["data"], 
                                  filename=error_test["filename"], 
                                  content_type=error_test["content_type"])
                
                async with self.session.post(
                    f"{self.base_url}/api/customer/excel-upload",
                    data=form_data
                ) as response:
                    if response.status == error_test["expected_status"]:
                        passed_tests += 1
                        logger.info(f"    ✅ {error_test['name']}: 예상된 {response.status} 상태 코드")
                    else:
                        logger.info(f"    ❌ {error_test['name']}: 예상 {error_test['expected_status']}, 실제 {response.status}")
                        
            except Exception as e:
                logger.info(f"    ❌ {error_test['name']}: 예외 발생 - {str(e)}")
        
        success_rate = passed_tests / len(error_tests)
        if success_rate >= 0.8:  # 80% 이상 성공
            self.log_test_result(
                test_name, True,
                f"오류 시나리오 테스트 성공: {passed_tests}/{len(error_tests)} 통과",
                {"success_rate": f"{success_rate*100:.1f}%"}
            )
        else:
            self.log_test_result(
                test_name, False,
                f"오류 시나리오 테스트 부족: {passed_tests}/{len(error_tests)} 통과 (목표: 80% 이상)",
                {"success_rate": f"{success_rate*100:.1f}%"}
            )

    async def test_large_file_handling(self, user_id: int = 1):
        """대용량 파일 처리 테스트"""
        test_name = "대용량 파일 처리"
        
        try:
            # 1000행 데이터 생성
            test_data = []
            for i in range(1000):
                test_data.append({
                    "고객명": f"고객{i:04d}",
                    "전화번호": f"010-{1000+i:04d}-{5000+i:04d}",
                    "고객유형": "가입" if i % 2 == 0 else "미가입",
                    "상품명": f"상품{i%10}",
                    "가입금액": f"{(i%10+1)*100}만원"
                })
            
            excel_data = self.create_test_excel(test_data, "large_file_test.xlsx")
            
            # 파일 크기 확인
            file_size_mb = len(excel_data) / (1024 * 1024)
            logger.info(f"    테스트 파일 크기: {file_size_mb:.2f}MB")
            
            # API 호출 (타임아웃 증가)
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='large_file_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            timeout = aiohttp.ClientTimeout(total=300)  # 5분 타임아웃
            
            async with self.session.post(
                f"{self.base_url}/api/customer/excel-upload",
                data=form_data,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    processed_rows = result.get("processed_rows", 0)
                    created_customers = result.get("created_customers", 0)
                    processing_time = result.get("processing_time_seconds", 0)
                    
                    if processed_rows >= 800:  # 80% 이상 처리
                        self.log_test_result(
                            test_name, True,
                            f"대용량 파일 처리 성공: {processed_rows}/1000 행 처리, {processing_time:.2f}초 소요",
                            {
                                "file_size_mb": f"{file_size_mb:.2f}MB",
                                "processed_rows": processed_rows,
                                "created_customers": created_customers,
                                "processing_time": f"{processing_time:.2f}초",
                                "rows_per_second": f"{processed_rows/processing_time:.1f}" if processing_time > 0 else "N/A"
                            }
                        )
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"대용량 파일 처리 부족: {processed_rows}/1000 행 처리 (목표: 800행 이상)",
                            result
                        )
                elif response.status == 413:
                    self.log_test_result(
                        test_name, True,
                        "파일 크기 제한 정상 동작 (413 오류)",
                        {"file_size_mb": f"{file_size_mb:.2f}MB"}
                    )
                else:
                    error_text = await response.text()
                    self.log_test_result(test_name, False, f"HTTP {response.status} 오류: {error_text}")
                    
        except asyncio.TimeoutError:
            self.log_test_result(test_name, False, "타임아웃 발생 (5분 초과)")
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def run_all_tests(self, user_id: int = 1):
        """모든 테스트 실행"""
        logger.info("=" * 80)
        logger.info("🧪 Enhanced Excel Upload API 테스트 시작")
        logger.info("=" * 80)
        
        test_functions = [
            self.test_basic_excel_upload,
            self.test_complex_column_mapping,
            self.test_multiple_products_per_customer,
            self.test_data_validation,
            self.test_error_scenarios,
            self.test_large_file_handling
        ]
        
        for test_func in test_functions:
            try:
                await test_func(user_id)
            except Exception as e:
                logger.error(f"테스트 실행 중 오류: {test_func.__name__} - {str(e)}")
        
        # 결과 요약
        self.print_test_summary()

    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        logger.info("=" * 80)
        logger.info("📊 테스트 결과 요약")
        logger.info("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        logger.info(f"총 테스트: {total_tests}")
        logger.info(f"성공: {passed_tests} ✅")
        logger.info(f"실패: {failed_tests} ❌")
        logger.info(f"성공률: {passed_tests/total_tests*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n실패한 테스트:")
            for result in self.test_results:
                if not result["success"]:
                    logger.info(f"  ❌ {result['test_name']}: {result['message']}")
        
        logger.info("=" * 80)
        
        # 결과를 JSON 파일로 저장
        with open('excel_upload_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info("상세 결과가 excel_upload_test_results.json 파일에 저장되었습니다.")


async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Excel Upload API 테스트')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API 기본 URL')
    parser.add_argument('--user-id', type=int, default=1, help='테스트용 사용자 ID')
    args = parser.parse_args()
    
    async with ExcelUploadTester(args.base_url) as tester:
        await tester.run_all_tests(args.user_id)


if __name__ == "__main__":
    asyncio.run(main())