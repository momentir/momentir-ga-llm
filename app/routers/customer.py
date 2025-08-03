from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import pandas as pd
import io

from app.models import (
    CustomerCreateRequest, CustomerResponse, CustomerUpdateRequest,
    ExcelUploadResponse, ColumnMappingRequest, ColumnMappingResponse,
    ErrorResponse
)
from app.services.customer_service import CustomerService
from app.services.memo_refiner import MemoRefinerService
from app.database import get_db
from datetime import datetime

router = APIRouter(prefix="/api/customer", tags=["customer"])
customer_service = CustomerService()
memo_refiner = MemoRefinerService()


@router.post("/create", response_model=CustomerResponse)
async def create_customer(request: CustomerCreateRequest, db: AsyncSession = Depends(get_db)):
    """
    새 고객을 생성합니다.
    
    - **name**: 고객 이름
    - **contact**: 연락처 (전화번호, 이메일 등)
    - **affiliation**: 소속 (회사, 기관 등)
    - **occupation**: 직업
    - **gender**: 성별
    - **date_of_birth**: 생년월일 (YYYY-MM-DD)
    - **interests**: 관심사 리스트
    - **life_events**: 인생 이벤트 목록
    - **insurance_products**: 보험 상품 정보
    
    기능:
    - 고객 데이터 검증 및 저장
    - 생년월일 자동 파싱
    - JSON 데이터 처리
    """
    try:
        customer = await customer_service.create_customer(request, db)
        
        return CustomerResponse(
            customer_id=str(customer.customer_id),
            name=customer.name,
            contact=customer.contact,
            affiliation=customer.affiliation,
            occupation=customer.occupation,
            gender=customer.gender,
            date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
            interests=customer.interests or [],
            life_events=customer.life_events or [],
            insurance_products=customer.insurance_products or [],
            created_at=customer.created_at,
            updated_at=customer.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    """
    고객 ID로 고객 정보를 조회합니다.
    
    - **customer_id**: 조회할 고객의 ID
    
    기능:
    - 고객 상세 정보 조회
    - 관련 메모 및 이벤트 정보 포함
    """
    try:
        customer = await customer_service.get_customer_by_id(customer_id, db)
        
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        return CustomerResponse(
            customer_id=str(customer.customer_id),
            name=customer.name,
            contact=customer.contact,
            affiliation=customer.affiliation,
            occupation=customer.occupation,
            gender=customer.gender,
            date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
            interests=customer.interests or [],
            life_events=customer.life_events or [],
            insurance_products=customer.insurance_products or [],
            created_at=customer.created_at,
            updated_at=customer.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: str, request: CustomerUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    고객 정보를 업데이트합니다.
    
    - **customer_id**: 업데이트할 고객의 ID
    - 요청 본문에 업데이트할 필드들 포함
    
    기능:
    - 부분 업데이트 지원 (null이 아닌 필드만 업데이트)
    - 데이터 검증 및 변환
    """
    try:
        customer = await customer_service.update_customer(customer_id, request, db)
        
        return CustomerResponse(
            customer_id=str(customer.customer_id),
            name=customer.name,
            contact=customer.contact,
            affiliation=customer.affiliation,
            occupation=customer.occupation,
            gender=customer.gender,
            date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
            interests=customer.interests or [],
            life_events=customer.life_events or [],
            insurance_products=customer.insurance_products or [],
            created_at=customer.created_at,
            updated_at=customer.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 업데이트 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    """
    고객을 삭제합니다.
    
    - **customer_id**: 삭제할 고객의 ID
    
    기능:
    - 고객 데이터 완전 삭제
    - 관련 메모 및 이벤트도 함께 삭제 (CASCADE)
    """
    try:
        success = await customer_service.delete_customer(customer_id, db)
        
        if success:
            return {"message": f"고객 {customer_id}가 성공적으로 삭제되었습니다."}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 삭제 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(default=100, le=1000, description="최대 조회 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 개수"),
    search: Optional[str] = Query(default=None, description="검색어 (이름, 연락처, 소속)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객 목록을 조회합니다.
    
    - **limit**: 최대 조회 수 (기본: 100, 최대: 1000)
    - **offset**: 건너뛸 개수 (페이징용)
    - **search**: 검색어 (이름, 연락처, 소속에서 검색)
    
    기능:
    - 페이징 지원
    - 검색 기능
    - 최신순 정렬
    """
    try:
        if search:
            customers = await customer_service.search_customers(search, db, limit)
            total_count = len(customers)
        else:
            customers, total_count = await customer_service.get_customer_list(db, limit, offset)
        
        customer_responses = []
        for customer in customers:
            customer_responses.append(CustomerResponse(
                customer_id=str(customer.customer_id),
                name=customer.name,
                contact=customer.contact,
                affiliation=customer.affiliation,
                occupation=customer.occupation,
                gender=customer.gender,
                date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
                interests=customer.interests or [],
                life_events=customer.life_events or [],
                insurance_products=customer.insurance_products or [],
                created_at=customer.created_at,
                updated_at=customer.updated_at
            ))
        
        return customer_responses
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/column-mapping", response_model=ColumnMappingResponse)
async def map_excel_columns(request: ColumnMappingRequest):
    """
    엑셀 컬럼명을 표준 스키마로 매핑합니다.
    
    - **excel_columns**: 엑셀 파일의 컬럼명 리스트
    
    기능:
    - LLM을 사용한 지능형 컬럼 매핑
    - 한국어/영어 컬럼명 지원
    - 동의어 및 약어 인식
    - 신뢰도 점수 제공
    """
    try:
        result = await customer_service.map_excel_columns(request.excel_columns)
        
        return ColumnMappingResponse(
            mapping=result["mapping"],
            unmapped_columns=result["unmapped_columns"],
            confidence_score=result["confidence_score"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"컬럼 매핑 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/excel-upload", response_model=ExcelUploadResponse)
async def upload_excel_file(
    file: UploadFile = File(..., description="업로드할 엑셀 파일 (.xlsx, .xls)"),
    auto_map: bool = Query(default=True, description="자동 컬럼 매핑 사용 여부"),
    db: AsyncSession = Depends(get_db)
):
    """
    엑셀 파일을 업로드하여 고객 데이터를 일괄 등록/업데이트합니다.
    
    - **file**: 엑셀 파일 (.xlsx 또는 .xls)
    - **auto_map**: 자동 컬럼 매핑 사용 여부
    
    기능:
    - 다양한 엑셀 형식 지원
    - LLM 기반 자동 컬럼 매핑
    - 중복 고객 자동 감지 및 업데이트
    - 에러 로그 제공
    - 처리 결과 상세 리포트
    """
    try:
        # 파일 형식 검증
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="엑셀 파일만 업로드 가능합니다 (.xlsx, .xls)"
            )
        
        # 파일 읽기
        contents = await file.read()
        
        try:
            # pandas로 엑셀 파일 읽기
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"엑셀 파일을 읽을 수 없습니다: {str(e)}"
            )
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="엑셀 파일이 비어있습니다."
            )
        
        # 컬럼 매핑
        column_mapping = {}
        if auto_map:
            excel_columns = df.columns.tolist()
            mapping_result = await customer_service.map_excel_columns(excel_columns)
            column_mapping = mapping_result["mapping"]
        else:
            # 수동 매핑인 경우 1:1 매핑 (구현 필요시 확장)
            column_mapping = {col: col for col in df.columns}
        
        # 데이터 처리
        process_result = await customer_service.process_excel_data(df, column_mapping, db)
        
        return ExcelUploadResponse(
            success=process_result["success"],
            processed_rows=process_result["processed_rows"],
            created_customers=process_result["created_customers"],
            updated_customers=process_result["updated_customers"],
            errors=process_result["errors"],
            column_mapping=column_mapping
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"엑셀 업로드 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{customer_id}/analytics")
async def get_customer_analytics(customer_id: str, db: AsyncSession = Depends(get_db)):
    """
    특정 고객의 메모 및 분석 통계를 조회합니다.
    
    - **customer_id**: 조회할 고객의 ID
    
    기능:
    - 고객별 메모 작성 통계
    - 분석 수행 이력
    - 정제율 및 활동 빈도
    - 고객 프로필 요약
    """
    try:
        analytics = await memo_refiner.get_customer_analytics(customer_id, db)
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 분석 통계 조회 중 오류가 발생했습니다: {str(e)}"
        )