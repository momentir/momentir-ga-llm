from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import memo, customer, events
from app.database import db_manager
from dotenv import load_dotenv
import os

load_dotenv()


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
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}