#!/usr/bin/env python3
"""
테스트 데이터 생성 스크립트
- 샘플 설계사 데이터 (3-5명)
- 각 설계사별 고객 데이터 (10-20명씩)
- 다양한 가입상품 데이터
"""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import random
import os
from faker import Faker

fake = Faker('ko_KR')  # 한국어 faker

class TestDataGenerator:
    def __init__(self, database_url: str = None):
        if not database_url:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL이 설정되지 않았습니다.")
        # postgresql://를 postgresql+asyncpg://로 변경
        if database_url.startswith('postgresql://'):
            self.database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        else:
            self.database_url = database_url
        
        self.engine = create_async_engine(
            self.database_url,
            echo=False
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
    async def create_sample_users(self) -> List[Dict[str, Any]]:
        """샘플 설계사 데이터 생성"""
        users_data = [
            {
                "name": "김민수",
                "email": "minsu.kim@momentir.com",
                "encrypted_password": "hashed_password_1",
                "phone": "010-1234-5678",
                "sign_up_status": "COMPLETED",
                "agreed_marketing_opt_in": True,
                "created_at": datetime.now() - timedelta(days=365),
                "updated_at": datetime.now()
            },
            {
                "name": "이지은",
                "email": "jieun.lee@momentir.com", 
                "encrypted_password": "hashed_password_2",
                "phone": "010-2345-6789",
                "sign_up_status": "COMPLETED",
                "agreed_marketing_opt_in": False,
                "created_at": datetime.now() - timedelta(days=200),
                "updated_at": datetime.now()
            },
            {
                "name": "박철수",
                "email": "cheolsu.park@momentir.com",
                "encrypted_password": "hashed_password_3",
                "phone": "010-3456-7890", 
                "sign_up_status": "COMPLETED",
                "agreed_marketing_opt_in": True,
                "created_at": datetime.now() - timedelta(days=150),
                "updated_at": datetime.now()
            },
            {
                "name": "최영희",
                "email": "younghee.choi@momentir.com",
                "encrypted_password": "hashed_password_4",
                "phone": "010-4567-8901",
                "sign_up_status": "COMPLETED", 
                "agreed_marketing_opt_in": True,
                "created_at": datetime.now() - timedelta(days=100),
                "updated_at": datetime.now()
            },
            {
                "name": "정태호",
                "email": "taeho.jung@momentir.com",
                "encrypted_password": "hashed_password_5",
                "phone": "010-5678-9012",
                "sign_up_status": "COMPLETED",
                "agreed_marketing_opt_in": False,
                "created_at": datetime.now() - timedelta(days=50),
                "updated_at": datetime.now()
            }
        ]
        
        created_users = []
        async with self.async_session() as session:
            try:
                from sqlalchemy import text
                for user_data in users_data:
                    # 이미 존재하는지 확인
                    existing_user = await session.execute(
                        text("SELECT * FROM users WHERE email = :email"),
                        {"email": user_data["email"]}
                    )
                    if existing_user.fetchone():
                        # 기존 사용자 ID 가져오기
                        user_query = await session.execute(
                            text("SELECT id, name, email FROM users WHERE email = :email"),
                            {"email": user_data["email"]}
                        )
                        user_row = user_query.fetchone()
                        created_users.append({
                            "user_id": user_row[0],
                            "name": user_row[1],
                            "email": user_row[2]
                        })
                        print(f"✅ 기존 설계사 사용: {user_row[1]} (ID: {user_row[0]})")
                        continue
                        
                    # 새 사용자 생성
                    insert_query = text("""
                    INSERT INTO users (name, email, encrypted_password, phone, sign_up_status, 
                                     agreed_marketing_opt_in, created_at, updated_at)
                    VALUES (:name, :email, :encrypted_password, :phone, :sign_up_status, 
                            :agreed_marketing_opt_in, :created_at, :updated_at)
                    RETURNING id, name, email
                    """)
                    
                    result = await session.execute(insert_query, user_data)
                    
                    user_row = result.fetchone()
                    if user_row:
                        created_users.append({
                            "user_id": user_row[0],
                            "name": user_row[1],
                            "email": user_row[2]
                        })
                        print(f"✅ 설계사 생성: {user_row[1]} (ID: {user_row[0]})")
                
                await session.commit()
                return created_users
                
            except Exception as e:
                await session.rollback()
                print(f"❌ 설계사 데이터 생성 오류: {str(e)}")
                return []
    
    def generate_customer_data(self, user_id: int, count: int = 15) -> List[Dict[str, Any]]:
        """설계사별 고객 데이터 생성"""
        customers = []
        customer_types = ["가입", "미가입"] 
        contact_channels = ["가족", "지역", "소개", "지역마케팅", "인바운드", "제휴db", "단체계약", "방카", "개척", "기타"]
        
        for i in range(count):
            # 기본 정보 생성
            name = fake.name()
            phone = f"010-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}"
            
            # 주민번호 생성 (마스킹된 형태)
            birth_year = random.randint(50, 99)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            gender_code = random.randint(1, 4)
            resident_number = f"{birth_year:02d}{birth_month:02d}{birth_day:02d}-{gender_code}******"
            
            customer_data = {
                "customer_id": str(uuid.uuid4()),
                "user_id": user_id,
                "name": name,
                "customer_type": random.choice(customer_types),
                "contact_channel": random.choice(contact_channels),
                "phone": phone,
                "resident_number": resident_number,
                "address": fake.address(),
                "job_title": fake.job(),
                "bank_name": random.choice(["국민은행", "우리은행", "신한은행", "하나은행", "기업은행"]),
                "account_number": f"{random.randint(100, 999)}-{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                "referrer": fake.name() if random.random() > 0.7 else None,  # 30% 확률로 소개자
                "notes": fake.text(max_nb_chars=100) if random.random() > 0.8 else None,  # 20% 확률로 기타사항
                "created_at": fake.date_time_between(start_date='-2y', end_date='now'),
                "updated_at": datetime.now()
            }
            customers.append(customer_data)
            
        return customers
    
    def generate_product_data(self, customer_id: str, customer_type: str) -> List[Dict[str, Any]]:
        """고객별 가입상품 데이터 생성"""
        products = []
        
        if customer_type == "미가입":
            return products  # 미가입 고객은 상품 없음
        
        # 가입 고객은 1-3개 상품
        product_count = random.randint(1, 3)
        product_names = [
            "종합보험", "생명보험", "건강보험", "자동차보험", "여행보험", 
            "화재보험", "상해보험", "연금보험", "저축성보험", "태아보험"
        ]
        
        used_products = set()
        
        for i in range(product_count):
            # 중복되지 않는 상품명 선택
            available_products = [p for p in product_names if p not in used_products]
            if not available_products:
                break
                
            product_name = random.choice(available_products)
            used_products.add(product_name)
            
            # 가입일자 생성 (과거 1년 이내)
            subscription_date = fake.date_between(start_date='-1y', end_date='today')
            
            # 종료일/갱신일 (가입일 + 1년)
            expiry_date = subscription_date + timedelta(days=365)
            
            product_data = {
                "product_id": str(uuid.uuid4()),
                "customer_id": customer_id,
                "product_name": product_name,
                "coverage_amount": f"{random.randint(100, 5000):,}만원",
                "subscription_date": subscription_date,
                "expiry_renewal_date": expiry_date,
                "auto_transfer_date": str(random.randint(1, 28)),  # 1-28일 중 선택
                "policy_issued": random.choice([True, False]),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            products.append(product_data)
            
        return products
    
    async def create_customers_and_products(self, users: List[Dict[str, Any]]):
        """고객 및 가입상품 데이터 생성"""
        async with self.async_session() as session:
            try:
                from sqlalchemy import text
                total_customers = 0
                total_products = 0
                
                for user in users:
                    user_id = user["user_id"]
                    user_name = user["name"]
                    
                    # 고객 수 결정 (10-20명)
                    customer_count = random.randint(10, 20)
                    customers_data = self.generate_customer_data(user_id, customer_count)
                    
                    user_customers = 0
                    user_products = 0
                    
                    for customer_data in customers_data:
                        # 고객 생성
                        customer_insert = text("""
                        INSERT INTO customers (
                            customer_id, user_id, name, customer_type, contact_channel,
                            phone, resident_number, address, job_title, bank_name,
                            account_number, referrer, notes, created_at, updated_at
                        ) VALUES (
                            :customer_id, :user_id, :name, :customer_type, :contact_channel,
                            :phone, :resident_number, :address, :job_title, :bank_name,
                            :account_number, :referrer, :notes, :created_at, :updated_at
                        )
                        """)
                        
                        await session.execute(customer_insert, customer_data)
                        user_customers += 1
                        
                        # 가입상품 생성
                        products_data = self.generate_product_data(
                            customer_data["customer_id"], 
                            customer_data["customer_type"]
                        )
                        
                        for product_data in products_data:
                            product_insert = text("""
                            INSERT INTO customer_products (
                                product_id, customer_id, product_name, coverage_amount,
                                subscription_date, expiry_renewal_date, auto_transfer_date,
                                policy_issued, created_at, updated_at
                            ) VALUES (
                                :product_id, :customer_id, :product_name, :coverage_amount,
                                :subscription_date, :expiry_renewal_date, :auto_transfer_date,
                                :policy_issued, :created_at, :updated_at
                            )
                            """)
                            
                            await session.execute(product_insert, product_data)
                            user_products += 1
                    
                    total_customers += user_customers
                    total_products += user_products
                    
                    print(f"✅ {user_name} 설계사: 고객 {user_customers}명, 상품 {user_products}개 생성")
                
                await session.commit()
                print(f"\n🎉 전체 테스트 데이터 생성 완료!")
                print(f"   - 총 고객: {total_customers}명")
                print(f"   - 총 상품: {total_products}개")
                
            except Exception as e:
                await session.rollback()
                print(f"❌ 고객/상품 데이터 생성 오류: {str(e)}")
                raise e
    
    async def generate_all_test_data(self):
        """모든 테스트 데이터 생성"""
        print("=" * 60)
        print("🏗️  테스트 데이터 생성 시작")
        print("=" * 60)
        
        try:
            # 1. 설계사 데이터 생성
            print("\n📋 1단계: 설계사 데이터 생성")
            users = await self.create_sample_users()
            
            if not users:
                print("❌ 설계사 데이터 생성 실패")
                return
            
            # 2. 고객 및 상품 데이터 생성
            print(f"\n👥 2단계: 고객 및 가입상품 데이터 생성 ({len(users)}명 설계사)")
            await self.create_customers_and_products(users)
            
            print("\n✅ 모든 테스트 데이터 생성이 완료되었습니다!")
            
        except Exception as e:
            print(f"\n❌ 테스트 데이터 생성 중 오류 발생: {str(e)}")
        finally:
            await self.engine.dispose()

async def main():
    # 환경변수에서 DATABASE_URL 가져오기
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        print("다음과 같이 설정하세요:")
        print("export DATABASE_URL='postgresql://user:password@host:port/database'")
        return
    
    generator = TestDataGenerator(database_url)
    await generator.generate_all_test_data()

if __name__ == "__main__":
    asyncio.run(main())