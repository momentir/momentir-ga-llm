"""
pytest 전역 설정 및 픽스처
"""
import pytest
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 테스트 환경 변수 설정
os.environ["TESTING"] = "true"
os.environ["SQL_ECHO"] = "false"  # 테스트 중에는 SQL 로그 비활성화

@pytest.fixture(scope="session")
def anyio_backend():
    """async 테스트를 위한 anyio 백엔드 설정"""
    return "asyncio"

@pytest.fixture(autouse=True)
def setup_test_env():
    """모든 테스트 실행 전에 환경 설정"""
    # 테스트용 환경 변수 설정
    os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_momentir.db"
    yield
    # 테스트 후 정리 (필요시)