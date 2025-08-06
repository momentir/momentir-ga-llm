#!/usr/bin/env python3
"""
테스트용 엑셀 파일 생성 스크립트
다양한 형태의 엑셀 파일을 생성하여 업로드 API 테스트에 사용
"""

import pandas as pd
import os
import random
from datetime import datetime, date, timedelta
from faker import Faker
from pathlib import Path

fake = Faker('ko_KR')

class TestExcelGenerator:
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            # 기본값: /tests/excel-upload/test_excel_files
            # 현재: /tests/excel-upload/db/create_test_excel_files.py
            # 목표: /tests/excel-upload/test_excel_files
            script_dir = Path(__file__).parent  # /tests/excel-upload/db
            output_dir = script_dir.parent / "test_excel_files"  # /tests/excel-upload/test_excel_files
        else:
            output_dir = Path(output_dir)
            
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def create_basic_format_excel(self):
        """기본 형태의 엑셀 파일 생성"""
        print("📊 기본 형태 엑셀 파일 생성 중...")
        
        data = []
        for i in range(20):
            row = {
                "고객명": fake.name(),
                "전화번호": f"010-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                "고객유형": random.choice(["가입", "미가입"]),
                "접점": random.choice(["가족", "지역", "소개", "지역마케팅", "인바운드"]),
                "주소": fake.address(),
                "직업": fake.job(),
                "상품명": random.choice(["종합보험", "생명보험", "건강보험", "자동차보험"]),
                "가입금액": f"{random.randint(100, 2000):,}만원",
                "가입일자": fake.date_between(start_date='-1y', end_date='today').strftime('%Y-%m-%d'),
                "증권교부": random.choice(["Y", "N"])
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "01_기본형태.xlsx"
        df.to_excel(filepath, index=False, sheet_name='고객데이터')
        print(f"✅ {filepath} 생성 완료")
        
    def create_complex_mapping_excel(self):
        """복잡한 컬럼명 매핑이 필요한 엑셀 파일 생성"""
        print("🔀 복잡한 컬럼 매핑 엑셀 파일 생성 중...")
        
        data = []
        for i in range(15):
            row = {
                "성명": fake.name(),  # name 매핑
                "핸드폰": f"010{random.randint(10000000, 99999999):08d}",  # phone 매핑 (하이픈 없음)
                "분류": "가입고객" if random.random() > 0.3 else "미가입고객",  # customer_type 매핑
                "경로": random.choice(["가족추천", "지역활동", "소개받음", "마케팅", "인바운드콜"]),  # contact_channel 매핑
                "거주지": fake.address(),  # address 매핑
                "직장": fake.company(),  # job_title 매핑
                "주민등록번호": f"{random.randint(800101, 991231):06d}-{random.randint(1, 4):01d}******",  # resident_number 매핑
                "보험상품": random.choice(["종합보장보험", "건강플랜", "자동차종합", "여행자보험"]),  # product_name 매핑
                "보장액": f"{random.randint(200, 5000)}만원",  # coverage_amount 매핑
                "계약일": fake.date_between(start_date='-2y', end_date='today').strftime('%Y/%m/%d'),  # subscription_date 매핑
                "증권발급": "완료" if random.random() > 0.4 else "미발급"  # policy_issued 매핑
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "02_복잡한컬럼매핑.xlsx"
        df.to_excel(filepath, index=False, sheet_name='보험고객')
        print(f"✅ {filepath} 생성 완료")
        
    def create_multiple_products_per_customer_excel(self):
        """고객당 여러 상품이 있는 엑셀 파일 생성"""
        print("👥 고객당 여러 상품 엑셀 파일 생성 중...")
        
        data = []
        customers = []
        
        # 5명의 고객 생성
        for i in range(5):
            customer = {
                "name": fake.name(),
                "phone": f"010-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                "address": fake.address(),
                "job": fake.job()
            }
            customers.append(customer)
        
        # 각 고객에 대해 2-4개의 상품 생성
        products = ["생명보험", "건강보험", "자동차보험", "여행보험", "화재보험"]
        
        for customer in customers:
            product_count = random.randint(2, 4)
            selected_products = random.sample(products, product_count)
            
            for product in selected_products:
                row = {
                    "고객명": customer["name"],
                    "전화번호": customer["phone"],
                    "고객유형": "가입",
                    "주소": customer["address"],
                    "직업": customer["job"],
                    "상품명": product,
                    "가입금액": f"{random.randint(300, 3000):,}만원",
                    "가입일자": fake.date_between(start_date='-1y', end_date='today').strftime('%Y-%m-%d'),
                    "자동이체일": str(random.randint(1, 28)),
                    "증권교부": random.choice(["Y", "N"])
                }
                data.append(row)
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "03_고객당여러상품.xlsx"
        df.to_excel(filepath, index=False, sheet_name='고객상품데이터')
        print(f"✅ {filepath} 생성 완료 (총 {len(data)}행)")
        
    def create_data_validation_test_excel(self):
        """데이터 검증 테스트용 엑셀 파일 생성"""
        print("🔍 데이터 검증 테스트 엑셀 파일 생성 중...")
        
        data = [
            {
                "고객명": "홍길동",
                "전화번호": "01012345678",  # 하이픈 없는 번호
                "주민번호": "8501011234567",  # 마스킹 필요
                "고객유형": "가입",
                "가입일자": "2024/01/15",  # 슬래시 형식 날짜
                "증권교부": "예",  # 한글 불린값
                "상품명": "종합보험"
            },
            {
                "고객명": "김영희", 
                "전화번호": "010-9876-5432",  # 정상 형식
                "주민번호": "920315-2******",  # 이미 마스킹됨
                "고객유형": "미가입",
                "가입일자": "2024-02-20",  # 하이픈 형식 날짜
                "증권교부": "아니오",  # 한글 불린값
                "상품명": ""  # 빈 값
            },
            {
                "고객명": "이철수",
                "전화번호": "010.1111.2222",  # 점 구분자
                "주민번호": "",  # 빈 값
                "고객유형": "가입고객",  # 다른 형태
                "가입일자": "24/03/10",  # 짧은 년도
                "증권교부": "O",  # O/X 형태
                "상품명": "건강보험"
            }
        ]
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "04_데이터검증테스트.xlsx"
        df.to_excel(filepath, index=False, sheet_name='검증테스트')
        print(f"✅ {filepath} 생성 완료")
        
    def create_large_file_excel(self, row_count: int = 1000):
        """대용량 파일 테스트용 엑셀 생성"""
        print(f"📈 대용량 파일 테스트 엑셀 생성 중... ({row_count:,}행)")
        
        data = []
        for i in range(row_count):
            row = {
                "고객명": fake.name(),
                "전화번호": f"010-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                "고객유형": random.choice(["가입", "미가입"]),
                "접점": random.choice(["가족", "지역", "소개", "지역마케팅", "인바운드", "제휴db"]),
                "주소": fake.address(),
                "직업": fake.job(),
                "상품명": random.choice([
                    "종합보험", "생명보험", "건강보험", "자동차보험", "여행보험", 
                    "화재보험", "상해보험", "연금보험", "저축성보험"
                ]),
                "가입금액": f"{random.randint(100, 5000):,}만원",
                "가입일자": fake.date_between(start_date='-2y', end_date='today').strftime('%Y-%m-%d'),
                "자동이체일": str(random.randint(1, 28)),
                "증권교부": random.choice(["Y", "N"])
            }
            data.append(row)
            
            # 진행상황 표시
            if (i + 1) % 100 == 0:
                print(f"   진행률: {i+1:,}/{row_count:,} ({(i+1)/row_count*100:.1f}%)")
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / f"05_대용량파일_{row_count}행.xlsx"
        
        print("   파일 저장 중...")
        df.to_excel(filepath, index=False, sheet_name='대용량데이터')
        
        # 파일 크기 확인
        file_size = filepath.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ {filepath} 생성 완료 (크기: {file_size:.2f}MB)")
        
    def create_mixed_format_excel(self):
        """다양한 형식이 혼재된 엑셀 파일 생성"""
        print("🎭 다양한 형식 혼재 엑셀 파일 생성 중...")
        
        data = []
        
        # 의도적으로 다양한 형식 혼용
        formats = {
            "phone": [
                "010-1234-5678",  # 표준 형식
                "01012345678",    # 하이픈 없음
                "010.1234.5678",  # 점 구분
                "010 1234 5678"   # 공백 구분
            ],
            "date": [
                "2024-01-15",     # ISO 형식
                "2024/01/15",     # 슬래시 형식
                "24-01-15",       # 짧은 년도
                "2024.01.15"      # 점 구분
            ],
            "boolean": [
                "Y", "N",         # Y/N
                "예", "아니오",    # 한글
                "O", "X",         # O/X
                "TRUE", "FALSE"   # 영어
            ],
            "customer_type": [
                "가입", "미가입",
                "가입고객", "미가입고객",
                "기존고객", "신규고객"
            ]
        }
        
        for i in range(30):
            row = {
                "고객명": fake.name(),
                "전화번호": random.choice(formats["phone"]),
                "고객유형": random.choice(formats["customer_type"]),
                "주소": fake.address(),
                "상품명": random.choice(["종합보험", "생명보험", "건강보험", "자동차보험"]),
                "가입일자": random.choice(formats["date"]),
                "증권교부": random.choice(formats["boolean"]),
                "가입금액": f"{random.randint(100, 3000)}만원"
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "06_혼합형식.xlsx"
        df.to_excel(filepath, index=False, sheet_name='혼합형식데이터')
        print(f"✅ {filepath} 생성 완료")
        
    def create_error_scenario_files(self):
        """오류 시나리오 테스트용 파일들 생성"""
        print("⚠️ 오류 시나리오 테스트 파일들 생성 중...")
        
        # 1. 빈 엑셀 파일
        empty_df = pd.DataFrame()
        empty_filepath = self.output_dir / "07_빈파일.xlsx"
        empty_df.to_excel(empty_filepath, index=False)
        print(f"✅ {empty_filepath} 생성 완료 (빈 파일)")
        
        # 2. 헤더만 있는 파일
        header_only_df = pd.DataFrame(columns=["고객명", "전화번호", "상품명"])
        header_filepath = self.output_dir / "08_헤더만.xlsx"
        header_only_df.to_excel(header_filepath, index=False)
        print(f"✅ {header_filepath} 생성 완료 (헤더만)")
        
        # 3. 잘못된 텍스트 파일 (CSV가 아닌)
        text_filepath = self.output_dir / "09_잘못된형식.txt"
        with open(text_filepath, 'w', encoding='utf-8') as f:
            f.write("이것은 엑셀 파일이 아닙니다.")
        print(f"✅ {text_filepath} 생성 완료 (잘못된 형식)")
        
    def create_realistic_scenario_excel(self):
        """실제 시나리오를 반영한 종합 엑셀 파일"""
        print("🎯 실제 시나리오 종합 엑셀 파일 생성 중...")
        
        # 실제 보험업계에서 사용할 만한 데이터
        data = []
        
        # 실제 보험상품명들
        real_products = [
            "무배당 라이나 건강보험", "삼성화재 자동차보험", "현대해상 여행보험",
            "KB손해보험 종합보험", "메리츠화재 실버보험", "한화손보 펫보험",
            "DB손해보험 치아보험", "롯데손보 운전자보험", "AIG생명 연금보험"
        ]
        
        # 실제 직업군들
        real_jobs = [
            "회사원", "공무원", "자영업자", "교사", "의사", "변호사", "엔지니어",
            "간호사", "요리사", "디자이너", "프로그래머", "경영자", "연구원"
        ]
        
        # 실제 은행명들
        real_banks = [
            "국민은행", "신한은행", "우리은행", "하나은행", "기업은행",
            "농협은행", "새마을금고", "신협", "우체국", "씨티은행"
        ]
        
        for i in range(50):
            # 주민번호 생성 (실제같이)
            birth_year = random.randint(60, 99)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            gender_code = random.randint(1, 4)
            resident_number = f"{birth_year:02d}{birth_month:02d}{birth_day:02d}-{gender_code}******"
            
            row = {
                "고객명": fake.name(),
                "전화번호": f"010-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                "주민등록번호": resident_number,
                "고객유형": "기존고객" if random.random() > 0.2 else "신규고객",
                "고객접점": random.choice(["지인소개", "온라인", "전화상담", "방문상담", "행사참여"]),
                "주소": fake.address(),
                "직업": random.choice(real_jobs),
                "계좌은행": random.choice(real_banks),
                "계좌번호": f"{random.randint(100, 999)}-{random.randint(100000, 999999)}-{random.randint(100, 999)}",
                "소개자": fake.name() if random.random() > 0.6 else "",
                "상품명": random.choice(real_products),
                "가입금액": f"{random.randint(100, 10000):,}만원",
                "가입일자": fake.date_between(start_date='-2y', end_date='today').strftime('%Y-%m-%d'),
                "만료일": (fake.date_between(start_date='today', end_date='+2y')).strftime('%Y-%m-%d'),
                "자동이체일": str(random.randint(1, 28)),
                "증권교부여부": "교부완료" if random.random() > 0.3 else "미교부",
                "비고": fake.text(max_nb_chars=50) if random.random() > 0.8 else ""
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        filepath = self.output_dir / "10_실제시나리오_종합.xlsx"
        df.to_excel(filepath, index=False, sheet_name='고객관리')
        print(f"✅ {filepath} 생성 완료")
        
    def generate_all_test_files(self):
        """모든 테스트 엑셀 파일 생성"""
        print("=" * 60)
        print("📁 테스트용 엑셀 파일 생성 시작")
        print("=" * 60)
        print(f"출력 디렉토리: {self.output_dir.absolute()}")
        print()
        
        try:
            # 각종 테스트 파일 생성
            self.create_basic_format_excel()
            self.create_complex_mapping_excel()
            self.create_multiple_products_per_customer_excel()
            self.create_data_validation_test_excel()
            self.create_large_file_excel(1000)  # 1000행
            self.create_mixed_format_excel()
            self.create_error_scenario_files()
            self.create_realistic_scenario_excel()
            
            print()
            print("=" * 60)
            print("✅ 모든 테스트 엑셀 파일 생성 완료!")
            print("=" * 60)
            
            # 생성된 파일 목록 출력
            files = list(self.output_dir.glob("*.xlsx")) + list(self.output_dir.glob("*.txt"))
            print(f"\n📋 생성된 파일 목록 ({len(files)}개):")
            for i, file in enumerate(sorted(files), 1):
                file_size = file.stat().st_size / 1024  # KB
                if file_size > 1024:
                    size_str = f"{file_size/1024:.2f}MB"
                else:
                    size_str = f"{file_size:.1f}KB"
                print(f"  {i:2d}. {file.name} ({size_str})")
                
        except Exception as e:
            print(f"❌ 엑셀 파일 생성 중 오류 발생: {str(e)}")

def main():
    generator = TestExcelGenerator("../../../scripts/test_excel_files")
    generator.generate_all_test_files()

if __name__ == "__main__":
    main()