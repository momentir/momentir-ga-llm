import os
from typing import Optional
from functools import wraps
from langsmith import Client
from langchain_core.tracers.langchain import LangChainTracer
from langchain_openai import AzureChatOpenAI, ChatOpenAI
import logging

logger = logging.getLogger(__name__)

class LangSmithManager:
    """LangSmith 추적 관리자"""
    
    def __init__(self):
        self.enabled = False
        self.client: Optional[Client] = None
        self.tracer: Optional[LangChainTracer] = None
        self.project_name = os.getenv("LANGSMITH_PROJECT", "momentir-cx-llm")
        self.llm_client = None
        
        self._initialize()
    
    def _initialize(self):
        """LangSmith 초기화"""
        api_key = os.getenv("LANGSMITH_API_KEY")
        tracing_enabled = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        
        if api_key and api_key != "your-langsmith-api-key-here" and tracing_enabled:
            try:
                # LangSmith 클라이언트 초기화
                self.client = Client(api_key=api_key)
                
                # 환경변수 설정
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_API_KEY"] = api_key
                os.environ["LANGCHAIN_PROJECT"] = self.project_name
                os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
                
                # LangChain Tracer 초기화 (최신 방식)
                self.tracer = LangChainTracer()
                
                # LLM 클라이언트 초기화 (Azure 또는 OpenAI)
                self._init_llm_client()
                
                self.enabled = True
                logger.info(f"✅ LangSmith 추적이 활성화되었습니다. 프로젝트: {self.project_name}")
                
            except Exception as e:
                logger.warning(f"⚠️  LangSmith 초기화 실패: {e}")
                self.enabled = False
        else:
            logger.info("ℹ️  LangSmith 추적이 비활성화되어 있습니다.")
    
    def _init_llm_client(self):
        """LLM 클라이언트 초기화 (Azure 또는 OpenAI)"""
        api_type = os.getenv("OPENAI_API_TYPE", "openai")
        
        try:
            if api_type == "azure":
                self.llm_client = AzureChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                    deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4"),
                    callbacks=[self.tracer] if self.tracer else []
                )
                logger.info("✅ Azure OpenAI LLM 클라이언트 초기화 완료")
            else:
                self.llm_client = ChatOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    model="gpt-4",
                    callbacks=[self.tracer] if self.tracer else []
                )
                logger.info("✅ OpenAI LLM 클라이언트 초기화 완료")
        except Exception as e:
            logger.warning(f"⚠️  LLM 클라이언트 초기화 실패: {e}")
    
    def get_callbacks(self):
        """LangChain 콜백 반환"""
        if self.enabled and self.tracer:
            return [self.tracer]
        return []
    
    def trace_run(self, name: str, run_type: str = "llm", metadata: dict = None):
        """실행 추적 데코레이터"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)
                
                try:
                    # 메타데이터 설정
                    run_metadata = {
                        "function": func.__name__,
                        "module": func.__module__,
                        **(metadata or {})
                    }
                    
                    # 실행 시작 로깅
                    logger.info(f"🔍 LangSmith 추적 시작: {name}")
                    
                    result = await func(*args, **kwargs)
                    
                    # 실행 완료 로깅
                    logger.info(f"✅ LangSmith 추적 완료: {name}")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"❌ LangSmith 추적 중 오류: {name} - {e}")
                    raise
                    
            return wrapper
        return decorator
    
    def log_llm_call(self, model: str, prompt: str, response: str, metadata: dict = None):
        """LLM 호출 수동 로깅"""
        if not self.enabled or not self.client:
            return
            
        try:
            self.client.create_run(
                name=f"llm_call_{model}",
                run_type="llm",
                inputs={"prompt": prompt},
                outputs={"response": response},
                extra={
                    "model": model,
                    **(metadata or {})
                }
            )
        except Exception as e:
            logger.warning(f"⚠️  LangSmith 수동 로깅 실패: {e}")

# 전역 LangSmith 매니저 인스턴스
langsmith_manager = LangSmithManager()

def trace_llm_call(name: str, metadata: dict = None):
    """LLM 호출 추적 데코레이터"""
    return langsmith_manager.trace_run(name, "llm", metadata)