from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import pandas as pd
import io

from app.models import (
    CustomerCreateRequest, CustomerResponse, CustomerUpdateRequest,
    ExcelUploadResponse, ColumnMappingRequest, ColumnMappingResponse,
    ErrorResponse
)
from app.models.main_models import ExcelUploadRequest, CustomerProductCreate, CustomerProductResponse
from app.db_models import User
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
    새 고객을 생성합니다 (확장된 필드 및 가입상품 지원).
    
    ## 기본 필드:
    - **user_id**: 설계사 ID (필수)
    - **name**: 고객 이름
    - **contact**: 연락처 (전화번호, 이메일 등)
    - **affiliation**: 소속 (회사, 기관 등)
    - **gender**: 성별
    - **date_of_birth**: 생년월일 (YYYY-MM-DD)
    - **interests**: 관심사 리스트
    - **life_events**: 인생 이벤트 목록
    - **insurance_products**: 보험 상품 정보
    
    ## 확장 필드:
    - **customer_type**: 고객 유형 (가입, 미가입)
    - **contact_channel**: 고객 접점 (가족, 지역, 소개, 지역마케팅, 인바운드, 제휴db, 단체계약, 방카, 개척, 기타)
    - **phone**: 전화번호 (자동 포맷팅: 000-0000-0000)
    - **resident_number**: 주민번호 (자동 마스킹: 999999-1******)
    - **address**: 주소
    - **job_title**: 직업
    - **bank_name**: 계좌은행
    - **account_number**: 계좌번호
    - **referrer**: 소개자
    - **notes**: 기타 메모
    
    ## 가입상품:
    - **products**: 가입상품 리스트 (CustomerProductCreate 배열)
    
    ## 기능:
    - 설계사 ID 검증
    - 전화번호/주민번호 자동 포맷팅
    - 가입상품 동시 생성
    - 데이터 검증 및 변환
    """
    try:
        # 설계사 ID 검증 (필수)
        if not request.user_id:
            raise HTTPException(
                status_code=400,
                detail="설계사 ID(user_id)는 필수입니다."
            )
        
        customer = await customer_service.create_customer(request, db)
        
        # 가입상품 조회 (관계를 통해 로드)
        from app.db_models import CustomerProduct
        from sqlalchemy import select
        
        products_stmt = select(CustomerProduct).where(CustomerProduct.customer_id == customer.customer_id)
        products_result = await db.execute(products_stmt)
        customer_products = products_result.scalars().all()
        
        # 응답 데이터 구성
        from app.models.main_models import CustomerProductResponse
        products_response = []
        for product in customer_products:
            products_response.append(CustomerProductResponse(
                product_id=str(product.product_id),
                product_name=product.product_name,
                coverage_amount=product.coverage_amount,
                subscription_date=product.subscription_date.date() if product.subscription_date else None,
                expiry_renewal_date=product.expiry_renewal_date.date() if product.expiry_renewal_date else None,
                auto_transfer_date=product.auto_transfer_date,
                policy_issued=product.policy_issued or False,
                created_at=product.created_at,
                updated_at=product.updated_at
            ))
        
        return CustomerResponse(
            customer_id=str(customer.customer_id),
            user_id=customer.user_id,
            name=customer.name,
            affiliation=customer.affiliation,
            gender=customer.gender,
            date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
            interests=customer.interests or [],
            life_events=customer.life_events or [],
            insurance_products=customer.insurance_products or [],
            
            # 확장 필드들
            customer_type=customer.customer_type,
            contact_channel=customer.contact_channel,
            phone=customer.phone,
            resident_number=customer.resident_number,
            address=customer.address,
            job_title=customer.job_title,
            bank_name=customer.bank_name,
            account_number=customer.account_number,
            referrer=customer.referrer,
            notes=customer.notes,
            
            # 가입상품들
            products=products_response,
            
            created_at=customer.created_at,
            updated_at=customer.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str, 
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객 ID로 고객 정보를 조회합니다 (가입상품 포함).
    
    - **customer_id**: 조회할 고객의 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    
    기능:
    - 고객 상세 정보 조회 (모든 확장 필드 포함)
    - 가입상품 정보 함께 조회
    - 설계사 권한 체크 (user_id 제공 시)
    """
    try:
        customer = await customer_service.get_customer_by_id(customer_id, db)
        
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 가입상품 조회
        from app.db_models import CustomerProduct
        from sqlalchemy import select
        
        products_stmt = select(CustomerProduct).where(CustomerProduct.customer_id == customer.customer_id)
        products_result = await db.execute(products_stmt)
        customer_products = products_result.scalars().all()
        
        # 가입상품 응답 데이터 구성
        from app.models.main_models import CustomerProductResponse
        products_response = []
        for product in customer_products:
            products_response.append(CustomerProductResponse(
                product_id=str(product.product_id),
                product_name=product.product_name,
                coverage_amount=product.coverage_amount,
                subscription_date=product.subscription_date.date() if product.subscription_date else None,
                expiry_renewal_date=product.expiry_renewal_date.date() if product.expiry_renewal_date else None,
                auto_transfer_date=product.auto_transfer_date,
                policy_issued=product.policy_issued or False,
                created_at=product.created_at,
                updated_at=product.updated_at
            ))
        
        return CustomerResponse(
            customer_id=str(customer.customer_id),
            user_id=customer.user_id,
            name=customer.name,
            affiliation=customer.affiliation,
            gender=customer.gender,
            date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
            interests=customer.interests or [],
            life_events=customer.life_events or [],
            insurance_products=customer.insurance_products or [],
            
            # 확장 필드들
            customer_type=customer.customer_type,
            contact_channel=customer.contact_channel,
            phone=customer.phone,
            resident_number=customer.resident_number,
            address=customer.address,
            job_title=customer.job_title,
            bank_name=customer.bank_name,
            account_number=customer.account_number,
            referrer=customer.referrer,
            notes=customer.notes,
            
            # 가입상품들
            products=products_response,
            
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
async def update_customer(
    customer_id: str, 
    request: CustomerUpdateRequest, 
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객 정보를 업데이트합니다 (확장된 필드 지원).
    
    - **customer_id**: 업데이트할 고객의 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    - 요청 본문에 업데이트할 필드들 포함
    
    ## 지원 필드:
    - 기존 필드: name, contact, affiliation, gender, date_of_birth, interests, life_events, insurance_products
    - 확장 필드: customer_type, contact_channel, phone, resident_number, address, job_title, bank_name, account_number, referrer, notes
    
    ## 기능:
    - 부분 업데이트 지원 (null이 아닌 필드만 업데이트)
    - 전화번호/주민번호 자동 포맷팅
    - 설계사 권한 체크
    - 가입상품 정보 함께 반환
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 고객 정보 업데이트
        updated_customer = await customer_service.update_customer(customer_id, request, db)
        
        # 가입상품 조회
        from app.db_models import CustomerProduct
        from sqlalchemy import select
        
        products_stmt = select(CustomerProduct).where(CustomerProduct.customer_id == updated_customer.customer_id)
        products_result = await db.execute(products_stmt)
        customer_products = products_result.scalars().all()
        
        # 가입상품 응답 데이터 구성
        from app.models.main_models import CustomerProductResponse
        products_response = []
        for product in customer_products:
            products_response.append(CustomerProductResponse(
                product_id=str(product.product_id),
                product_name=product.product_name,
                coverage_amount=product.coverage_amount,
                subscription_date=product.subscription_date.date() if product.subscription_date else None,
                expiry_renewal_date=product.expiry_renewal_date.date() if product.expiry_renewal_date else None,
                auto_transfer_date=product.auto_transfer_date,
                policy_issued=product.policy_issued or False,
                created_at=product.created_at,
                updated_at=product.updated_at
            ))
        
        return CustomerResponse(
            customer_id=str(updated_customer.customer_id),
            user_id=updated_customer.user_id,
            name=updated_customer.name,
            affiliation=updated_customer.affiliation,
            gender=updated_customer.gender,
            date_of_birth=updated_customer.date_of_birth.date() if updated_customer.date_of_birth else None,
            interests=updated_customer.interests or [],
            life_events=updated_customer.life_events or [],
            insurance_products=updated_customer.insurance_products or [],
            
            # 확장 필드들
            customer_type=updated_customer.customer_type,
            contact_channel=updated_customer.contact_channel,
            phone=updated_customer.phone,
            resident_number=updated_customer.resident_number,
            address=updated_customer.address,
            job_title=updated_customer.job_title,
            bank_name=updated_customer.bank_name,
            account_number=updated_customer.account_number,
            referrer=updated_customer.referrer,
            notes=updated_customer.notes,
            
            # 가입상품들
            products=products_response,
            
            created_at=updated_customer.created_at,
            updated_at=updated_customer.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"고객 업데이트 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str, 
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객을 삭제합니다.
    
    - **customer_id**: 삭제할 고객의 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    
    기능:
    - 고객 데이터 완전 삭제
    - 관련 메모 및 이벤트도 함께 삭제 (CASCADE)
    - 설계사 권한 체크
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 삭제 권한이 없습니다."
            )
        
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
    user_id: Optional[int] = Query(None, description="설계사 ID (필터링용)"),
    search: Optional[str] = Query(default=None, description="검색어 (이름, 연락처, 소속)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객 목록을 조회합니다 (설계사별 필터링 지원).
    
    - **limit**: 최대 조회 수 (기본: 100, 최대: 1000)
    - **offset**: 건너뛸 개수 (페이징용)
    - **user_id**: 설계사 ID (해당 설계사의 고객만 조회)
    - **search**: 검색어 (이름, 연락처, 소속에서 검색)
    
    ## 기능:
    - 페이징 지원
    - 설계사별 필터링
    - 검색 기능 
    - 최신순 정렬
    - 가입상품 개수 표시
    """
    try:
        # 설계사별 필터링을 위한 쿼리 조건 구성
        from app.db_models import Customer, CustomerProduct
        from sqlalchemy import select, func as sql_func, and_
        
        # 기본 쿼리 구성
        base_query = select(Customer)
        if user_id:
            base_query = base_query.where(Customer.user_id == user_id)
        
        # 검색 조건 추가
        if search:
            search_conditions = [
                Customer.name.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
                Customer.affiliation.ilike(f"%{search}%"),
            ]
            from sqlalchemy import or_
            base_query = base_query.where(or_(*search_conditions))
        
        # 페이징 및 정렬 적용
        query = base_query.offset(offset).limit(limit).order_by(Customer.updated_at.desc())
        
        result = await db.execute(query)
        customers = result.scalars().all()
        
        # 각 고객의 가입상품 개수 조회
        customer_responses = []
        for customer in customers:
            # 가입상품 개수 조회
            products_count_query = select(sql_func.count(CustomerProduct.product_id)).where(
                CustomerProduct.customer_id == customer.customer_id
            )
            products_count_result = await db.execute(products_count_query)
            products_count = products_count_result.scalar() or 0
            
            # 가입상품 조회 (리스트용이므로 간략하게)
            products_query = select(CustomerProduct).where(CustomerProduct.customer_id == customer.customer_id).limit(5)
            products_result = await db.execute(products_query)
            customer_products = products_result.scalars().all()
            
            # 응답 데이터 구성
            from app.models.main_models import CustomerProductResponse
            products_response = []
            for product in customer_products:
                products_response.append(CustomerProductResponse(
                    product_id=str(product.product_id),
                    product_name=product.product_name,
                    coverage_amount=product.coverage_amount,
                    subscription_date=product.subscription_date.date() if product.subscription_date else None,
                    expiry_renewal_date=product.expiry_renewal_date.date() if product.expiry_renewal_date else None,
                    auto_transfer_date=product.auto_transfer_date,
                    policy_issued=product.policy_issued or False,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
            
            customer_responses.append(CustomerResponse(
                customer_id=str(customer.customer_id),
                user_id=customer.user_id,
                name=customer.name,
                    affiliation=customer.affiliation,
                    gender=customer.gender,
                date_of_birth=customer.date_of_birth.date() if customer.date_of_birth else None,
                interests=customer.interests or [],
                life_events=customer.life_events or [],
                insurance_products=customer.insurance_products or [],
                
                # 확장 필드들
                customer_type=customer.customer_type,
                contact_channel=customer.contact_channel,
                phone=customer.phone,
                resident_number=customer.resident_number,
                address=customer.address,
                job_title=customer.job_title,
                bank_name=customer.bank_name,
                account_number=customer.account_number,
                referrer=customer.referrer,
                notes=customer.notes,
                
                # 가입상품들 (최대 5개만 표시)
                products=products_response,
                
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
async def map_excel_columns(
    file: UploadFile = File(..., description="컬럼 매핑할 엑셀 파일"),
    user_id: int = Form(..., description="설계사 ID"),
    custom_prompt: Optional[str] = Form(None, description="커스텀 매핑 프롬프트"),
    db: AsyncSession = Depends(get_db)
):
    """
    엑셀 파일의 컬럼명을 표준 스키마로 매핑합니다.
    
    - **file**: 매핑할 엑셀 파일
    - **user_id**: 설계사 ID 
    - **custom_prompt**: 커스텀 매핑 프롬프트 (선택사항)
    
    기능:
    - LLM을 사용한 지능형 컬럼 매핑
    - 한국어/영어 컬럼명 지원
    - 동의어 및 약어 인식
    - 신뢰도 점수 제공
    """
    try:
        # 파일 타입 검증
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 파일 형식입니다. .xlsx 또는 .xls 파일만 업로드 가능합니다."
            )
        
        # 설계사 존재 확인
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail=f"설계사 ID {user_id}를 찾을 수 없습니다.")
        
        # 엑셀 파일 읽기
        try:
            # 파일 포인터를 처음으로 이동
            await file.seek(0)
            # 파일 내용을 바이트로 읽기
            contents = await file.read()
            # BytesIO 객체로 변환
            excel_buffer = io.BytesIO(contents)
            # pandas로 엑셀 읽기
            df = pd.read_excel(excel_buffer, engine='openpyxl')
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"엑셀 파일 읽기 실패: {str(e)}"
            )
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="엑셀 파일이 비어있습니다."
            )
        
        # 컬럼 매핑 실행
        excel_columns = df.columns.tolist()
        result = await customer_service.map_excel_columns(
            excel_columns, 
            db_session=db, 
            custom_prompt=custom_prompt
        )
        
        return ColumnMappingResponse(
            mapping=result["mapping"],
            unmapped_columns=result["unmapped_columns"],
            confidence_score=result["confidence_score"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"컬럼 매핑 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/excel-upload", response_model=ExcelUploadResponse)
async def upload_excel_file(
    file: UploadFile = File(..., description="업로드할 엑셀 파일 (.xlsx, .xls)"),
    user_id: int = Form(..., description="설계사 ID (필수)"),
    auto_map: bool = Query(default=True, description="자동 컬럼 매핑 사용 여부"),
    custom_prompt: Optional[str] = Form(None, description="커스텀 매핑 프롬프트"),
    column_mapping_json: Optional[str] = Form(None, description="미리 생성된 컬럼 매핑 JSON"),
    db: AsyncSession = Depends(get_db)
):
    """
    엑셀 파일을 업로드하여 고객 데이터를 일괄 등록/업데이트합니다.
    
    - **file**: 엑셀 파일 (.xlsx 또는 .xls)
    - **user_id**: 설계사 ID (Form 데이터로 전송)
    - **auto_map**: 자동 컬럼 매핑 사용 여부
    
    ## 지원 기능:
    - **확장된 필드 지원**: 고객 유형, 접점, 전화번호, 주민번호, 주소, 직업, 은행정보, 소개자, 메모
    - **가입상품 처리**: 동일 행 또는 여러 행에 걸친 상품 정보 자동 추출 및 저장
    - **데이터 검증**: 전화번호 자동 포맷팅(000-0000-0000), 주민번호 마스킹(999999-1******)
    - **LLM 기반 매핑**: 다양한 컬럼명 자동 인식 (한국어/영어, 동의어, 약어)
    - **중복 방지**: 고객 및 상품 중복 체크
    - **트랜잭션 처리**: 데이터 일관성 보장
    - **상세 통계**: 필드별 매핑 성공률, 처리 시간, 오류 상세 정보
    
    ## 응답 정보:
    - **처리된 행 수**: 총 처리한 엑셀 행 수
    - **생성된 고객 수**: 새로 생성된 고객 수
    - **업데이트된 고객 수**: 기존 고객 업데이트 수
    - **생성된 상품 수**: 새로 생성된 가입상품 수
    - **실패한 상품 수**: 처리 실패한 상품 수
    - **필드별 매핑 성공률**: 각 필드의 데이터 추출 성공률
    - **처리 시간**: 총 처리 소요 시간(초)
    - **오류 목록**: 상세한 오류 메시지 (행 번호 포함)
    
    ## 예시 엑셀 형식:
    ```
    | 고객명 | 전화번호 | 고객유형 | 접점 | 상품명 | 가입금액 | 가입일자 |
    |--------|----------|----------|------|--------|----------|----------|
    | 홍길동 | 01012345678 | 가입 | 소개 | 종합보험 | 100만원 | 2024-01-01 |
    ```
    """
    try:
        # 설계사 권한 확인
        from app.db_models import User
        from sqlalchemy import select
        
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"설계사 ID {user_id}를 찾을 수 없습니다. 유효한 설계사 ID를 입력해주세요."
            )
        
        # 파일 형식 검증
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail="엑셀 파일만 업로드 가능합니다 (.xlsx, .xls)"
            )
        
        # 파일 크기 검증 (100MB 제한)
        if file.size and file.size > 100 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="파일 크기가 너무 큽니다. 100MB 이하의 파일을 업로드해주세요."
            )
        
        # 파일 읽기
        contents = await file.read()
        
        try:
            # pandas로 엑셀 파일 읽기 (첫 번째 시트만)
            df = pd.read_excel(io.BytesIO(contents), sheet_name=0)
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
        
        # 최대 행 수 제한 (10000행)
        if len(df) > 10000:
            raise HTTPException(
                status_code=400,
                detail=f"처리할 수 있는 최대 행 수를 초과했습니다. (최대 10,000행, 현재 {len(df)}행)"
            )
        
        # 컬럼 매핑
        column_mapping = {}
        if column_mapping_json:
            # 미리 생성된 컬럼 매핑이 있는 경우 사용
            import json
            try:
                column_mapping = json.loads(column_mapping_json)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="컬럼 매핑 JSON 형식이 올바르지 않습니다."
                )
        elif auto_map:
            excel_columns = df.columns.tolist()
            mapping_result = await customer_service.map_excel_columns(
                excel_columns, 
                db_session=db, 
                custom_prompt=custom_prompt
            )
            column_mapping = mapping_result["mapping"]
        else:
            # 수동 매핑인 경우 1:1 매핑
            column_mapping = {col: col for col in df.columns}
        
        # 데이터 처리 (확장된 process_excel_data 메서드 사용)
        process_result = await customer_service.process_excel_data(df, column_mapping, user_id, db)
        
        # 트랜잭션 명시적 커밋 (개별 커밋 후 전체 트랜잭션 확정)
        await db.commit()
        
        # 확장된 응답 반환
        return ExcelUploadResponse(
            success=process_result["success"],
            processed_rows=process_result["processed_rows"],
            created_customers=process_result["created_customers"],
            updated_customers=process_result["updated_customers"],
            errors=process_result["errors"],
            column_mapping=column_mapping,
            
            # 새로운 필드들
            total_products=process_result["total_products"],
            created_products=process_result["created_products"],
            failed_products=process_result["failed_products"],
            mapping_success_rate=process_result["mapping_success_rate"],
            processing_time_seconds=process_result["processing_time_seconds"],
            processed_at=process_result["processed_at"],
            
            # 미리보기 데이터
            original_data_preview=process_result.get("original_data_preview"),
            processed_data_preview=process_result.get("processed_data_preview")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"엑셀 업로드 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{customer_id}/products", response_model=List[CustomerProductResponse])
async def get_customer_products(
    customer_id: str,
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객의 가입상품 목록을 조회합니다.
    
    - **customer_id**: 조회할 고객의 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    
    기능:
    - 특정 고객의 모든 가입상품 조회
    - 설계사 권한 체크 (user_id 제공 시)
    - 상품별 상세 정보 제공
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 가입상품 조회
        from app.db_models import CustomerProduct
        from sqlalchemy import select
        
        products_stmt = select(CustomerProduct).where(CustomerProduct.customer_id == customer.customer_id)
        products_result = await db.execute(products_stmt)
        customer_products = products_result.scalars().all()
        
        # 응답 데이터 구성
        from app.models.main_models import CustomerProductResponse
        products_response = []
        for product in customer_products:
            products_response.append(CustomerProductResponse(
                product_id=str(product.product_id),
                product_name=product.product_name,
                coverage_amount=product.coverage_amount,
                subscription_date=product.subscription_date.date() if product.subscription_date else None,
                expiry_renewal_date=product.expiry_renewal_date.date() if product.expiry_renewal_date else None,
                auto_transfer_date=product.auto_transfer_date,
                policy_issued=product.policy_issued or False,
                created_at=product.created_at,
                updated_at=product.updated_at
            ))
        
        return products_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"가입상품 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/{customer_id}/products", response_model=CustomerProductResponse)
async def create_customer_product(
    customer_id: str,
    request: CustomerProductCreate,
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객의 가입상품을 추가합니다.
    
    - **customer_id**: 고객 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    - 요청 본문에 가입상품 정보 포함
    
    기능:
    - 새로운 가입상품 생성
    - 설계사 권한 체크
    - 데이터 검증 및 변환
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 가입상품 생성
        from app.db_models import CustomerProduct
        import uuid
        
        new_product = CustomerProduct(
            product_id=uuid.uuid4(),
            customer_id=customer.customer_id,
            product_name=request.product_name,
            coverage_amount=request.coverage_amount,
            subscription_date=request.subscription_date,
            expiry_renewal_date=request.expiry_renewal_date,
            auto_transfer_date=request.auto_transfer_date,
            policy_issued=request.policy_issued or False
        )
        
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)
        
        # 응답 데이터 구성
        return CustomerProductResponse(
            product_id=str(new_product.product_id),
            product_name=new_product.product_name,
            coverage_amount=new_product.coverage_amount,
            subscription_date=new_product.subscription_date.date() if new_product.subscription_date else None,
            expiry_renewal_date=new_product.expiry_renewal_date.date() if new_product.expiry_renewal_date else None,
            auto_transfer_date=new_product.auto_transfer_date,
            policy_issued=new_product.policy_issued or False,
            created_at=new_product.created_at,
            updated_at=new_product.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"가입상품 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.put("/{customer_id}/products/{product_id}", response_model=CustomerProductResponse)
async def update_customer_product(
    customer_id: str,
    product_id: str,
    request: CustomerProductCreate,
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객의 가입상품을 수정합니다.
    
    - **customer_id**: 고객 ID
    - **product_id**: 수정할 가입상품 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    - 요청 본문에 수정할 가입상품 정보 포함
    
    기능:
    - 기존 가입상품 수정
    - 설계사 권한 체크
    - 부분 업데이트 지원
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 가입상품 존재 여부 확인
        from app.db_models import CustomerProduct
        from sqlalchemy import select, update
        import uuid
        
        try:
            product_uuid = uuid.UUID(product_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 상품 ID 형식입니다."
            )
        
        product_stmt = select(CustomerProduct).where(
            CustomerProduct.product_id == product_uuid,
            CustomerProduct.customer_id == customer.customer_id
        )
        product_result = await db.execute(product_stmt)
        existing_product = product_result.scalar_one_or_none()
        
        if not existing_product:
            raise HTTPException(
                status_code=404,
                detail=f"상품 ID {product_id}를 찾을 수 없습니다."
            )
        
        # 가입상품 수정 (null이 아닌 필드만 업데이트)
        update_data = {}
        if request.product_name is not None:
            update_data["product_name"] = request.product_name
        if request.coverage_amount is not None:
            update_data["coverage_amount"] = request.coverage_amount
        if request.subscription_date is not None:
            update_data["subscription_date"] = request.subscription_date
        if request.expiry_renewal_date is not None:
            update_data["expiry_renewal_date"] = request.expiry_renewal_date
        if request.auto_transfer_date is not None:
            update_data["auto_transfer_date"] = request.auto_transfer_date
        if request.policy_issued is not None:
            update_data["policy_issued"] = request.policy_issued
        
        if update_data:
            update_stmt = update(CustomerProduct).where(
                CustomerProduct.product_id == product_uuid
            ).values(**update_data)
            
            await db.execute(update_stmt)
            await db.commit()
        
        # 업데이트된 상품 조회
        updated_product_result = await db.execute(product_stmt)
        updated_product = updated_product_result.scalar_one()
        
        # 응답 데이터 구성
        return CustomerProductResponse(
            product_id=str(updated_product.product_id),
            product_name=updated_product.product_name,
            coverage_amount=updated_product.coverage_amount,
            subscription_date=updated_product.subscription_date.date() if updated_product.subscription_date else None,
            expiry_renewal_date=updated_product.expiry_renewal_date.date() if updated_product.expiry_renewal_date else None,
            auto_transfer_date=updated_product.auto_transfer_date,
            policy_issued=updated_product.policy_issued or False,
            created_at=updated_product.created_at,
            updated_at=updated_product.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"가입상품 수정 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{customer_id}/products/{product_id}")
async def delete_customer_product(
    customer_id: str,
    product_id: str,
    user_id: Optional[int] = Query(None, description="설계사 ID (권한 체크용)"),
    db: AsyncSession = Depends(get_db)
):
    """
    고객의 가입상품을 삭제합니다.
    
    - **customer_id**: 고객 ID
    - **product_id**: 삭제할 가입상품 ID
    - **user_id**: 설계사 ID (권한 체크용, 선택사항)
    
    기능:
    - 기존 가입상품 삭제
    - 설계사 권한 체크
    - 데이터 무결성 보장
    """
    try:
        # 먼저 고객 존재 여부 확인
        customer = await customer_service.get_customer_by_id(customer_id, db)
        if not customer:
            raise HTTPException(
                status_code=404,
                detail=f"고객 ID {customer_id}를 찾을 수 없습니다."
            )
        
        # 설계사 권한 체크 (user_id가 제공된 경우)
        if user_id and customer.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="해당 고객에 대한 접근 권한이 없습니다."
            )
        
        # 가입상품 존재 여부 확인 및 삭제
        from app.db_models import CustomerProduct
        from sqlalchemy import select, delete
        import uuid
        
        try:
            product_uuid = uuid.UUID(product_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="유효하지 않은 상품 ID 형식입니다."
            )
        
        product_stmt = select(CustomerProduct).where(
            CustomerProduct.product_id == product_uuid,
            CustomerProduct.customer_id == customer.customer_id
        )
        product_result = await db.execute(product_stmt)
        existing_product = product_result.scalar_one_or_none()
        
        if not existing_product:
            raise HTTPException(
                status_code=404,
                detail=f"상품 ID {product_id}를 찾을 수 없습니다."
            )
        
        # 가입상품 삭제
        delete_stmt = delete(CustomerProduct).where(
            CustomerProduct.product_id == product_uuid
        )
        
        await db.execute(delete_stmt)
        await db.commit()
        
        return {
            "message": f"가입상품 {product_id}가 성공적으로 삭제되었습니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"가입상품 삭제 중 오류가 발생했습니다: {str(e)}"
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