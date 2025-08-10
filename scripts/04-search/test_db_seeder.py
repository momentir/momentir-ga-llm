#!/usr/bin/env python3
"""
Test database seeding utility
Creates realistic test data for natural language search testing
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List
import uuid
import random
from faker import Faker

# Add the parent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config.test_config import TestConfig
from app.db_models.main_models import Customer, CustomerProduct, CustomerMemo
from app.db_models.auth_models import User
from app.database import Base

fake = Faker('ko_KR')  # Korean locale for realistic names

class TestDataSeeder:
    """Seeds test database with realistic data"""
    
    def __init__(self):
        TestConfig.override_env_vars()
        self.engine = create_async_engine(
            TestConfig.TEST_DATABASE_URL,
            echo=False
        )
        self.AsyncSessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def create_tables(self):
        """Create all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    
    async def seed_users(self) -> List[User]:
        """Create test users"""
        users = []
        async with self.AsyncSessionLocal() as session:
            for i in range(5):
                user = User(
                    email=f"agent{i+1}@test.com",
                    full_name=fake.name(),
                    is_active=True
                )
                users.append(user)
                session.add(user)
            
            await session.commit()
            await session.refresh(users[0])  # Refresh to get IDs
        
        print(f"✅ Created {len(users)} test users")
        return users
    
    async def seed_customers(self, users: List[User]) -> List[Customer]:
        """Create test customers with varied profiles"""
        customers = []
        
        # Predefined test customers for specific scenarios
        test_scenarios = [
            {
                "name": "홍길동",
                "gender": "남성",
                "customer_type": "가입",
                "contact_channel": "지역",
                "phone": "010-1234-5678",
                "job_title": "회사원"
            },
            {
                "name": "김영희",
                "gender": "여성", 
                "customer_type": "가입",
                "contact_channel": "소개",
                "phone": "010-9876-5432",
                "job_title": "교사"
            },
            {
                "name": "박철수",
                "gender": "남성",
                "customer_type": "미가입",
                "contact_channel": "인바운드",
                "phone": "010-5555-1234",
                "job_title": "의사"
            },
            {
                "name": "이미영",
                "gender": "여성",
                "customer_type": "가입",
                "contact_channel": "제휴db",
                "phone": "010-7777-8888",
                "job_title": "간호사"
            }
        ]
        
        async with self.AsyncSessionLocal() as session:
            # Create scenario customers
            for scenario in test_scenarios:
                customer = Customer(
                    user_id=random.choice(users).id,
                    name=scenario["name"],
                    gender=scenario["gender"],
                    customer_type=scenario["customer_type"],
                    contact_channel=scenario["contact_channel"],
                    phone=scenario["phone"],
                    job_title=scenario["job_title"],
                    date_of_birth=fake.date_of_birth(minimum_age=25, maximum_age=65),
                    address=fake.address(),
                    created_at=datetime.now() - timedelta(days=random.randint(1, 365))
                )
                customers.append(customer)
                session.add(customer)
            
            # Create additional random customers
            for i in range(TestConfig.TEST_DATA_SIZE["customers"] - len(test_scenarios)):
                customer = Customer(
                    user_id=random.choice(users).id,
                    name=fake.name(),
                    gender=random.choice(["남성", "여성"]),
                    customer_type=random.choice(["가입", "미가입"]),
                    contact_channel=random.choice(["가족", "지역", "소개", "지역마케팅", "인바운드", "제휴db", "단체계약"]),
                    phone=fake.phone_number(),
                    date_of_birth=fake.date_of_birth(minimum_age=20, maximum_age=70),
                    address=fake.address(),
                    job_title=random.choice(["회사원", "자영업", "교사", "의사", "간호사", "공무원", "주부"]),
                    created_at=datetime.now() - timedelta(days=random.randint(1, 730))
                )
                customers.append(customer)
                session.add(customer)
            
            await session.commit()
        
        print(f"✅ Created {len(customers)} test customers")
        return customers
    
    async def seed_products(self, customers: List[Customer]) -> List[CustomerProduct]:
        """Create customer insurance products"""
        products = []
        
        insurance_products = [
            "화재보험", "자동차보험", "건강보험", "생명보험", "종신보험",
            "의료실비보험", "암보험", "치아보험", "여행보험", "펜션보험"
        ]
        
        async with self.AsyncSessionLocal() as session:
            for customer in customers[:TestConfig.TEST_DATA_SIZE["products"]]:
                # Some customers have multiple products
                num_products = random.randint(1, 3)
                
                for _ in range(num_products):
                    # Create expiring products for "만기 고객" test scenario
                    if random.random() < 0.1:  # 10% chance of expiring this month
                        expiry_date = datetime.now() + timedelta(days=random.randint(1, 30))
                    else:
                        expiry_date = fake.date_between(
                            start_date=datetime.now() + timedelta(days=30),
                            end_date=datetime.now() + timedelta(days=1095)
                        )
                    
                    product = CustomerProduct(
                        customer_id=customer.customer_id,
                        product_name=random.choice(insurance_products),
                        coverage_amount=f"{random.randint(1000, 50000)}만원",
                        subscription_date=fake.date_between(
                            start_date=customer.created_at,
                            end_date=datetime.now()
                        ),
                        expiry_renewal_date=expiry_date,
                        auto_transfer_date=str(random.randint(1, 28)),
                        policy_issued=random.choice([True, False])
                    )
                    products.append(product)
                    session.add(product)
            
            await session.commit()
        
        print(f"✅ Created {len(products)} insurance products")
        return products
    
    async def seed_memos(self, customers: List[Customer]) -> List[CustomerMemo]:
        """Create customer memos"""
        memos = []
        
        memo_templates = [
            "고객 상담 완료. 보험 가입 검토 중",
            "전화 상담 진행. 추가 문의 예정",
            "보험료 납입 지연 상담",
            "보험금 청구 접수 완료",
            "계약 갱신 안내 완료",
            "신규 상품 안내 및 상담",
            "고객 불만 접수 및 처리",
            "보험료 인상 안내 상담"
        ]
        
        async with self.AsyncSessionLocal() as session:
            for i in range(TestConfig.TEST_DATA_SIZE["memos"]):
                customer = random.choice(customers)
                memo = CustomerMemo(
                    customer_id=customer.customer_id,
                    original_memo=random.choice(memo_templates),
                    status="confirmed",
                    author=f"상담원{random.randint(1, 10)}",
                    created_at=datetime.now() - timedelta(days=random.randint(0, 365))
                )
                memos.append(memo)
                session.add(memo)
            
            await session.commit()
        
        print(f"✅ Created {len(memos)} customer memos")
        return memos
    
    async def seed_all(self):
        """Seed entire test database"""
        print("🌱 Starting test database seeding...")
        
        await self.create_tables()
        users = await self.seed_users()
        customers = await self.seed_customers(users)
        await self.seed_products(customers)
        await self.seed_memos(customers)
        
        print("🎉 Test database seeding completed!")
    
    async def cleanup(self):
        """Cleanup database connections"""
        await self.engine.dispose()

async def main():
    """Main seeding function"""
    seeder = TestDataSeeder()
    try:
        await seeder.seed_all()
    finally:
        await seeder.cleanup()

if __name__ == "__main__":
    asyncio.run(main())