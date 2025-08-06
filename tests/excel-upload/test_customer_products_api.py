#!/usr/bin/env python3
"""
Customer Products API 테스트 스크립트
- 가입상품 CRUD 테스트
- 관계 데이터 무결성 검증
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import uuid

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('customer_products_api_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CustomerProductsAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.session = None
        self.test_customer_id = None
        self.test_product_ids = []
        
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

    async def setup_test_customer(self, user_id: int = 1) -> Optional[str]:
        """테스트용 고객 생성"""
        test_name = "테스트 고객 생성 (Setup)"
        
        try:
            customer_data = {
                "user_id": user_id,
                "name": "테스트고객_상품API",
                "phone": "010-9999-9999",
                "customer_type": "가입",
                "contact_channel": "테스트",
                "address": "서울시 테스트구 테스트동",
                "job_title": "테스트직업"
            }
            
            async with self.session.post(
                f"{self.base_url}/api/customer/create",
                json=customer_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    customer_id = result.get("customer_id")
                    
                    self.log_test_result(
                        test_name, True,
                        f"테스트 고객 생성 성공: {customer_id}",
                        {"customer_name": result.get("name")}
                    )
                    
                    return customer_id
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"테스트 고객 생성 실패: HTTP {response.status} - {error_text}"
                    )
                    return None
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")
            return None

    async def test_create_product(self, customer_id: str, user_id: int = 1):
        """가입상품 생성 테스트"""
        test_name = "가입상품 생성"
        
        try:
            product_data = {
                "product_name": "종합보험",
                "coverage_amount": "1000만원",
                "subscription_date": "2024-01-15",
                "expiry_renewal_date": "2025-01-15",
                "auto_transfer_date": "15",
                "policy_issued": True
            }
            
            async with self.session.post(
                f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}",
                json=product_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    product_id = result.get("product_id")
                    
                    # 응답 데이터 검증
                    validations = []
                    if result.get("product_name") == product_data["product_name"]:
                        validations.append("상품명 일치")
                    if result.get("coverage_amount") == product_data["coverage_amount"]:
                        validations.append("가입금액 일치")
                    if result.get("policy_issued") == product_data["policy_issued"]:
                        validations.append("증권교부 여부 일치")
                    
                    if len(validations) >= 3:
                        self.test_product_ids.append(product_id)
                        self.log_test_result(
                            test_name, True,
                            f"가입상품 생성 성공: {product_id}",
                            {
                                "product_name": result.get("product_name"),
                                "coverage_amount": result.get("coverage_amount"),
                                "validations": validations
                            }
                        )
                        return product_id
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"응답 데이터 검증 실패: {len(validations)}/3 검증 통과",
                            {"expected": product_data, "actual": result}
                        )
                        return None
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"HTTP {response.status} 오류: {error_text}"
                    )
                    return None
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")
            return None

    async def test_get_customer_products(self, customer_id: str, user_id: int = 1):
        """고객 가입상품 목록 조회 테스트"""
        test_name = "가입상품 목록 조회"
        
        try:
            async with self.session.get(
                f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if isinstance(result, list):
                        product_count = len(result)
                        
                        # 생성한 상품이 목록에 있는지 확인
                        found_products = 0
                        for product in result:
                            if product.get("product_id") in self.test_product_ids:
                                found_products += 1
                        
                        if found_products == len(self.test_product_ids):
                            self.log_test_result(
                                test_name, True,
                                f"가입상품 목록 조회 성공: {product_count}개 상품",
                                {
                                    "total_products": product_count,
                                    "found_test_products": f"{found_products}/{len(self.test_product_ids)}"
                                }
                            )
                        else:
                            self.log_test_result(
                                test_name, False,
                                f"생성한 상품을 목록에서 찾을 수 없음: {found_products}/{len(self.test_product_ids)}",
                                {"products": [p.get("product_id") for p in result]}
                            )
                    else:
                        self.log_test_result(
                            test_name, False,
                            "응답 형식 오류: 배열이 아님",
                            {"response_type": type(result).__name__}
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"HTTP {response.status} 오류: {error_text}"
                    )
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_update_product(self, customer_id: str, product_id: str, user_id: int = 1):
        """가입상품 수정 테스트"""
        test_name = "가입상품 수정"
        
        try:
            update_data = {
                "product_name": "종합보험_수정",
                "coverage_amount": "1500만원",
                "policy_issued": False
            }
            
            async with self.session.put(
                f"{self.base_url}/api/customer/{customer_id}/products/{product_id}?user_id={user_id}",
                json=update_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 수정 내용 검증
                    validations = []
                    if result.get("product_name") == update_data["product_name"]:
                        validations.append("상품명 수정 성공")
                    if result.get("coverage_amount") == update_data["coverage_amount"]:
                        validations.append("가입금액 수정 성공")
                    if result.get("policy_issued") == update_data["policy_issued"]:
                        validations.append("증권교부 여부 수정 성공")
                    
                    if len(validations) >= 3:
                        self.log_test_result(
                            test_name, True,
                            f"가입상품 수정 성공: {product_id}",
                            {
                                "updated_fields": validations,
                                "product_name": result.get("product_name"),
                                "coverage_amount": result.get("coverage_amount")
                            }
                        )
                    else:
                        self.log_test_result(
                            test_name, False,
                            f"수정 내용 검증 실패: {len(validations)}/3 검증 통과",
                            {"expected": update_data, "actual": result}
                        )
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"HTTP {response.status} 오류: {error_text}"
                    )
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_create_multiple_products(self, customer_id: str, user_id: int = 1):
        """여러 가입상품 생성 테스트"""
        test_name = "여러 가입상품 생성"
        
        products_data = [
            {
                "product_name": "건강보험",
                "coverage_amount": "500만원",
                "subscription_date": "2024-02-01",
                "policy_issued": True
            },
            {
                "product_name": "자동차보험",
                "coverage_amount": "300만원",
                "subscription_date": "2024-03-01",
                "policy_issued": False
            },
            {
                "product_name": "여행보험", 
                "coverage_amount": "100만원",
                "subscription_date": "2024-04-01",
                "policy_issued": True
            }
        ]
        
        created_products = []
        
        try:
            for product_data in products_data:
                async with self.session.post(
                    f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}",
                    json=product_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        created_products.append({
                            "product_id": result.get("product_id"),
                            "product_name": result.get("product_name")
                        })
                        self.test_product_ids.append(result.get("product_id"))
            
            if len(created_products) == len(products_data):
                self.log_test_result(
                    test_name, True,
                    f"여러 가입상품 생성 성공: {len(created_products)}개",
                    {
                        "created_products": [p["product_name"] for p in created_products],
                        "total_created": len(created_products)
                    }
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"일부 상품 생성 실패: {len(created_products)}/{len(products_data)}",
                    {"created_products": created_products}
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_data_integrity(self, customer_id: str, user_id: int = 1):
        """관계 데이터 무결성 검증"""
        test_name = "데이터 무결성 검증"
        
        try:
            # 1. 고객 정보 조회
            async with self.session.get(
                f"{self.base_url}/api/customer/{customer_id}?user_id={user_id}"
            ) as response:
                if response.status != 200:
                    self.log_test_result(test_name, False, "고객 정보 조회 실패")
                    return
                
                customer_data = await response.json()
                customer_products = customer_data.get("products", [])
            
            # 2. 별도 API로 가입상품 목록 조회
            async with self.session.get(
                f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}"
            ) as response:
                if response.status != 200:
                    self.log_test_result(test_name, False, "가입상품 목록 조회 실패")
                    return
                
                products_data = await response.json()
            
            # 3. 데이터 일치성 검증
            validations = []
            
            # 상품 개수 비교
            if len(customer_products) == len(products_data):
                validations.append("상품 개수 일치")
            
            # 상품 ID 비교
            customer_product_ids = set(p.get("product_id") for p in customer_products)
            products_ids = set(p.get("product_id") for p in products_data)
            
            if customer_product_ids == products_ids:
                validations.append("상품 ID 일치")
            
            # 상품명 비교
            customer_product_names = set(p.get("product_name") for p in customer_products)
            products_names = set(p.get("product_name") for p in products_data)
            
            if customer_product_names == products_names:
                validations.append("상품명 일치")
            
            # 외래 키 관계 확인
            all_foreign_keys_valid = True
            for product in products_data:
                if not product.get("product_id"):  # product_id 존재 확인
                    all_foreign_keys_valid = False
                    break
            
            if all_foreign_keys_valid:
                validations.append("외래 키 관계 유효")
            
            if len(validations) >= 4:
                self.log_test_result(
                    test_name, True,
                    f"데이터 무결성 검증 성공: {len(validations)}/4 검증 통과",
                    {
                        "validations": validations,
                        "customer_products_count": len(customer_products),
                        "products_api_count": len(products_data)
                    }
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"데이터 무결성 검증 실패: {len(validations)}/4 검증 통과",
                    {
                        "failed_validations": [v for v in ["상품 개수 일치", "상품 ID 일치", "상품명 일치", "외래 키 관계 유효"] if v not in validations],
                        "customer_product_ids": list(customer_product_ids),
                        "products_ids": list(products_ids)
                    }
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_delete_product(self, customer_id: str, product_id: str, user_id: int = 1):
        """가입상품 삭제 테스트"""
        test_name = "가입상품 삭제"
        
        try:
            # 삭제 전 상품 존재 확인
            async with self.session.get(
                f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}"
            ) as response:
                if response.status == 200:
                    products_before = await response.json()
                    count_before = len(products_before)
                else:
                    self.log_test_result(test_name, False, "삭제 전 상품 목록 조회 실패")
                    return
            
            # 상품 삭제
            async with self.session.delete(
                f"{self.base_url}/api/customer/{customer_id}/products/{product_id}?user_id={user_id}"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # 삭제 후 상품 목록 확인
                    async with self.session.get(
                        f"{self.base_url}/api/customer/{customer_id}/products?user_id={user_id}"
                    ) as response:
                        if response.status == 200:
                            products_after = await response.json()
                            count_after = len(products_after)
                            
                            # 삭제된 상품이 목록에서 사라졌는지 확인
                            deleted_product_exists = any(
                                p.get("product_id") == product_id for p in products_after
                            )
                            
                            if count_after == count_before - 1 and not deleted_product_exists:
                                self.log_test_result(
                                    test_name, True,
                                    f"가입상품 삭제 성공: {product_id}",
                                    {
                                        "products_before": count_before,
                                        "products_after": count_after,
                                        "message": result.get("message")
                                    }
                                )
                            else:
                                self.log_test_result(
                                    test_name, False,
                                    f"삭제 후 상태 검증 실패: 삭제 전 {count_before}개, 삭제 후 {count_after}개",
                                    {"deleted_product_still_exists": deleted_product_exists}
                                )
                        else:
                            self.log_test_result(test_name, False, "삭제 후 상품 목록 조회 실패")
                else:
                    error_text = await response.text()
                    self.log_test_result(
                        test_name, False,
                        f"HTTP {response.status} 오류: {error_text}"
                    )
                    
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_error_scenarios(self, customer_id: str, user_id: int = 1):
        """오류 시나리오 테스트"""
        test_name = "오류 시나리오"
        
        error_tests = [
            {
                "name": "존재하지 않는 고객 상품 생성",
                "method": "POST",
                "url": f"/api/customer/{str(uuid.uuid4())}/products?user_id={user_id}",
                "data": {"product_name": "테스트상품"},
                "expected_status": 404
            },
            {
                "name": "존재하지 않는 상품 수정",
                "method": "PUT", 
                "url": f"/api/customer/{customer_id}/products/{str(uuid.uuid4())}?user_id={user_id}",
                "data": {"product_name": "수정테스트"},
                "expected_status": 404
            },
            {
                "name": "존재하지 않는 상품 삭제",
                "method": "DELETE",
                "url": f"/api/customer/{customer_id}/products/{str(uuid.uuid4())}?user_id={user_id}",
                "data": None,
                "expected_status": 404
            },
            {
                "name": "잘못된 UUID 형식",
                "method": "GET",
                "url": f"/api/customer/{customer_id}/products/invalid-uuid?user_id={user_id}",
                "data": None,
                "expected_status": 400
            }
        ]
        
        passed_tests = 0
        
        for error_test in error_tests:
            try:
                url = self.base_url + error_test["url"]
                
                if error_test["method"] == "POST":
                    async with self.session.post(url, json=error_test["data"]) as response:
                        status = response.status
                elif error_test["method"] == "PUT":
                    async with self.session.put(url, json=error_test["data"]) as response:
                        status = response.status
                elif error_test["method"] == "DELETE":
                    async with self.session.delete(url) as response:
                        status = response.status
                else:  # GET
                    async with self.session.get(url) as response:
                        status = response.status
                
                if status == error_test["expected_status"]:
                    passed_tests += 1
                    logger.info(f"    ✅ {error_test['name']}: 예상된 {status} 상태 코드")
                else:
                    logger.info(f"    ❌ {error_test['name']}: 예상 {error_test['expected_status']}, 실제 {status}")
                    
            except Exception as e:
                logger.info(f"    ❌ {error_test['name']}: 예외 발생 - {str(e)}")
        
        success_rate = passed_tests / len(error_tests)
        if success_rate >= 0.75:  # 75% 이상 성공
            self.log_test_result(
                test_name, True,
                f"오류 시나리오 테스트 성공: {passed_tests}/{len(error_tests)} 통과",
                {"success_rate": f"{success_rate*100:.1f}%"}
            )
        else:
            self.log_test_result(
                test_name, False,
                f"오류 시나리오 테스트 부족: {passed_tests}/{len(error_tests)} 통과 (목표: 75% 이상)",
                {"success_rate": f"{success_rate*100:.1f}%"}
            )

    async def cleanup_test_data(self, customer_id: str, user_id: int = 1):
        """테스트 데이터 정리"""
        test_name = "테스트 데이터 정리 (Cleanup)"
        
        try:
            # 테스트 고객 삭제
            async with self.session.delete(
                f"{self.base_url}/api/customer/{customer_id}?user_id={user_id}"
            ) as response:
                if response.status == 200:
                    self.log_test_result(
                        test_name, True,
                        f"테스트 고객 삭제 성공: {customer_id}"
                    )
                else:
                    logger.warning(f"테스트 고객 삭제 실패: HTTP {response.status}")
                    
        except Exception as e:
            logger.warning(f"테스트 데이터 정리 중 오류: {str(e)}")

    async def run_all_tests(self, user_id: int = 1):
        """모든 테스트 실행"""
        logger.info("=" * 80)
        logger.info("🧪 Customer Products API 테스트 시작")
        logger.info("=" * 80)
        
        # 1. 테스트 고객 생성
        customer_id = await self.setup_test_customer(user_id)
        if not customer_id:
            logger.error("테스트 고객 생성 실패 - 테스트 중단")
            return
        
        self.test_customer_id = customer_id
        
        try:
            # 2. 가입상품 CRUD 테스트
            product_id = await self.test_create_product(customer_id, user_id)
            
            if product_id:
                await self.test_get_customer_products(customer_id, user_id)
                await self.test_update_product(customer_id, product_id, user_id)
            
            # 3. 여러 상품 생성 테스트
            await self.test_create_multiple_products(customer_id, user_id)
            
            # 4. 데이터 무결성 검증
            await self.test_data_integrity(customer_id, user_id)
            
            # 5. 오류 시나리오 테스트
            await self.test_error_scenarios(customer_id, user_id)
            
            # 6. 삭제 테스트 (마지막에 실행)
            if self.test_product_ids:
                await self.test_delete_product(customer_id, self.test_product_ids[0], user_id)
            
        finally:
            # 7. 테스트 데이터 정리
            await self.cleanup_test_data(customer_id, user_id)
        
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
        with open('customer_products_api_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info("상세 결과가 customer_products_api_test_results.json 파일에 저장되었습니다.")


async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Customer Products API 테스트')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API 기본 URL')
    parser.add_argument('--user-id', type=int, default=1, help='테스트용 사용자 ID')
    args = parser.parse_args()
    
    async with CustomerProductsAPITester(args.base_url) as tester:
        await tester.run_all_tests(args.user_id)


if __name__ == "__main__":
    asyncio.run(main())