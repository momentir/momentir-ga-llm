#!/usr/bin/env python3
"""
통합 테스트 실행 스크립트
모든 API 테스트를 순차적으로 실행하고 종합 결과를 제공합니다.
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from datetime import datetime
import argparse

# 테스트 모듈들 import
from test_enhanced_excel_upload import ExcelUploadTester
from test_customer_products_api import CustomerProductsAPITester
from test_user_permissions import UserPermissionsTester

class IntegratedTestRunner:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.all_results = {
            "test_execution": {
                "start_time": None,
                "end_time": None,
                "total_duration_seconds": 0
            },
            "excel_upload": {"results": [], "summary": {}},
            "customer_products": {"results": [], "summary": {}},
            "user_permissions": {"results": [], "summary": {}}
        }
    
    def calculate_summary(self, results: list) -> dict:
        """테스트 결과 요약 계산"""
        if not results:
            return {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0}
        
        total = len(results)
        passed = sum(1 for r in results if r.get("success", False))
        failed = total - passed
        success_rate = (passed / total) * 100 if total > 0 else 0.0
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": round(success_rate, 1)
        }
    
    async def run_excel_upload_tests(self, user_id: int = 1):
        """엑셀 업로드 테스트 실행"""
        print("🧪 Enhanced Excel Upload API 테스트 실행 중...")
        
        try:
            async with ExcelUploadTester(self.base_url) as tester:
                await tester.run_all_tests(user_id)
                
                # 결과 수집
                self.all_results["excel_upload"]["results"] = tester.test_results
                self.all_results["excel_upload"]["summary"] = self.calculate_summary(tester.test_results)
                
                print(f"✅ Excel Upload 테스트 완료: {self.all_results['excel_upload']['summary']['success_rate']}% 성공률")
                
        except Exception as e:
            print(f"❌ Excel Upload 테스트 실행 중 오류: {str(e)}")
            self.all_results["excel_upload"]["error"] = str(e)
    
    async def run_customer_products_tests(self, user_id: int = 1):
        """고객 상품 API 테스트 실행"""
        print("🛒 Customer Products API 테스트 실행 중...")
        
        try:
            async with CustomerProductsAPITester(self.base_url) as tester:
                await tester.run_all_tests(user_id)
                
                # 결과 수집
                self.all_results["customer_products"]["results"] = tester.test_results
                self.all_results["customer_products"]["summary"] = self.calculate_summary(tester.test_results)
                
                print(f"✅ Customer Products 테스트 완료: {self.all_results['customer_products']['summary']['success_rate']}% 성공률")
                
        except Exception as e:
            print(f"❌ Customer Products 테스트 실행 중 오류: {str(e)}")
            self.all_results["customer_products"]["error"] = str(e)
    
    async def run_user_permissions_tests(self, user_ids: list = [1, 2]):
        """사용자 권한 테스트 실행"""
        print("🔒 User Permissions API 테스트 실행 중...")
        
        try:
            async with UserPermissionsTester(self.base_url) as tester:
                await tester.run_all_tests(user_ids)
                
                # 결과 수집
                self.all_results["user_permissions"]["results"] = tester.test_results
                self.all_results["user_permissions"]["summary"] = self.calculate_summary(tester.test_results)
                
                print(f"✅ User Permissions 테스트 완료: {self.all_results['user_permissions']['summary']['success_rate']}% 성공률")
                
        except Exception as e:
            print(f"❌ User Permissions 테스트 실행 중 오류: {str(e)}")
            self.all_results["user_permissions"]["error"] = str(e)
    
    async def run_all_tests(self, user_id: int = 1, user_ids: list = [1, 2]):
        """모든 테스트 실행"""
        print("=" * 100)
        print("🚀 보험설계사 엑셀 업로드 시스템 통합 테스트 시작")
        print("=" * 100)
        
        start_time = time.time()
        self.all_results["test_execution"]["start_time"] = datetime.now().isoformat()
        
        # 1. Excel Upload API 테스트
        await self.run_excel_upload_tests(user_id)
        print()
        
        # 2. Customer Products API 테스트  
        await self.run_customer_products_tests(user_id)
        print()
        
        # 3. User Permissions 테스트
        await self.run_user_permissions_tests(user_ids)
        print()
        
        # 실행 시간 기록
        end_time = time.time()
        duration = end_time - start_time
        self.all_results["test_execution"]["end_time"] = datetime.now().isoformat()
        self.all_results["test_execution"]["total_duration_seconds"] = round(duration, 2)
        
        # 종합 결과 출력
        self.print_comprehensive_summary()
        
        # 결과 저장
        self.save_results()
    
    def print_comprehensive_summary(self):
        """종합 테스트 결과 요약"""
        print("=" * 100)
        print("📊 통합 테스트 결과 종합 요약")
        print("=" * 100)
        
        # 전체 통계
        total_tests = 0
        total_passed = 0
        total_failed = 0
        
        test_categories = [
            ("Excel Upload API", "excel_upload"),
            ("Customer Products API", "customer_products"), 
            ("User Permissions", "user_permissions")
        ]
        
        print("\n📋 카테고리별 결과:")
        print("-" * 60)
        
        for category_name, category_key in test_categories:
            summary = self.all_results[category_key].get("summary", {})
            
            if summary:
                total = summary.get("total", 0)
                passed = summary.get("passed", 0)
                failed = summary.get("failed", 0)
                success_rate = summary.get("success_rate", 0.0)
                
                total_tests += total
                total_passed += passed
                total_failed += failed
                
                status_icon = "✅" if success_rate >= 80 else "⚠️" if success_rate >= 60 else "❌"
                print(f"{status_icon} {category_name:25s}: {passed:3d}/{total:3d} ({success_rate:5.1f}%)")
            else:
                error = self.all_results[category_key].get("error")
                if error:
                    print(f"❌ {category_name:25s}: 실행 오류 - {error}")
                else:
                    print(f"⏭️ {category_name:25s}: 테스트 미실행")
        
        print("-" * 60)
        
        # 전체 요약
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0.0
        overall_status = "✅ 우수" if overall_success_rate >= 80 else "⚠️ 보통" if overall_success_rate >= 60 else "❌ 개선 필요"
        
        print(f"{'전체 결과':25s}: {total_passed:3d}/{total_tests:3d} ({overall_success_rate:5.1f}%) - {overall_status}")
        
        # 실행 시간
        duration = self.all_results["test_execution"]["total_duration_seconds"]
        print(f"\n⏱️ 총 실행 시간: {duration:.2f}초 ({duration/60:.1f}분)")
        
        # 실패한 테스트가 있는 경우 상세 정보
        failed_tests = []
        for category_key in ["excel_upload", "customer_products", "user_permissions"]:
            for result in self.all_results[category_key].get("results", []):
                if not result.get("success", True):
                    failed_tests.append({
                        "category": category_key.replace("_", " ").title(),
                        "test": result.get("test_name", "Unknown"),
                        "message": result.get("message", "No message")
                    })
        
        if failed_tests:
            print(f"\n❌ 실패한 테스트 목록 ({len(failed_tests)}개):")
            print("-" * 80)
            for i, test in enumerate(failed_tests, 1):
                print(f"{i:2d}. [{test['category']}] {test['test']}")
                print(f"    └─ {test['message']}")
        
        # 권장사항
        print(f"\n💡 권장사항:")
        if overall_success_rate >= 90:
            print("   🎉 모든 테스트가 거의 완벽하게 통과했습니다! 시스템이 안정적으로 동작합니다.")
        elif overall_success_rate >= 80:
            print("   👍 대부분의 테스트가 성공했습니다. 몇 가지 개선점을 확인해보세요.")
        elif overall_success_rate >= 60:
            print("   ⚠️ 일부 중요한 기능에 문제가 있을 수 있습니다. 실패한 테스트를 우선 수정하세요.")
        else:
            print("   🚨 심각한 문제가 발견되었습니다. 시스템을 점검하고 핵심 기능부터 수정하세요.")
        
        if failed_tests:
            print("   📝 실패한 테스트의 상세 로그를 확인하여 문제를 해결하세요.")
            print("   🔍 각 테스트 카테고리별 JSON 결과 파일을 참고하세요.")
        
        print("=" * 100)
    
    def save_results(self):
        """테스트 결과를 파일에 저장"""
        # 통합 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        integrated_file = f"integrated_test_results_{timestamp}.json"
        
        with open(integrated_file, 'w', encoding='utf-8') as f:
            json.dump(self.all_results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"📁 통합 테스트 결과가 {integrated_file}에 저장되었습니다.")
        
        # 요약 보고서 생성 (Markdown)
        summary_file = f"test_report_{timestamp}.md"
        self.generate_markdown_report(summary_file)
        
        print(f"📄 테스트 보고서가 {summary_file}에 생성되었습니다.")
    
    def generate_markdown_report(self, filename: str):
        """Markdown 형식 테스트 보고서 생성"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# 보험설계사 엑셀 업로드 시스템 테스트 보고서\n\n")
            f.write(f"**실행 시간**: {self.all_results['test_execution']['start_time']}\n")
            f.write(f"**총 소요 시간**: {self.all_results['test_execution']['total_duration_seconds']}초\n\n")
            
            # 전체 요약
            total_tests = sum(s.get("total", 0) for s in [
                self.all_results["excel_upload"].get("summary", {}),
                self.all_results["customer_products"].get("summary", {}),
                self.all_results["user_permissions"].get("summary", {})
            ])
            total_passed = sum(s.get("passed", 0) for s in [
                self.all_results["excel_upload"].get("summary", {}),
                self.all_results["customer_products"].get("summary", {}),
                self.all_results["user_permissions"].get("summary", {})
            ])
            
            f.write("## 📊 전체 요약\n\n")
            f.write(f"- **총 테스트**: {total_tests}개\n")
            f.write(f"- **성공**: {total_passed}개\n")
            f.write(f"- **실패**: {total_tests - total_passed}개\n")
            f.write(f"- **성공률**: {(total_passed/total_tests*100):.1f}%\n\n")
            
            # 카테고리별 상세
            categories = [
                ("Excel Upload API", "excel_upload"),
                ("Customer Products API", "customer_products"),
                ("User Permissions", "user_permissions")
            ]
            
            for category_name, category_key in categories:
                f.write(f"## 🧪 {category_name}\n\n")
                summary = self.all_results[category_key].get("summary", {})
                
                if summary:
                    f.write(f"- **테스트 수**: {summary['total']}개\n")
                    f.write(f"- **성공**: {summary['passed']}개\n")
                    f.write(f"- **실패**: {summary['failed']}개\n")
                    f.write(f"- **성공률**: {summary['success_rate']}%\n\n")
                    
                    # 실패한 테스트 상세
                    failed_tests = [r for r in self.all_results[category_key].get("results", []) 
                                  if not r.get("success", True)]
                    
                    if failed_tests:
                        f.write("### ❌ 실패한 테스트\n\n")
                        for test in failed_tests:
                            f.write(f"- **{test['test_name']}**: {test['message']}\n")
                        f.write("\n")
                else:
                    f.write("테스트 실행되지 않음\n\n")


async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='보험설계사 엑셀 업로드 시스템 통합 테스트')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API 기본 URL')
    parser.add_argument('--user-id', type=int, default=1, help='주 테스트용 사용자 ID')
    parser.add_argument('--user-ids', nargs='+', type=int, default=[1, 2], help='권한 테스트용 사용자 ID 목록')
    parser.add_argument('--excel-only', action='store_true', help='Excel 업로드 테스트만 실행')
    parser.add_argument('--products-only', action='store_true', help='Customer Products 테스트만 실행')
    parser.add_argument('--permissions-only', action='store_true', help='User Permissions 테스트만 실행')
    
    args = parser.parse_args()
    
    runner = IntegratedTestRunner(args.base_url)
    
    if args.excel_only:
        await runner.run_excel_upload_tests(args.user_id)
    elif args.products_only:
        await runner.run_customer_products_tests(args.user_id)
    elif args.permissions_only:
        await runner.run_user_permissions_tests(args.user_ids)
    else:
        await runner.run_all_tests(args.user_id, args.user_ids)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ 테스트가 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)