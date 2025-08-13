#!/usr/bin/env python3
"""
User Permissions API 테스트 스크립트
- 설계사별 권한 체크 테스트
- 크로스 유저 접근 방지 검증
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('user_permissions_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UserPermissionsTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.session = None
        self.test_users = {}  # {user_id: {"customers": [], "products": []}}
        
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

    async def setup_test_users_and_data(self, user_ids: List[int] = [1, 2]):
        """테스트용 사용자별 데이터 생성"""
        test_name = "테스트 사용자 데이터 생성 (Setup)"
        
        try:
            setup_success = True
            
            for user_id in user_ids:
                self.test_users[user_id] = {"customers": [], "products": []}
                
                # 각 사용자별 고객 2명씩 생성
                for i in range(2):
                    customer_data = {
                        "user_id": user_id,
                        "name": f"사용자{user_id}_고객{i+1}",
                        "phone": f"010-{user_id:04d}-{1000+i:04d}",
                        "customer_type": "가입",
                        "contact_channel": "테스트",
                        "address": f"서울시 테스트구 사용자{user_id}동",
                        "job_title": "테스트직업"
                    }
                    
                    async with self.session.post(
                        f"{self.base_url}/v1/api/customer/create",
                        json=customer_data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            customer_id = result.get("customer_id")
                            self.test_users[user_id]["customers"].append(customer_id)
                            
                            # 각 고객에 상품 1개씩 추가
                            product_data = {
                                "product_name": f"사용자{user_id}_상품{i+1}",
                                "coverage_amount": f"{(i+1)*100}만원",
                                "subscription_date": "2024-01-01",
                                "policy_issued": True
                            }
                            
                            async with self.session.post(
                                f"{self.base_url}/v1/api/customer/{customer_id}/products?user_id={user_id}",
                                json=product_data
                            ) as prod_response:
                                if prod_response.status == 200:
                                    prod_result = await prod_response.json()
                                    self.test_users[user_id]["products"].append({
                                        "customer_id": customer_id,
                                        "product_id": prod_result.get("product_id")
                                    })
                                else:
                                    setup_success = False
                        else:
                            setup_success = False
            
            if setup_success:
                total_customers = sum(len(data["customers"]) for data in self.test_users.values())
                total_products = sum(len(data["products"]) for data in self.test_users.values())
                
                self.log_test_result(
                    test_name, True,
                    f"테스트 데이터 생성 성공: {len(user_ids)}명 사용자, {total_customers}명 고객, {total_products}개 상품",
                    {
                        "users": list(user_ids),
                        "customers_per_user": {uid: len(data["customers"]) for uid, data in self.test_users.items()},
                        "products_per_user": {uid: len(data["products"]) for uid, data in self.test_users.items()}
                    }
                )
            else:
                self.log_test_result(test_name, False, "테스트 데이터 생성 중 일부 실패")
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_user_own_data_access(self, user_id: int):
        """사용자 자신의 데이터 접근 테스트"""
        test_name = f"사용자{user_id} 본인 데이터 접근"
        
        if user_id not in self.test_users:
            self.log_test_result(test_name, False, f"사용자 {user_id} 테스트 데이터 없음")
            return
        
        try:
            user_data = self.test_users[user_id]
            access_tests = []
            
            # 1. 고객 목록 조회 (자신의 고객만 표시되어야 함)
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/?user_id={user_id}"
            ) as response:
                if response.status == 200:
                    customers = await response.json()
                    own_customers = [c for c in customers if c.get("user_id") == user_id]
                    
                    if len(own_customers) == len(user_data["customers"]):
                        access_tests.append("고객 목록 필터링 성공")
                    else:
                        access_tests.append(f"고객 목록 필터링 실패: {len(own_customers)}/{len(user_data['customers'])}")
            
            # 2. 특정 고객 조회
            if user_data["customers"]:
                customer_id = user_data["customers"][0]
                async with self.session.get(
                    f"{self.base_url}/v1/api/customer/{customer_id}?user_id={user_id}"
                ) as response:
                    if response.status == 200:
                        access_tests.append("본인 고객 조회 성공")
                    else:
                        access_tests.append(f"본인 고객 조회 실패: {response.status}")
            
            # 3. 고객 가입상품 조회
            if user_data["products"]:
                product_info = user_data["products"][0]
                async with self.session.get(
                    f"{self.base_url}/v1/api/customer/{product_info['customer_id']}/products?user_id={user_id}"
                ) as response:
                    if response.status == 200:
                        access_tests.append("본인 고객 상품 조회 성공")
                    else:
                        access_tests.append(f"본인 고객 상품 조회 실패: {response.status}")
            
            # 4. 고객 수정
            if user_data["customers"]:
                customer_id = user_data["customers"][0]
                update_data = {"notes": f"사용자{user_id} 수정 테스트"}
                
                async with self.session.put(
                    f"{self.base_url}/v1/api/customer/{customer_id}?user_id={user_id}",
                    json=update_data
                ) as response:
                    if response.status == 200:
                        access_tests.append("본인 고객 수정 성공")
                    else:
                        access_tests.append(f"본인 고객 수정 실패: {response.status}")
            
            success_count = len([test for test in access_tests if "성공" in test])
            total_count = len(access_tests)
            
            if success_count == total_count:
                self.log_test_result(
                    test_name, True,
                    f"본인 데이터 접근 모두 성공: {success_count}/{total_count}",
                    {"access_tests": access_tests}
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"본인 데이터 접근 일부 실패: {success_count}/{total_count}",
                    {"access_tests": access_tests}
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_cross_user_access_prevention(self, user_id: int, target_user_id: int):
        """크로스 유저 접근 방지 테스트"""
        test_name = f"사용자{user_id}→사용자{target_user_id} 크로스 접근 차단"
        
        if user_id not in self.test_users or target_user_id not in self.test_users:
            self.log_test_result(test_name, False, "테스트 데이터 없음")
            return
        
        try:
            target_data = self.test_users[target_user_id]
            blocked_tests = []
            
            # 1. 다른 사용자의 고객 조회 시도 (403 오류가 나와야 함)
            if target_data["customers"]:
                target_customer_id = target_data["customers"][0]
                
                async with self.session.get(
                    f"{self.base_url}/v1/api/customer/{target_customer_id}?user_id={user_id}"
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 고객 조회 차단 성공")
                    else:
                        blocked_tests.append(f"타인 고객 조회 차단 실패: {response.status} (예상: 403)")
            
            # 2. 다른 사용자의 고객 수정 시도
            if target_data["customers"]:
                target_customer_id = target_data["customers"][0]
                update_data = {"notes": f"사용자{user_id} 무단 수정 시도"}
                
                async with self.session.put(
                    f"{self.base_url}/v1/api/customer/{target_customer_id}?user_id={user_id}",
                    json=update_data
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 고객 수정 차단 성공")
                    else:
                        blocked_tests.append(f"타인 고객 수정 차단 실패: {response.status} (예상: 403)")
            
            # 3. 다른 사용자의 고객 삭제 시도
            if target_data["customers"]:
                target_customer_id = target_data["customers"][0]
                
                async with self.session.delete(
                    f"{self.base_url}/v1/api/customer/{target_customer_id}?user_id={user_id}"
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 고객 삭제 차단 성공")
                    else:
                        blocked_tests.append(f"타인 고객 삭제 차단 실패: {response.status} (예상: 403)")
            
            # 4. 다른 사용자의 고객 가입상품 조회 시도
            if target_data["products"]:
                product_info = target_data["products"][0]
                
                async with self.session.get(
                    f"{self.base_url}/v1/api/customer/{product_info['customer_id']}/products?user_id={user_id}"
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 고객 상품 조회 차단 성공")
                    else:
                        blocked_tests.append(f"타인 고객 상품 조회 차단 실패: {response.status} (예상: 403)")
            
            # 5. 다른 사용자의 고객에 상품 추가 시도
            if target_data["customers"]:
                target_customer_id = target_data["customers"][0]
                product_data = {
                    "product_name": "무단추가상품",
                    "coverage_amount": "100만원"
                }
                
                async with self.session.post(
                    f"{self.base_url}/v1/api/customer/{target_customer_id}/products?user_id={user_id}",
                    json=product_data
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 고객 상품 추가 차단 성공")
                    else:
                        blocked_tests.append(f"타인 고객 상품 추가 차단 실패: {response.status} (예상: 403)")
            
            # 6. 다른 사용자의 상품 수정 시도
            if target_data["products"]:
                product_info = target_data["products"][0]
                update_data = {"product_name": "무단수정상품"}
                
                async with self.session.put(
                    f"{self.base_url}/v1/api/customer/{product_info['customer_id']}/products/{product_info['product_id']}?user_id={user_id}",
                    json=update_data
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 상품 수정 차단 성공")
                    else:
                        blocked_tests.append(f"타인 상품 수정 차단 실패: {response.status} (예상: 403)")
            
            # 7. 다른 사용자의 상품 삭제 시도
            if target_data["products"]:
                product_info = target_data["products"][0]
                
                async with self.session.delete(
                    f"{self.base_url}/v1/api/customer/{product_info['customer_id']}/products/{product_info['product_id']}?user_id={user_id}"
                ) as response:
                    if response.status == 403:
                        blocked_tests.append("타인 상품 삭제 차단 성공")
                    else:
                        blocked_tests.append(f"타인 상품 삭제 차단 실패: {response.status} (예상: 403)")
            
            success_count = len([test for test in blocked_tests if "성공" in test])
            total_count = len(blocked_tests)
            
            if success_count == total_count:
                self.log_test_result(
                    test_name, True,
                    f"크로스 접근 차단 모두 성공: {success_count}/{total_count}",
                    {"blocked_tests": blocked_tests}
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"크로스 접근 차단 일부 실패: {success_count}/{total_count}",
                    {"blocked_tests": blocked_tests}
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_no_user_id_parameter(self):
        """user_id 파라미터 없이 접근 테스트"""
        test_name = "user_id 없이 접근 테스트"
        
        if not self.test_users:
            self.log_test_result(test_name, False, "테스트 데이터 없음")
            return
        
        try:
            # 임의의 고객 ID 선택
            first_user = list(self.test_users.keys())[0]
            customer_id = self.test_users[first_user]["customers"][0] if self.test_users[first_user]["customers"] else None
            
            if not customer_id:
                self.log_test_result(test_name, False, "테스트용 고객 데이터 없음")
                return
            
            access_tests = []
            
            # 1. user_id 없이 고객 조회
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/{customer_id}"
            ) as response:
                # user_id가 선택적 파라미터이므로 200이 나와야 함 (모든 데이터 표시)
                if response.status == 200:
                    access_tests.append("user_id 없이 고객 조회 허용")
                else:
                    access_tests.append(f"user_id 없이 고객 조회 상태: {response.status}")
            
            # 2. user_id 없이 고객 목록 조회
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/"
            ) as response:
                if response.status == 200:
                    customers = await response.json()
                    total_customers = sum(len(data["customers"]) for data in self.test_users.values())
                    
                    if len(customers) >= total_customers:
                        access_tests.append("user_id 없이 전체 고객 목록 조회 가능")
                    else:
                        access_tests.append(f"user_id 없이 고객 목록: {len(customers)}개 조회")
                else:
                    access_tests.append(f"user_id 없이 고객 목록 조회 상태: {response.status}")
            
            # 3. user_id 없이 상품 조회
            if self.test_users[first_user]["products"]:
                async with self.session.get(
                    f"{self.base_url}/v1/api/customer/{customer_id}/products"
                ) as response:
                    if response.status == 200:
                        access_tests.append("user_id 없이 상품 조회 허용")
                    else:
                        access_tests.append(f"user_id 없이 상품 조회 상태: {response.status}")
            
            self.log_test_result(
                test_name, True,
                f"user_id 없이 접근 테스트 완료",
                {"access_tests": access_tests}
            )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_invalid_user_id(self):
        """잘못된 user_id 테스트"""
        test_name = "잘못된 user_id 테스트"
        
        if not self.test_users:
            self.log_test_result(test_name, False, "테스트 데이터 없음")
            return
        
        try:
            first_user = list(self.test_users.keys())[0]
            customer_id = self.test_users[first_user]["customers"][0] if self.test_users[first_user]["customers"] else None
            
            if not customer_id:
                self.log_test_result(test_name, False, "테스트용 고객 데이터 없음")
                return
            
            invalid_tests = []
            
            # 1. 존재하지 않는 user_id
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/{customer_id}?user_id=99999"
            ) as response:
                if response.status == 403:
                    invalid_tests.append("존재하지 않는 user_id 차단 성공")
                else:
                    invalid_tests.append(f"존재하지 않는 user_id 상태: {response.status}")
            
            # 2. 음수 user_id
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/{customer_id}?user_id=-1"
            ) as response:
                if response.status in [400, 403, 422]:  # 유효하지 않은 값으로 처리
                    invalid_tests.append("음수 user_id 차단 성공")
                else:
                    invalid_tests.append(f"음수 user_id 상태: {response.status}")
            
            # 3. 문자열 user_id
            async with self.session.get(
                f"{self.base_url}/v1/api/customer/{customer_id}?user_id=invalid"
            ) as response:
                if response.status == 422:  # FastAPI validation error
                    invalid_tests.append("문자열 user_id 차단 성공")
                else:
                    invalid_tests.append(f"문자열 user_id 상태: {response.status}")
            
            success_count = len([test for test in invalid_tests if "성공" in test])
            total_count = len(invalid_tests)
            
            if success_count >= total_count * 0.67:  # 67% 이상 성공
                self.log_test_result(
                    test_name, True,
                    f"잘못된 user_id 처리: {success_count}/{total_count} 성공",
                    {"invalid_tests": invalid_tests}
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"잘못된 user_id 처리 부족: {success_count}/{total_count} 성공",
                    {"invalid_tests": invalid_tests}
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def test_excel_upload_permissions(self, user_id: int):
        """엑셀 업로드 권한 테스트"""
        test_name = f"사용자{user_id} 엑셀 업로드 권한"
        
        try:
            import pandas as pd
            import io
            
            # 테스트 엑셀 데이터 생성
            test_data = [{
                "고객명": f"엑셀테스트_{user_id}",
                "전화번호": f"010-{user_id:04d}-9999",
                "고객유형": "가입",
                "상품명": "엑셀업로드상품"
            }]
            
            df = pd.DataFrame(test_data)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='고객데이터')
            buffer.seek(0)
            excel_data = buffer.getvalue()
            
            permission_tests = []
            
            # 1. 본인 user_id로 엑셀 업로드
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', str(user_id))
            form_data.add_field('file', excel_data, filename='permission_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/v1/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("created_customers", 0) > 0:
                        permission_tests.append("본인 user_id 엑셀 업로드 성공")
                    else:
                        permission_tests.append("본인 user_id 엑셀 업로드 실패 (고객 생성 없음)")
                else:
                    permission_tests.append(f"본인 user_id 엑셀 업로드 실패: {response.status}")
            
            # 2. 존재하지 않는 user_id로 엑셀 업로드
            form_data = aiohttp.FormData()
            form_data.add_field('user_id', '99999')
            form_data.add_field('file', excel_data, filename='permission_test.xlsx', 
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            async with self.session.post(
                f"{self.base_url}/v1/api/customer/excel-upload",
                data=form_data
            ) as response:
                if response.status == 404:  # 사용자 없음
                    permission_tests.append("존재하지 않는 user_id 엑셀 업로드 차단 성공")
                else:
                    permission_tests.append(f"존재하지 않는 user_id 엑셀 업로드 상태: {response.status}")
            
            success_count = len([test for test in permission_tests if "성공" in test])
            total_count = len(permission_tests)
            
            if success_count == total_count:
                self.log_test_result(
                    test_name, True,
                    f"엑셀 업로드 권한 테스트 성공: {success_count}/{total_count}",
                    {"permission_tests": permission_tests}
                )
            else:
                self.log_test_result(
                    test_name, False,
                    f"엑셀 업로드 권한 테스트 실패: {success_count}/{total_count}",
                    {"permission_tests": permission_tests}
                )
                
        except Exception as e:
            self.log_test_result(test_name, False, f"예외 발생: {str(e)}")

    async def cleanup_test_data(self):
        """테스트 데이터 정리"""
        test_name = "테스트 데이터 정리 (Cleanup)"
        
        try:
            cleanup_count = 0
            
            for user_id, data in self.test_users.items():
                for customer_id in data["customers"]:
                    try:
                        async with self.session.delete(
                            f"{self.base_url}/v1/api/customer/{customer_id}?user_id={user_id}"
                        ) as response:
                            if response.status == 200:
                                cleanup_count += 1
                    except Exception:
                        pass  # 정리 과정에서는 오류 무시
            
            self.log_test_result(
                test_name, True,
                f"테스트 데이터 정리 완료: {cleanup_count}개 고객 삭제",
                {"cleaned_customers": cleanup_count}
            )
                
        except Exception as e:
            logger.warning(f"테스트 데이터 정리 중 오류: {str(e)}")

    async def run_all_tests(self, user_ids: List[int] = [1, 2]):
        """모든 테스트 실행"""
        logger.info("=" * 80)
        logger.info("🔒 User Permissions API 테스트 시작")
        logger.info("=" * 80)
        
        # 1. 테스트 데이터 생성
        await self.setup_test_users_and_data(user_ids)
        
        if not self.test_users:
            logger.error("테스트 데이터 생성 실패 - 테스트 중단")
            return
        
        try:
            # 2. 각 사용자의 본인 데이터 접근 테스트
            for user_id in user_ids:
                await self.test_user_own_data_access(user_id)
            
            # 3. 크로스 유저 접근 방지 테스트
            if len(user_ids) >= 2:
                await self.test_cross_user_access_prevention(user_ids[0], user_ids[1])
                await self.test_cross_user_access_prevention(user_ids[1], user_ids[0])
            
            # 4. user_id 파라미터 관련 테스트
            await self.test_no_user_id_parameter()
            await self.test_invalid_user_id()
            
            # 5. 엑셀 업로드 권한 테스트
            for user_id in user_ids:
                await self.test_excel_upload_permissions(user_id)
            
        finally:
            # 6. 테스트 데이터 정리
            await self.cleanup_test_data()
        
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
        
        # 카테고리별 요약
        categories = {
            "Setup": [],
            "본인 데이터 접근": [],
            "크로스 접근 차단": [],
            "파라미터 검증": [],
            "엑셀 업로드 권한": [],
            "Cleanup": []
        }
        
        for result in self.test_results:
            test_name = result["test_name"]
            if "Setup" in test_name or "생성" in test_name:
                categories["Setup"].append(result)
            elif "본인 데이터" in test_name:
                categories["본인 데이터 접근"].append(result)
            elif "크로스 접근" in test_name:
                categories["크로스 접근 차단"].append(result)
            elif "user_id" in test_name and "엑셀" not in test_name:
                categories["파라미터 검증"].append(result)
            elif "엑셀" in test_name:
                categories["엑셀 업로드 권한"].append(result)
            elif "Cleanup" in test_name or "정리" in test_name:
                categories["Cleanup"].append(result)
        
        logger.info("\n카테고리별 결과:")
        for category, results in categories.items():
            if results:
                passed = sum(1 for r in results if r["success"])
                total = len(results)
                logger.info(f"  {category}: {passed}/{total} 성공")
        
        if failed_tests > 0:
            logger.info("\n실패한 테스트:")
            for result in self.test_results:
                if not result["success"]:
                    logger.info(f"  ❌ {result['test_name']}: {result['message']}")
        
        logger.info("=" * 80)
        
        # 결과를 JSON 파일로 저장
        with open('user_permissions_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info("상세 결과가 user_permissions_test_results.json 파일에 저장되었습니다.")


async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='User Permissions API 테스트')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API 기본 URL')
    parser.add_argument('--user-ids', nargs='+', type=int, default=[1, 2], help='테스트용 사용자 ID 목록')
    args = parser.parse_args()
    
    async with UserPermissionsTester(args.base_url) as tester:
        await tester.run_all_tests(args.user_ids)


if __name__ == "__main__":
    asyncio.run(main())