from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import memo, customer, events, prompts
from app.database import db_manager
from app.utils.langsmith_config import langsmith_manager
from dotenv import load_dotenv
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    title="보험계약자 메모 정제 API",
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

app.include_router(memo.router)
app.include_router(customer.router)
app.include_router(events.router)
app.include_router(prompts.router)


@app.get("/")
async def root():
    return {
        "message": "보험계약자 메모 정제 API",
        "version": "1.0.0",
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
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}