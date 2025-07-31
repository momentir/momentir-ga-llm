import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from typing import AsyncGenerator


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self):
        # Mock 모드 체크
        use_mock_mode = os.getenv("USE_MOCK_MODE", "false").lower() == "true"
        
        if use_mock_mode:
            # SQLite 사용 (Mock 모드)
            self.database_url = os.getenv("MOCK_DATABASE_URL", "sqlite+aiosqlite:///./dev_memo.db")
            print("🗄️  Mock 모드: SQLite 데이터베이스 사용")
            
            self.engine = create_async_engine(
                self.database_url,
                echo=True,  # 개발용이므로 SQL 로그 표시
                connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
            )
        else:
            # PostgreSQL 사용 (프로덕션 모드)
            self.database_url = os.getenv("DATABASE_URL")
            if not self.database_url:
                raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
            
            # PostgreSQL URL을 asyncpg용으로 변환
            if self.database_url.startswith("postgresql://"):
                self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
            self.engine = create_async_engine(
                self.database_url,
                echo=False,  # 개발 시에는 True로 설정하여 SQL 로그 확인
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
            # Mock 모드가 아닐 때만 pgvector 확장 설치
            use_mock_mode = os.getenv("USE_MOCK_MODE", "false").lower() == "true"
            if not use_mock_mode:
                # pgvector 확장 설치 (PostgreSQL용)
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            
            # 테이블 생성
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