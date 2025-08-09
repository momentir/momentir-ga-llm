from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from app.routers import memo, customer, events, prompts, auth
from app.database import db_manager
from app.utils.langsmith_config import langsmith_manager
from dotenv import load_dotenv
import os
import logging

# 불필요한 404 로그를 필터링하는 클래스
class IgnoreSpecificPathsFilter(logging.Filter):
    def filter(self, record):
        # 무시할 경로 패턴들
        ignore_patterns = [
            '/.well-known/appspecific/com.chrome.devtools.json',
            '/favicon.ico',
            '/robots.txt',
            '/apple-touch-icon',
            '/.well-known/',
            '/sitemap.xml'
        ]
        
        # 로그 메시지에서 무시할 패턴이 있는지 확인
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            for pattern in ignore_patterns:
                if pattern in message and '404 Not Found' in message:
                    return False
        
        return True

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# uvicorn의 access 로거에 필터 적용
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(IgnoreSpecificPathsFilter())

load_dotenv()

# LangSmith 상태 로깅
logger.info(f"🔍 LangSmith 상태: enabled={langsmith_manager.enabled}, project={langsmith_manager.project_name}")
logger.info(f"🔍 환경변수 - LANGSMITH_API_KEY: {'설정됨' if os.getenv('LANGSMITH_API_KEY') else '설정안됨'}")
logger.info(f"🔍 환경변수 - LANGSMITH_TRACING: {os.getenv('LANGSMITH_TRACING')}")
logger.info(f"🔍 환경변수 - LANGSMITH_PROJECT: {os.getenv('LANGSMITH_PROJECT')}")
logger.info(f"🔍 환경변수 - LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2')}")
logger.info(f"🔍 환경변수 - LANGCHAIN_ENDPOINT: {os.getenv('LANGCHAIN_ENDPOINT')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시: 데이터베이스 초기화
    await db_manager.init_db()
    print("데이터베이스가 초기화되었습니다.")
    
    yield
    
    # 종료 시: 리소스 정리
    await db_manager.close()
    print("데이터베이스 연결이 종료되었습니다.")


app = FastAPI(
    title="Momentir CX API",
    description="보험계약자의 고객 메모를 LLM을 통해 정제하고 분석하는 시스템 (PostgreSQL + pgvector)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(memo.router)
app.include_router(customer.router)
app.include_router(events.router)
app.include_router(prompts.router)

# 프롬프트 테스트 로그 라우터 추가
from app.routers import prompt_logs
app.include_router(prompt_logs.router)

# LCEL SQL 파이프라인 라우터 추가
from app.api import lcel_sql_routes
app.include_router(lcel_sql_routes.router)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {
        "message": "Momentir CX API",
        "version": "1.0.0",
        "web_interface": "/static/prompt_manager.html",
        "endpoints": {
            "memo_quick_save": "/api/memo/quick-save",
            "memo_refine": "/api/memo/refine",
            "memo_analyze": "/api/memo/analyze", 
            "memo_get": "/api/memo/memo/{memo_id}",
            "customer_create": "/api/customer/create",
            "customer_list": "/api/customer/",
            "customer_excel_upload": "/api/customer/excel-upload",
            "customer_column_mapping": "/api/customer/column-mapping",
            "customer_analytics": "/api/customer/{customer_id}/analytics",
            "events_process_memo": "/api/events/process-memo",
            "events_upcoming": "/api/events/upcoming",
            "events_customer": "/api/events/customer/{customer_id}",
            "events_status": "/api/events/status",
            "events_statistics": "/api/events/statistics",
            "events_generate_rule_based": "/api/events/generate-rule-based",
            "events_update_priorities": "/api/events/update-priorities",
            "events_priority": "/api/events/priority/{priority}",
            "events_urgent_today": "/api/events/urgent-today",
            "prompts_templates": "/api/prompts/templates",
            "prompts_render": "/api/prompts/render",
            "prompts_ab_tests": "/api/prompts/ab-tests",
            "auth_login": "/v1/auth/login",
            "auth_logout": "/v1/auth/logout",
            "auth_signup": "/v1/auth/sign-up",
            "auth_find_email": "/v1/auth/find-my-email",
            "auth_reset_password": "/v1/auth/reset-password",
            "auth_verify_email": "/v1/auth/verify-email-account",
            "lcel_sql_generate": "/api/lcel-sql/generate",
            "lcel_sql_streaming": "/api/lcel-sql/generate-streaming", 
            "lcel_sql_execute": "/api/lcel-sql/execute-and-run",
            "lcel_sql_strategies": "/api/lcel-sql/strategies",
            "lcel_sql_health": "/api/lcel-sql/health",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 불필요한 404 로그를 방지하기 위한 엔드포인트들

@app.get("/favicon.ico")
async def favicon():
    # 빈 응답으로 404 로그 방지
    return Response(status_code=204)

@app.get("/robots.txt")
async def robots():
    return PlainTextResponse("User-agent: *\nDisallow: /api/\nAllow: /static/")

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools():
    return Response(status_code=204)