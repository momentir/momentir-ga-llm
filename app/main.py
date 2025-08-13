from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
# V1 Routers (Legacy)
from app.api.v1.routers import memo as memo_v1, customer as customer_v1, events as events_v1, prompts as prompts_v1, auth as auth_v1, search as search_v1

# V2 Routers (Next Generation)  
from app.api.v2.routers import memo as memo_v2, search as search_v2

# Core shared components
from app.core.database import db_manager
from app.core.utils.langsmith_config import langsmith_manager
from app.core.utils.cloudwatch_logger import cloudwatch_logger
from app.core.middleware.monitoring import setup_monitoring_middleware
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
    
    # CloudWatch 로깅 초기화
    cloudwatch_logger.log_structured(
        "INFO", 
        "Application startup completed",
        {
            "event_type": "application_startup",
            "ecs_fargate": cloudwatch_logger.is_ecs_fargate,
            "environment": cloudwatch_logger.environment
        }
    )
    
    yield
    
    # 종료 시: 리소스 정리
    await db_manager.close()
    print("데이터베이스 연결이 종료되었습니다.")
    
    # CloudWatch 로깅 종료
    cloudwatch_logger.log_structured(
        "INFO", 
        "Application shutdown completed",
        {
            "event_type": "application_shutdown",
            "environment": cloudwatch_logger.environment
        }
    )


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

# CloudWatch 모니터링 미들웨어 설정
setup_monitoring_middleware(app, enable_detailed=True)

# V1 API Routes (Legacy)
app.include_router(auth_v1.router)
app.include_router(memo_v1.router)
app.include_router(customer_v1.router)
app.include_router(events_v1.router)
app.include_router(prompts_v1.router)
app.include_router(search_v1.router)

# V1 Additional routers
from app.api.v1.routers import prompt_logs as prompt_logs_v1
app.include_router(prompt_logs_v1.router)

# V2 API Routes (Next Generation)
app.include_router(memo_v2.router)
app.include_router(search_v2.router)

# LCEL SQL 파이프라인 라우터 추가
from app.api import lcel_sql_routes
app.include_router(lcel_sql_routes.router)

# V1 검색 분석 라우터 추가
from app.api.v1.routers import search_analytics as search_analytics_v1
app.include_router(search_analytics_v1.router)

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {
        "message": "Momentir CX API",
        "version": "1.0.0",
        "web_interface": "/static/prompt_manager.html",
        "endpoints": {
            "memo_quick_save": "/v1/api/memo/quick-save",
            "memo_refine": "/v1/api/memo/refine",
            "memo_analyze": "/v1/api/memo/analyze", 
            "memo_get": "/v1/api/memo/memo/{memo_id}",
            "customer_create": "/v1/api/customer/create",
            "customer_list": "/v1/api/customer/",
            "customer_excel_upload": "/v1/api/customer/excel-upload",
            "customer_column_mapping": "/v1/api/customer/column-mapping",
            "customer_analytics": "/v1/api/customer/{customer_id}/analytics",
            "events_process_memo": "/v1/api/events/process-memo",
            "events_upcoming": "/v1/api/events/upcoming",
            "events_customer": "/v1/api/events/customer/{customer_id}",
            "events_status": "/v1/api/events/status",
            "events_statistics": "/v1/api/events/statistics",
            "events_generate_rule_based": "/v1/api/events/generate-rule-based",
            "events_update_priorities": "/v1/api/events/update-priorities",
            "events_priority": "/v1/api/events/priority/{priority}",
            "events_urgent_today": "/v1/api/events/urgent-today",
            "prompts_templates": "/v1/api/prompts/templates",
            "prompts_render": "/v1/api/prompts/render",
            "prompts_ab_tests": "/v1/api/prompts/ab-tests",
            "auth_login": "/v1/auth/login",
            "auth_logout": "/v1/auth/logout",
            "auth_signup": "/v1/auth/sign-up",
            "auth_find_email": "/v1/auth/find-my-email",
            "auth_reset_password": "/v1/auth/reset-password",
            "auth_verify_email": "/v1/auth/verify-email-account",
            "lcel_sql_generate": "/v1/api/lcel-sql/generate",
            "lcel_sql_streaming": "/v1/api/lcel-sql/generate-streaming", 
            "lcel_sql_execute": "/v1/api/lcel-sql/execute-and-run",
            "lcel_sql_strategies": "/v1/api/lcel-sql/strategies",
            "lcel_sql_health": "/v1/api/lcel-sql/health",
            "natural_language_search": "/v1/api/search/natural-language",
            "search_strategies": "/v1/api/search/strategies",
            "search_health": "/v1/api/search/health",
            "search_websocket": "/ws/search/stream",
            "search_analytics_record": "/v1/api/search-analytics/record",
            "search_analytics_popular": "/v1/api/search-analytics/popular-queries",
            "search_analytics_performance": "/v1/api/search-analytics/performance-stats",
            "search_analytics_failures": "/v1/api/search-analytics/failure-patterns",
            "search_analytics_dashboard": "/v1/api/search-analytics/dashboard",
            "v2_memo_quick_save": "/v2/api/memo/quick-save",
            "v2_memo_refine": "/v2/api/memo/refine",
            "v2_memo_analyze": "/v2/api/memo/analyze",
            "v2_memo_get": "/v2/api/memo/memo/{memo_id}",
            "v2_natural_language_search": "/v2/api/search/natural-language",
            "v2_search_strategies": "/v2/api/search/strategies/v2",
            "v2_search_analytics": "/v2/api/search/analytics/v2",
            "v2_search_feedback": "/v2/api/search/feedback/v2",
            "v2_search_health": "/v2/api/search/health/v2",
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