#!/usr/bin/env python3
"""
간단한 프롬프트 생성 테스트
"""
import asyncio
import os
import sys
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.prompt_service import PromptService
from app.models.prompt_models import PromptTemplateCreate, PromptCategory

# 환경변수에서 데이터베이스 URL 가져오기
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dbadmin:5JYbqQeiuQI7tYNaDoFAnp0oL@momentir-cx.ctacoom6szjg.ap-northeast-2.rds.amazonaws.com:5432/momentir-cx-llm")

# PostgreSQL URL을 AsyncPG 형식으로 변환
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 데이터베이스 엔진 생성
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_prompt_creation():
    """간단한 프롬프트 생성 테스트"""
    async with AsyncSessionLocal() as db:
        service = PromptService(db)
        
        # 테스트 프롬프트 생성
        template_request = PromptTemplateCreate(
            name="테스트 프롬프트",
            description="간단한 테스트용 프롬프트", 
            category=PromptCategory.MEMO_REFINE,
            template_content="안녕하세요 {{ name }}님!",
            variables={"name": "사용자 이름"},
            created_by="test"
        )
        
        try:
            template = await service.create_template(template_request)
            print(f"✅ 테스트 프롬프트 생성 성공: {template.id}")
            print(f"   생성일: {template.created_at}")
            print(f"   수정일: {template.updated_at}")
            
        except Exception as e:
            print(f"❌ 테스트 프롬프트 생성 실패: {e}")
        
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_prompt_creation())