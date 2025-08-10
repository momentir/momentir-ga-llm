"""
Test configuration for natural language search testing
"""
import os
from typing import Optional

class TestConfig:
    """Configuration for test environment"""
    
    # Test database configuration
    TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_password@localhost:5433/momentir_test"
    TEST_DATABASE_URL_SYNC = "postgresql://test_user:test_password@localhost:5433/momentir_test"
    
    # Test environment settings
    ENVIRONMENT = "test"
    DEBUG = True
    TESTING = True
    
    # Disable external services during testing
    LANGSMITH_TRACING = "false"
    CLOUDWATCH_ENABLED = False
    
    # Test data settings
    TEST_DATA_SIZE = {
        "customers": 100,
        "products": 50,
        "memos": 200
    }
    
    # Performance test thresholds
    MAX_RESPONSE_TIME = 3.0  # seconds
    MAX_CONCURRENT_REQUESTS = 5
    
    @classmethod
    def override_env_vars(cls):
        """Override environment variables for testing"""
        os.environ["DATABASE_URL"] = cls.TEST_DATABASE_URL
        os.environ["ENVIRONMENT"] = cls.ENVIRONMENT
        os.environ["LANGSMITH_TRACING"] = cls.LANGSMITH_TRACING
        os.environ["DISABLE_KONLPY"] = "true"