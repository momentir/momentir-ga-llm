import os
from typing import Optional
from functools import wraps
from langsmith import Client
from langchain_core.tracers.langchain import LangChainTracer
from langchain_openai import AzureChatOpenAI, ChatOpenAI
import logging

# .env 파일 로드 시도
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

class LangSmithManager:
    """LangSmith 추적 관리자"""
    
    def __init__(self):
        self.enabled = False
        self.client: Optional[Client] = None
        self.tracer: Optional[LangChainTracer] = None
        self.project_name = self._get_project_name()
        self.llm_client = None
        
        self._initialize()
    
    def _get_project_name(self) -> str:
        """환경별 LangSmith 프로젝트명 결정"""
        # 운영환경 감지 조건들
        is_production = (
            os.getenv("ENVIRONMENT") == "production" or 
            os.getenv("AWS_EXECUTION_ENV") is not None or
            os.getenv("ECS_CONTAINER_METADATA_URI") is not None or
            os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
        )
        
        # 로컬 환경 명시적 감지 (운영환경이 아닌 경우만 체크)
        is_local = not is_production and (
            os.getenv("ENVIRONMENT") == "local" or
            os.path.exists(".env")  # .env 파일 존재하고 운영환경이 아닌 경우 로컬로 간주
        )
        
        # 메모 정제용 프로젝트명 결정
        if is_production:
            return "momentir-cx-llm-memo"
        else:
            return "local-llm-memo"
    
    def get_excel_upload_project_name(self) -> str:
        """엑셀 업로드용 프로젝트명 반환"""
        # 운영환경 감지 조건들
        is_production = (
            os.getenv("ENVIRONMENT") == "production" or 
            os.getenv("AWS_EXECUTION_ENV") is not None or
            os.getenv("ECS_CONTAINER_METADATA_URI") is not None or
            os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
        )
        
        # 로컬 환경 명시적 감지 (운영환경이 아닌 경우만 체크)
        is_local = not is_production and (
            os.getenv("ENVIRONMENT") == "local" or
            os.path.exists(".env")  # .env 파일 존재하고 운영환경이 아닌 경우 로컬로 간주
        )
        
        # 엑셀 업로드용 프로젝트명 결정
        if is_production:
            return "momentir-cx-llm-excel-upload"
        else:
            return "local-llm-excel-upload"
    
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
    
    def get_callbacks(self, project_name: Optional[str] = None):
        """LangChain 콜백 반환 (프로젝트별 설정 지원)"""
        if self.enabled and self.tracer:
            # 프로젝트명이 지정된 경우, 새로운 tracer 생성
            if project_name:
                # 프로젝트명을 직접 지정하여 tracer 생성
                temp_tracer = LangChainTracer(project_name=project_name)
                return [temp_tracer]
            return [self.tracer]
        return []
    
    def trace_run(self, name: str, run_type: str = "llm", metadata: dict = None, project_name: Optional[str] = None):
        """실행 추적 데코레이터 (프로젝트별 설정 지원)"""
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
                        "project": project_name or self.project_name,
                        **(metadata or {})
                    }
                    
                    # 실행 시작 로깅
                    used_project = project_name or self.project_name
                    logger.info(f"🔍 LangSmith 추적 시작: {name} (프로젝트: {used_project})")
                    
                    # 프로젝트명이 지정된 경우, 환경변수 임시 변경
                    original_project = None
                    if project_name:
                        original_project = os.environ.get("LANGCHAIN_PROJECT")
                        os.environ["LANGCHAIN_PROJECT"] = project_name
                    
                    try:
                        result = await func(*args, **kwargs)
                    finally:
                        # 원래 환경변수 복원
                        if project_name and original_project:
                            os.environ["LANGCHAIN_PROJECT"] = original_project
                    
                    # 실행 완료 로깅
                    logger.info(f"✅ LangSmith 추적 완료: {name} (프로젝트: {used_project})")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"❌ LangSmith 추적 중 오류: {name} - {e}")
                    raise
                    
            return wrapper
        return decorator
    
    def log_llm_call(self, model: str, prompt: str, response: str, metadata: dict = None, project_name: Optional[str] = None):
        """LLM 호출 수동 로깅 (프로젝트별 설정 지원)"""
        if not self.enabled or not self.client:
            return
            
        try:
            # 프로젝트명이 지정된 경우 환경변수 임시 변경
            original_project = None
            if project_name:
                original_project = os.environ.get("LANGCHAIN_PROJECT")
                os.environ["LANGCHAIN_PROJECT"] = project_name
            
            try:
                self.client.create_run(
                    name=f"llm_call_{model}",
                    run_type="llm",
                    inputs={"prompt": prompt},
                    outputs={"response": response},
                    extra={
                        "model": model,
                        "project": project_name or self.project_name,
                        **(metadata or {})
                    }
                )
            finally:
                # 원래 환경변수 복원
                if project_name and original_project:
                    os.environ["LANGCHAIN_PROJECT"] = original_project
                    
        except Exception as e:
            logger.warning(f"⚠️  LangSmith 수동 로깅 실패: {e}")

# 전역 LangSmith 매니저 인스턴스
langsmith_manager = LangSmithManager()

def trace_llm_call(name: str, metadata: dict = None, project_name: Optional[str] = None):
    """LLM 호출 추적 데코레이터 (프로젝트별 설정 지원)"""
    return langsmith_manager.trace_run(name, "llm", metadata, project_name)

def trace_excel_upload_call(name: str, metadata: dict = None):
    """엑셀 업로드 관련 LLM 호출 추적 데코레이터"""
    project_name = langsmith_manager.get_excel_upload_project_name()
    return langsmith_manager.trace_run(name, "llm", metadata, project_name)

def get_excel_upload_llm_client():
    """엑셀 업로드 전용 LangChain 클라이언트 반환 (엑셀 업로드 프로젝트로 설정됨)"""
    if not langsmith_manager.enabled:
        return None
    
    # 엑셀 업로드 프로젝트명 가져오기
    excel_project = langsmith_manager.get_excel_upload_project_name()
    
    # 엑셀 업로드 전용 콜백 생성
    callbacks = langsmith_manager.get_callbacks(excel_project)
    
    # API 타입에 따라 적절한 클라이언트 생성
    api_type = os.getenv("OPENAI_API_TYPE", "openai")
    
    try:
        if api_type == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4"),
                callbacks=callbacks
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4",
                callbacks=callbacks
            )
    except Exception as e:
        logger.warning(f"⚠️  엑셀 업로드 전용 LLM 클라이언트 생성 실패: {e}")
        return None