import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from typing import AsyncGenerator
import logging
import asyncio
import json

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


class ReadOnlyDatabaseManager:
    def __init__(self):
        # 읽기 전용 데이터베이스 URL 가져오기
        self.read_only_database_url = os.getenv("READ_ONLY_DATABASE_URL")
        
        # 읽기 전용 URL이 없으면 기본 URL을 사용하되 읽기 전용 사용자로 변경
        if not self.read_only_database_url:
            base_url = os.getenv("DATABASE_URL")
            if not base_url:
                raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
            
            # 기본 URL에서 읽기 전용 사용자로 변경 (예: dbadmin -> dbreader)
            if "dbadmin" in base_url:
                self.read_only_database_url = base_url.replace("dbadmin", "dbreader")
            else:
                # 읽기 전용 사용자가 없으면 기본 URL 사용 (개발환경)
                self.read_only_database_url = base_url
                logger.warning("읽기 전용 데이터베이스 사용자가 설정되지 않았습니다. 기본 연결을 사용합니다.")
        
        # PostgreSQL URL을 asyncpg용으로 변환
        if self.read_only_database_url.startswith("postgresql://"):
            self.read_only_database_url = self.read_only_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        print(f"🗄️  읽기 전용 PostgreSQL 연결: {self.read_only_database_url.split('@')[1] if '@' in self.read_only_database_url else 'localhost'}")
        
        # 읽기 전용 엔진 생성 (타임아웃 5초, 작은 풀 사이즈)
        self.engine = create_async_engine(
            self.read_only_database_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            pool_size=3,  # 읽기 전용이므로 작은 풀 사이즈
            max_overflow=5,
            pool_timeout=5,  # 5초 타임아웃
            pool_recycle=3600,  # 1시간마다 연결 재활용
            connect_args={
                "server_settings": {
                    "application_name": "momentir-readonly",
                    "statement_timeout": "5000",  # 5초 타임아웃
                }
            }
        )
        
        # 읽기 전용 세션 메이커
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 읽기 전용 세션에서는 이벤트 리스너 대신 트랜잭션 수준에서 제어
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """비동기 읽기 전용 데이터베이스 세션 생성"""
        async with self.async_session_maker() as session:
            try:
                # 읽기 전용 트랜잭션으로 설정
                await session.execute(text("SET TRANSACTION READ ONLY"))
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def execute_query_with_limit(self, query: str, params: dict = None, limit: int = 1000) -> list:
        """
        읽기 전용 쿼리를 실행하고 최대 1000행으로 제한
        
        Args:
            query: 실행할 SQL 쿼리
            params: 쿼리 파라미터
            limit: 최대 결과 행 수 (기본값: 1000)
        
        Returns:
            쿼리 결과 리스트
        """
        if limit > 100:
            limit = 100
            logger.warning("쿼리 결과는 최대 100행으로 제한됩니다.")
        
        # LIMIT 절이 없으면 추가
        query_upper = query.upper()
        if "LIMIT" not in query_upper:
            # 세미콜론 제거 후 LIMIT 추가
            query = query.rstrip(';').rstrip()
            query = f"{query} LIMIT {limit}"

        # 🔎 최종 실행 SQL 로깅 (LIMIT 등 후처리 반영된 상태)
        final_sql = query
        logger.info("🧾 FINAL SQL (effective) ▼\n%s\n-- params: %s",final_sql, json.dumps(params or {}, ensure_ascii=False))
        
        async for session in self.get_session():
            try:
                # 타임아웃 설정으로 쿼리 실행
                result = await asyncio.wait_for(
                    session.execute(text(query), params or {}),
                    timeout=5.0
                )
                return result.fetchall()
            except asyncio.TimeoutError:
                logger.error("쿼리 실행 시간이 5초를 초과했습니다.")
                raise RuntimeError("쿼리 타임아웃: 5초 이내에 완료되지 않았습니다.")
            except Exception as e:
                logger.error(f"읽기 전용 쿼리 실행 중 오류 발생: {e}")
                raise

    async def close(self):
        """읽기 전용 데이터베이스 연결 종료"""
        await self.engine.dispose()


# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()
read_only_db_manager = ReadOnlyDatabaseManager()


# FastAPI dependencies
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session


async def get_read_only_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in read_only_db_manager.get_session():
        yield session