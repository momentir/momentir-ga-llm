"""
LLM 클라이언트 통합 관리 - 싱글톤 패턴으로 중복 호출 방지
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, ChatOpenAI, AzureOpenAIEmbeddings, OpenAIEmbeddings
from app.utils.langsmith_config import langsmith_manager

# 환경변수 로드
load_dotenv()

logger = logging.getLogger(__name__)


class LLMClientManager:
    """LLM 클라이언트를 통합 관리하는 싱글톤 클래스"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        # 초기화 상태 설정
        self._initialized = True
        
        # 클라이언트들 초기화
        self.chat_client: Optional[AzureChatOpenAI | ChatOpenAI] = None
        self.embedding_client: Optional[AzureOpenAIEmbeddings | OpenAIEmbeddings] = None
        
        # Azure vs OpenAI 설정 확인
        self.api_type = os.getenv("OPENAI_API_TYPE", "openai")
        
        # 클라이언트 초기화
        self._init_chat_client()
        self._init_embedding_client()
        
        logger.info(f"✅ LLMClientManager 싱글톤 초기화 완료 ({self.api_type})")
    
    def _init_chat_client(self):
        """Chat 클라이언트 초기화 (Azure 또는 OpenAI)"""
        try:
            if self.api_type == "azure":
                self.chat_client = AzureChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                    deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4"),
                    callbacks=langsmith_manager.get_callbacks(),
                    temperature=0.1,
                    max_tokens=1000
                )
                self.chat_model_name = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4")
                logger.info(f"✅ Azure Chat 클라이언트 초기화: {self.chat_model_name}")
            else:
                self.chat_client = ChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model="gpt-4",
                    callbacks=langsmith_manager.get_callbacks(),
                    temperature=0.1,
                    max_tokens=1000
                )
                self.chat_model_name = "gpt-4"
                logger.info("✅ OpenAI Chat 클라이언트 초기화: gpt-4")
                
        except Exception as e:
            logger.error(f"❌ Chat 클라이언트 초기화 실패: {e}")
            self.chat_client = None
    
    def _init_embedding_client(self):
        """Embedding 클라이언트 초기화 (Azure 또는 OpenAI)"""
        try:
            if self.api_type == "azure":
                # Azure 임베딩 전용 리소스 설정 확인
                embedding_endpoint = os.getenv("AZURE_EMBEDDING_ENDPOINT")
                embedding_api_key = os.getenv("AZURE_EMBEDDING_API_KEY")
                
                if embedding_endpoint and embedding_api_key:
                    self.embedding_client = AzureOpenAIEmbeddings(
                        api_key=embedding_api_key,
                        azure_endpoint=embedding_endpoint,
                        api_version=os.getenv("AZURE_EMBEDDING_API_VERSION", "2024-02-01"),
                        deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
                    )
                    self.embedding_model_name = os.getenv("AZURE_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
                    logger.info(f"✅ Azure Embedding 클라이언트 초기화: {self.embedding_model_name}")
                else:
                    logger.warning("⚠️  Azure 임베딩 전용 리소스 설정이 없습니다.")
                    self.embedding_client = None
                    self.embedding_model_name = None
            else:
                self.embedding_client = OpenAIEmbeddings(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model="text-embedding-ada-002"
                )
                self.embedding_model_name = "text-embedding-ada-002"
                logger.info("✅ OpenAI Embedding 클라이언트 초기화: text-embedding-ada-002")
                
        except Exception as e:
            logger.error(f"❌ Embedding 클라이언트 초기화 실패: {e}")
            self.embedding_client = None
    
    def get_chat_client(self) -> Optional[AzureChatOpenAI | ChatOpenAI]:
        """Chat 클라이언트 반환"""
        return self.chat_client
    
    def get_embedding_client(self) -> Optional[AzureOpenAIEmbeddings | OpenAIEmbeddings]:
        """Embedding 클라이언트 반환"""
        return self.embedding_client
    
    def get_chat_model_name(self) -> str:
        """Chat 모델명 반환"""
        return getattr(self, 'chat_model_name', 'gpt-4')
    
    def get_embedding_model_name(self) -> str:
        """Embedding 모델명 반환"""
        return getattr(self, 'embedding_model_name', 'text-embedding-ada-002')
    
    def is_ready(self) -> bool:
        """클라이언트들이 준비되었는지 확인"""
        return self.chat_client is not None
    
    def is_embedding_ready(self) -> bool:
        """Embedding 클라이언트가 준비되었는지 확인"""
        return self.embedding_client is not None


# 전역 싱글톤 인스턴스
llm_client_manager = LLMClientManager()