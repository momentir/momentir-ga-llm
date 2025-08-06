#!/usr/bin/env python3
"""
전체 테스트 시나리오 실행 스크립트
1. 데이터베이스 마이그레이션 실행
2. 테스트 데이터 생성
3. 테스트용 엑셀 파일 생성  
4. API 테스트 실행
"""

import asyncio
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class FullTestRunner:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.project_root = Path(__file__).parent.parent.parent
        self.db_scripts_dir = Path(__file__).parent  # /tests/excel-upload/db
        self.api_tests_dir = self.db_scripts_dir.parent / "api"  # /tests/excel-upload/api
        
    def run_command(self, command: str, description: str, cwd: str = None) -> bool:
        """명령어 실행 및 결과 반환"""
        print(f"\n🔧 {description}")
        print(f"   실행: {command}")
        
        try:
            if cwd is None:
                cwd = str(self.project_root)
                
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True,
                cwd=cwd,
                env={**os.environ, 'DATABASE_URL': self.database_url} if self.database_url else os.environ
            )
            
            if result.returncode == 0:
                print(f"✅ {description} 성공")
                if result.stdout.strip():
                    print(f"   출력: {result.stdout.strip()[:200]}...")
                return True
            else:
                print(f"❌ {description} 실패")
                if result.stderr:
                    print(f"   오류: {result.stderr.strip()}")
                if result.stdout:
                    print(f"   출력: {result.stdout.strip()}")
                return False
                
        except Exception as e:
            print(f"❌ {description} 실행 중 예외 발생: {str(e)}")
            return False
    
    def check_prerequisites(self) -> bool:
        """전제조건 확인"""
        print("🔍 전제조건 확인 중...")
        
        # DATABASE_URL 확인
        if not self.database_url:
            print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
            print("다음과 같이 설정하세요:")
            print("export DATABASE_URL='postgresql://user:password@host:port/database'")
            return False
        
        print(f"✅ DATABASE_URL: {self.database_url[:50]}...")
        
        # Python 패키지 확인
        required_packages = ['alembic', 'pandas', 'faker', 'aiohttp', 'openpyxl']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package} 패키지 확인")
            except ImportError:
                missing_packages.append(package)
                print(f"❌ {package} 패키지 누락")
        
        if missing_packages:
            print(f"\n다음 패키지를 설치하세요:")
            print(f"pip install {' '.join(missing_packages)}")
            return False
        
        # 필수 파일 확인
        required_files = [
            self.db_scripts_dir / "create_test_data.py",
            self.db_scripts_dir / "create_test_excel_files.py",
            self.api_tests_dir / "run_all_tests.py"
        ]
        
        for file_path in required_files:
            if file_path.exists():
                print(f"✅ {file_path.name} 파일 확인")
            else:
                print(f"❌ {file_path.name} 파일 누락")
                return False
        
        return True
    
    def run_database_migrations(self) -> bool:
        """데이터베이스 마이그레이션 실행"""
        print("\n" + "="*60)
        print("📊 1단계: 데이터베이스 마이그레이션")
        print("="*60)
        
        # 현재 마이그레이션 상태 확인
        success = self.run_command(
            "alembic current",
            "현재 마이그레이션 상태 확인"
        )
        
        if not success:
            return False
        
        # 최신 마이그레이션으로 업그레이드
        success = self.run_command(
            "alembic upgrade head",
            "최신 마이그레이션으로 업그레이드"
        )
        
        return success
    
    def create_test_data(self) -> bool:
        """테스트 데이터 생성"""
        print("\n" + "="*60)
        print("👥 2단계: 테스트 데이터 생성")
        print("="*60)
        
        # 테스트 데이터 생성 스크립트 실행
        success = self.run_command(
            f"python {self.db_scripts_dir}/create_test_data.py",
            "샘플 설계사 및 고객 데이터 생성"
        )
        
        return success
    
    def create_test_excel_files(self) -> bool:
        """테스트용 엑셀 파일 생성"""
        print("\n" + "="*60)
        print("📁 3단계: 테스트용 엑셀 파일 생성")
        print("="*60)
        
        # 엑셀 파일 생성 스크립트 실행
        success = self.run_command(
            f"python {self.db_scripts_dir}/create_test_excel_files.py",
            "다양한 형태의 테스트 엑셀 파일 생성"
        )
        
        return success
    
    def run_api_tests(self) -> bool:
        """API 테스트 실행"""
        print("\n" + "="*60)
        print("🧪 4단계: API 테스트 실행")
        print("="*60)
        
        # API 서버가 실행 중인지 확인
        import aiohttp
        import asyncio
        
        async def check_api_server():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8000/docs', timeout=5) as response:
                        return response.status == 200
            except:
                return False
        
        # API 서버 상태 확인
        server_running = asyncio.run(check_api_server())
        
        if not server_running:
            print("⚠️ API 서버가 실행되지 않고 있습니다.")
            print("   다른 터미널에서 다음 명령을 실행하세요:")
            print("   python -m uvicorn app.main:app --reload")
            print("   또는 서버가 다른 포트에서 실행 중이면 --base-url 옵션을 사용하세요.")
            
            user_input = input("\nAPI 서버가 준비되었으면 'y'를 입력하고 Enter를 누르세요 (건너뛰려면 's'): ")
            if user_input.lower() == 's':
                print("⏭️ API 테스트를 건너뜁니다.")
                return True
            elif user_input.lower() != 'y':
                print("❌ API 테스트를 취소합니다.")
                return False
        
        # 통합 API 테스트 실행
        success = self.run_command(
            f"python {self.api_tests_dir}/run_all_tests.py --user-id 1 --user-ids 1 2",
            "통합 API 테스트 실행"
        )
        
        if success:
            print("\n📊 테스트 결과 파일들이 생성되었습니다:")
            result_files = [
                "integrated_test_results_*.json",
                "test_report_*.md", 
                "excel_upload_test_results.json",
                "customer_products_api_test_results.json",
                "user_permissions_test_results.json"
            ]
            for pattern in result_files:
                print(f"   - {pattern}")
        
        return success
    
    def run_full_scenario(self) -> bool:
        """전체 테스트 시나리오 실행"""
        start_time = datetime.now()
        
        print("🚀" + "="*58 + "🚀")
        print("   보험설계사 엑셀 업로드 시스템 전체 테스트 시나리오")
        print("🚀" + "="*58 + "🚀")
        print(f"시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 전제조건 확인
        if not self.check_prerequisites():
            print("\n❌ 전제조건 확인 실패 - 테스트를 중단합니다.")
            return False
        
        steps = [
            ("데이터베이스 마이그레이션", self.run_database_migrations),
            ("테스트 데이터 생성", self.create_test_data),
            ("테스트용 엑셀 파일 생성", self.create_test_excel_files),
            ("API 테스트 실행", self.run_api_tests)
        ]
        
        success_count = 0
        
        for step_name, step_func in steps:
            try:
                if step_func():
                    success_count += 1
                    print(f"\n✅ {step_name} 완료")
                else:
                    print(f"\n❌ {step_name} 실패")
                    
                    # 실패시 계속할지 물어보기
                    user_input = input(f"\n{step_name}이(가) 실패했습니다. 계속 진행하시겠습니까? (y/n): ")
                    if user_input.lower() != 'y':
                        print("🛑 테스트 시나리오를 중단합니다.")
                        break
                        
            except KeyboardInterrupt:
                print(f"\n🛑 사용자에 의해 {step_name} 중단됨")
                break
            except Exception as e:
                print(f"\n💥 {step_name} 중 예상치 못한 오류 발생: {str(e)}")
                break
        
        # 최종 결과 요약
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "🎉"*60)
        print("전체 테스트 시나리오 완료!")
        print("🎉"*60)
        print(f"완료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"총 소요 시간: {duration.total_seconds():.1f}초")
        print(f"성공한 단계: {success_count}/{len(steps)}")
        
        if success_count == len(steps):
            print("🏆 모든 단계가 성공적으로 완료되었습니다!")
            print("\n다음 파일들을 확인해보세요:")
            print("📁 test_excel_files/ - 생성된 테스트 엑셀 파일들")
            print("📊 *test_results*.json - API 테스트 결과 파일들") 
            print("📄 test_report_*.md - 테스트 보고서")
            return True
        else:
            print("⚠️ 일부 단계가 실패했습니다. 오류 메시지를 확인해주세요.")
            return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='보험설계사 엑셀 업로드 시스템 전체 테스트')
    parser.add_argument('--database-url', help='데이터베이스 연결 URL')
    parser.add_argument('--skip-migrations', action='store_true', help='마이그레이션 단계 건너뛰기')
    parser.add_argument('--skip-data', action='store_true', help='테스트 데이터 생성 건너뛰기')
    parser.add_argument('--skip-excel', action='store_true', help='엑셀 파일 생성 건너뛰기')
    parser.add_argument('--skip-api-tests', action='store_true', help='API 테스트 건너뛰기')
    
    args = parser.parse_args()
    
    # DATABASE_URL 설정
    database_url = args.database_url or os.getenv('DATABASE_URL')
    
    runner = FullTestRunner(database_url)
    
    # 개별 단계 실행 또는 전체 실행
    if any([args.skip_migrations, args.skip_data, args.skip_excel, args.skip_api_tests]):
        print("개별 단계 실행 모드")
        
        if not args.skip_migrations:
            runner.run_database_migrations()
        if not args.skip_data:
            runner.create_test_data()
        if not args.skip_excel:
            runner.create_test_excel_files()
        if not args.skip_api_tests:
            runner.run_api_tests()
    else:
        # 전체 시나리오 실행
        success = runner.run_full_scenario()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 예상치 못한 오류 발생: {str(e)}")
        sys.exit(1)