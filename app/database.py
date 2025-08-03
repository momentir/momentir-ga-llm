import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self):
        # PostgreSQL 데이터베이스 URL 가져오기
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
        
        # PostgreSQL URL을 asyncpg용으로 변환
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        print(f"🗄️  PostgreSQL 데이터베이스 연결: {self.database_url.split('@')[1] if '@' in self.database_url else 'localhost'}")
        
        self.engine = create_async_engine(
            self.database_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # SQL 로그 표시 여부
            pool_size=10,
            max_overflow=20
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """비동기 데이터베이스 세션 생성"""
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def init_db(self):
        """데이터베이스 초기화 및 pgvector 확장 설치"""
        async with self.engine.begin() as conn:
            # pgvector 확장 설치 (PostgreSQL용)
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            
            # 테이블 생성 (개발 환경에서만)
            # 프로덕션에서는 Alembic 마이그레이션 사용
            if os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true":
                await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """데이터베이스 연결 종료"""
        await self.engine.dispose()


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()


# FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session