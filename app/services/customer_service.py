import os
import uuid
import pandas as pd
import openai
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.db_models import Customer, CustomerProduct, User
from app.models import CustomerCreateRequest, CustomerUpdateRequest
from app.models.main_models import CustomerProductCreate, CustomerProductResponse
from app.utils.langsmith_config import langsmith_manager, trace_llm_call, trace_excel_upload_call, get_excel_upload_llm_client
from app.utils.llm_client import llm_client_manager
from app.utils.dynamic_prompt_loader import get_column_mapping_prompt, prompt_loader
from app.models.prompt_models import PromptCategory
from datetime import datetime, date
import json
import re
import logging
import time
from collections import defaultdict
from typing import Optional, Union

logger = logging.getLogger(__name__)


class CustomerService:
    def __init__(self):
        # 싱글톤 LLM 클라이언트 매니저 사용
        self.llm_manager = llm_client_manager
        
        # 호환성을 위한 속성들 (기존 코드와의 호환성 유지)
        self.llm_client = self.llm_manager.get_chat_client()
        self.chat_model = self.llm_manager.get_chat_model_name()
        
        # Fallback용 원본 클라이언트
        self._init_fallback_client()
        
        logger.info("✅ CustomerService 초기화 완료 (싱글톤 클라이언트 사용)")
    
    def _init_fallback_client(self):
        """Fallback용 원본 클라이언트 초기화"""
        api_type = os.getenv("OPENAI_API_TYPE", "openai")
        
        try:
            if api_type == "azure":
                self.client = openai.AsyncAzureOpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
                )
            else:
                self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        except Exception as e:
            logger.warning(f"⚠️  CustomerService Fallback 클라이언트 초기화 실패: {e}")
            self.client = None
        
        # 확장된 표준 고객 스키마 정의
        self.standard_schema = {
            "name": "고객 이름",
            "affiliation": "소속 (회사, 기관 등)",
            "gender": "성별",
            "date_of_birth": "생년월일",
            "interests": "관심사 (리스트)",
            "life_events": "인생 이벤트 (결혼, 출산 등)",
            "insurance_products": "보험 상품 정보",
            
            # 새로 추가된 필드들
            "customer_type": "고객 유형 (가입, 미가입)",
            "contact_channel": "고객 접점 (가족, 지역, 소개 등)",
            "phone": "전화번호",
            "resident_number": "주민번호",
            "address": "주소",
            "job_title": "직업",
            "bank_name": "계좌은행",
            "account_number": "계좌번호",
            "referrer": "소개자",
            "notes": "기타",
            
            # 가입상품 관련 필드들
            "product_name": "가입상품명",
            "coverage_amount": "가입금액",
            "subscription_date": "가입일자",
            "expiry_renewal_date": "종료일/갱신일",
            "auto_transfer_date": "자동이체일",
            "policy_issued": "증권교부여부"
        }
        
        # 동적 프롬프트 로딩을 위한 설정
        self.use_dynamic_prompts = True

    def _digits_only(self, s: Optional[str]) -> str:
        return re.sub(r'\D', '', s or '')

    def normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        """
        한국 휴대폰 번호 강제 규칙:
        - 항상 010으로 시작, 총 11자리
        - 엑셀 포맷 이슈로 '0'이 빠진 '10xxxxxxxx' 형태면 앞에 '0'을 보정
        - 형식 강제: 000-0000-0000
        """
        if not phone:
            return None
        digits = self._digits_only(phone)

        # 선행 0 누락 보정(예: 10xxxxxxxx → 010xxxxxxxx)
        if len(digits) == 10 and digits.startswith('10'):
            digits = '0' + digits

        if not (len(digits) == 11 and digits.startswith('010')):
            # 강제 규칙에 맞지 않으면 None 반환(저장 회피) 또는 raise로 바꿀 수 있음
            return None

        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"

    def normalize_gender(self, gender: Optional[str]) -> Optional[str]:
        """
        성별 정규화:
        - 남자 / 여자 중 하나로만 반환
        - 허용 변형: 남/여, M/F, male/female 등
        """
        if not gender:
            return None
        g = str(gender).strip().lower()
        if g in {"남", "남자", "m", "male"}:
            return "남자"
        if g in {"여", "여자", "f", "female"}:
            return "여자"
        return None

    def parse_date_formats(self, date_str: Optional[str]) -> Optional[date]:
        """
        날짜 파서(확장):
        - YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD, YYYYMMDD 등
        - 반환: date (시간 제거)
        """
        if not isinstance(date_str, str):
            return None
        s = date_str.strip()
        if not s:
            return None

        fmts = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
            "%Y%m%d",               # 추가
            "%d/%m/%Y", "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"
        ]
        for fmt in fmts:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    def normalize_date_to_datetime(self, val: Union[str, date, datetime, None]) -> Optional[datetime]:
        """
        입력이 str이면 위 parse_date_formats로 파싱 → datetime으로 변환
        입력이 date면 00:00:00로 결합, datetime이면 그대로
        """
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return datetime.combine(val, datetime.min.time())
        if isinstance(val, str):
            d = self.parse_date_formats(val)
            if d:
                return datetime.combine(d, datetime.min.time())
        return None

    def normalize_postcode(self, postcode: Optional[str]) -> Optional[str]:
        """
        대한민국 우편번호: 숫자 5자리만 유효
        """
        if not postcode:
            return None
        digits = self._digits_only(postcode)
        return digits if len(digits) == 5 else None

    def normalize_customer_type(self, t: Optional[str]) -> Optional[str]:
        """
        고객유형: '가입' / '미가입'만 허용
        """
        if not t:
            return None
        s = str(t).strip().lower()
        if s in {"가입", "가입자", "existing", "subscribed"}:
            return "가입"
        if s in {"미가입", "무가입", "비가입", "non", "nonsubscribed", "prospect"}:
            return "미가입"
        return None

    def normalize_contact_channel(self, ch: Optional[str]) -> Optional[str]:
        """
        접점채널 허용 집합에 정규화. 모르면 '기타'
        """
        if not ch:
            return None
        s = str(ch).strip().lower().replace(" ", "")
        mapping = {
            "가족":"가족","지역":"지역","소개":"소개","지역마케팅":"지역마케팅",
            "인바운드":"인바운드","제휴db":"제휴db","제휴DB":"제휴db","제휴":"제휴db",
            "단체계약":"단체계약","방카":"방카","개척":"개척","기타":"기타"
        }
        return mapping.get(s, "기타")

    def normalize_account_number(self, acc: Optional[str]) -> Optional[str]:
        """
        계좌번호: 공백 제거, 숫자/하이픈 외 제거.
        카드번호(16자리 연속숫자)로 보이는 값은 None 처리(오인 방지).
        """
        if not acc:
            return None
        cleaned = re.sub(r"[^0-9\-]", "", acc)
        digits = self._digits_only(cleaned)
        if len(digits) == 16:
            return None  # 카드번호로 오인 가능 값 방지
        return cleaned or None

    def mask_resident_number(self, resident_number: Optional[str]) -> Optional[str]:
        """
        주민번호 마스킹 강화: 13자리만 유효, 999999-1****** 포맷으로 반환
        """
        if not resident_number:
            return None
        digits = self._digits_only(resident_number)
        if len(digits) != 13:
            return None
        return f"{digits[:6]}-{digits[6]}{'*' * 6}"


    def validate_policy_issued(self, value: str) -> bool:
        """증권교부여부를 불린으로 변환합니다."""
        if not value or not isinstance(value, str):
            return False
        
        value = value.strip().lower()
        true_values = ['y', 'yes', '예', '발급', '완료', 'true', '1', 'o', 'ok']
        return value in true_values

    def extract_product_fields(self, row_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """행 데이터에서 가입상품 정보를 추출합니다."""
        products = []
        
        # 단일 상품 정보 추출
        product_data = {}
        for field in ['product_name', 'coverage_amount', 'subscription_date', 'expiry_renewal_date', 'auto_transfer_date', 'policy_issued']:
            if field in row_data and row_data[field]:
                product_data[field] = row_data[field]
        
        if product_data.get('product_name'):
            products.append(product_data)
        
        # 여러 상품이 있는 경우 처리 (product_name_1, product_name_2 등)
        i = 1
        while True:
            product_data = {}
            has_data = False
            
            for field in ['product_name', 'coverage_amount', 'subscription_date', 'expiry_renewal_date', 'auto_transfer_date', 'policy_issued']:
                field_with_suffix = f"{field}_{i}"
                if field_with_suffix in row_data and row_data[field_with_suffix]:
                    product_data[field] = row_data[field_with_suffix]
                    has_data = True
            
            if not has_data or not product_data.get('product_name'):
                break
                
            products.append(product_data)
            i += 1
        
        return products

    async def create_customer(self, customer_data: CustomerCreateRequest, db_session: AsyncSession) -> Customer:
        """
        새 고객을 생성합니다 (확장된 필드 및 가입상품 지원).
        """
        try:
            # 설계사 ID 검증
            if customer_data.user_id:
                user_stmt = select(User).where(User.id == customer_data.user_id)
                user_result = await db_session.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if not user:
                    raise Exception(f"설계사 ID {customer_data.user_id}를 찾을 수 없습니다.")

            date_of_birth_dt = self.normalize_date_to_datetime(customer_data.date_of_birth)
            phone = self.normalize_phone(customer_data.phone)
            resident_number = self.mask_resident_number(customer_data.resident_number)
            normalized_gender = self.normalize_gender(customer_data.gender)
            customer_type = self.normalize_customer_type(customer_data.customer_type)
            contact_channel = self.normalize_contact_channel(customer_data.contact_channel)
            account_number = self.normalize_account_number(customer_data.account_number)

            # Customer 객체 생성 (모든 새로운 필드 포함)
            customer = Customer(
                customer_id=uuid.uuid4(),
                user_id=customer_data.user_id,
                name=customer_data.name,
                affiliation=customer_data.affiliation,
                gender=normalized_gender,
                date_of_birth=date_of_birth_dt,
                interests=customer_data.interests or [],
                life_events=customer_data.life_events or [],
                insurance_products=customer_data.insurance_products or [],
                
                # 새로 추가된 필드들
                customer_type=customer_data.customer_type,
                contact_channel=customer_data.contact_channel,
                phone=phone,
                resident_number=resident_number,
                address=customer_data.address,
                job_title=customer_data.job_title,
                bank_name=customer_data.bank_name,
                account_number=customer_data.account_number,
                referrer=customer_data.referrer,
                notes=customer_data.notes
            )

            db_session.add(customer)
            await db_session.flush()  # 고객 ID 생성을 위해 flush

            # 가입상품 생성
            if customer_data.products:
                for product_data in customer_data.products:
                    try:
                        # 상품 데이터 검증
                        subscription_date = None
                        expiry_renewal_date = None
                        
                        if product_data.subscription_date:
                            if isinstance(product_data.subscription_date, date):
                                subscription_date = datetime.combine(product_data.subscription_date, datetime.min.time())
                        
                        if product_data.expiry_renewal_date:
                            if isinstance(product_data.expiry_renewal_date, date):
                                expiry_renewal_date = datetime.combine(product_data.expiry_renewal_date, datetime.min.time())
                        
                        # CustomerProduct 객체 생성
                        product = CustomerProduct(
                            product_id=uuid.uuid4(),
                            customer_id=customer.customer_id,
                            product_name=product_data.product_name,
                            coverage_amount=product_data.coverage_amount,
                            subscription_date=subscription_date,
                            expiry_renewal_date=expiry_renewal_date,
                            auto_transfer_date=product_data.auto_transfer_date,
                            policy_issued=product_data.policy_issued or False
                        )
                        
                        db_session.add(product)
                        
                    except Exception as product_error:
                        logger.warning(f"상품 생성 중 오류 (고객 {customer.customer_id}): {str(product_error)}")
                        # 상품 생성 실패해도 고객 생성은 계속 진행

            await db_session.commit()
            await db_session.refresh(customer)

            return customer

        except Exception as e:
            await db_session.rollback()
            raise Exception(f"고객 생성 중 오류가 발생했습니다: {str(e)}")

    async def get_customer_by_id(self, customer_id: str, db_session: AsyncSession) -> Optional[Customer]:
        """
        고객 ID로 고객 정보를 조회합니다.
        """
        try:
            stmt = select(Customer).where(Customer.customer_id == uuid.UUID(customer_id))
            result = await db_session.execute(stmt)
            customer = result.scalar_one_or_none()
            return customer

        except Exception as e:
            raise Exception(f"고객 조회 중 오류가 발생했습니다: {str(e)}")

    async def update_customer(self, customer_id: str, customer_data: CustomerUpdateRequest, db_session: AsyncSession) -> Customer:
        """
        고객 정보를 업데이트합니다.
        """
        try:
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")

            # 업데이트할 필드들 처리
            update_data = customer_data.model_dump(exclude_unset=True)

            for field, value in update_data.items():
                if field == "date_of_birth":
                    value = self.normalize_date_to_datetime(value)
                elif field == "phone":
                    value = self.normalize_phone(value)
                elif field == "resident_number":
                    value = self.mask_resident_number(value)
                elif field == "gender":
                    value = self.normalize_gender(value)
                elif field == "customer_type":
                    value = self.normalize_customer_type(value)
                elif field == "contact_channel":
                    value = self.normalize_contact_channel(value)
                elif field == "account_number":
                    value = self.normalize_account_number(value)

                setattr(customer, field, value)

            await db_session.commit()
            await db_session.refresh(customer)

            return customer

        except Exception as e:
            await db_session.rollback()
            raise Exception(f"고객 업데이트 중 오류가 발생했습니다: {str(e)}")

    async def search_customers(self, query: str, db_session: AsyncSession, limit: int = 50) -> List[Customer]:
        """
        고객을 검색합니다 (이름, 연락처, 소속 등으로).
        """
        try:
            # 검색 조건 구성
            search_conditions = [
                Customer.name.ilike(f"%{query}%"),
                Customer.phone.ilike(f"%{query}%"),
                Customer.affiliation.ilike(f"%{query}%"),
            ]

            stmt = select(Customer).where(
                or_(*search_conditions)
            ).limit(limit).order_by(Customer.updated_at.desc())

            result = await db_session.execute(stmt)
            customers = result.scalars().all()

            return customers

        except Exception as e:
            raise Exception(f"고객 검색 중 오류가 발생했습니다: {str(e)}")

    @trace_excel_upload_call("excel_column_mapping", metadata={"operation": "column_mapping"})
    async def map_excel_columns(self, excel_columns: List[str], user_session: str = None, db_session: AsyncSession = None, custom_prompt: str = None) -> Dict[str, Any]:
        """
        LLM을 사용하여 엑셀 컬럼명을 표준 스키마로 매핑합니다. (동적 프롬프트 지원)
        """
        try:
            logger.info(f"엑셀 컬럼 매핑 시작: {excel_columns}")
            start_time = time.time()
            
            # 프롬프트 결정
            if custom_prompt:
                # 사용자 제공 커스텀 프롬프트 사용
                user_prompt = f"""{custom_prompt}"""
            elif self.use_dynamic_prompts:
                user_prompt = await get_column_mapping_prompt(
                    excel_columns, 
                    self.standard_schema, 
                    user_session, 
                    db_session
                )
            else:
                # 폴백 프롬프트 (하드코딩) - 더 구체적이고 명확한 매핑 가이드
                user_prompt = f"""당신은 보험설계사의 고객 엑셀 데이터를 분석하는 전문가입니다.
다음 엑셀 컬럼들을 표준 필드와 정확히 매핑해주세요.

엑셀 컬럼: {excel_columns}

매핑 규칙:
- 성명, 고객명, 이름, 고객이름 → name
- 전화, 연락처, 핸드폰, 핸드폰번호, 전화번호 → phone
- 회사, 소속, 직장, 기관 → affiliation
- 성별 → gender
- 생년월일, 생일, 출생일 → date_of_birth
- 관심사, 취미, 관심분야 → interests
- 인생이벤트, 생활이벤트, 이벤트 → life_events
- 보험상품정보, 기존보험, 보유보험 → insurance_products
- 분류, 유형, 고객유형 → customer_type
- 경로, 접점, 채널 → contact_channel
- 핸드폰, 전화번호, 휴대폰 → phone (전화번호 전용)
- 주민등록번호, 주민번호 → resident_number
- 거주지, 주소 → address
- 직장, 직업 → job_title
- 보험상품, 상품명, 가입상품, 보험명 → product_name
- 보장액, 가입금액, 보장금액 → coverage_amount
- 계약일, 가입일 → subscription_date
- 갱신일, 만료일, 종료일 → expiry_renewal_date
- 이체일, 납입일 → auto_transfer_date
- 증권발급, 증권교부 → policy_issued
- 은행, 계좌은행 → bank_name
- 계좌, 계좌번호 → account_number
- 소개자, 추천인 → referrer

정확히 JSON 형식으로만 응답해주세요:
{{
  "mapping": {{
    "성명": "name",
    "전화번호": "phone",
    "회사": "affiliation",
    "성별": "gender",
    "생년월일": "date_of_birth",
    "관심사": "interests",
    "인생이벤트": "life_events",
    "보험상품정보": "insurance_products",
    "분류": "customer_type",
    "경로": "contact_channel",
    "거주지": "address",
    "직장": "job_title",
    "보험상품": "product_name",
    "보장액": "coverage_amount",
    "계약일": "subscription_date",
    "갱신일": "expiry_renewal_date",
    "이체일": "auto_transfer_date",
    "증권발급": "policy_issued",
    "은행": "bank_name",
    "계좌": "account_number",
    "소개자": "referrer"
  }},
  "confidence_score": 0.95
}}

휴대폰 번호

한국 휴대폰 번호는 항상 010으로 시작하며 총 11자리 숫자다.
엑셀 포맷으로 인해 맨 앞 0이 생략될 수 있으니, 10으로 시작하는 경우 앞에 0을 보정한 뒤 해석한다.
휴대폰/전화 관련 컬럼은 모두 phone으로 매핑한다.

성별

성별은 반드시 ‘남자’ 또는 ‘여자’ 중 하나로만 해석·정규화한다(남/여, M/F 등은 각각 남자/여자로 변환 가정).

생년월일

YYYY-MM-DD 또는 YYYYMMDD 포맷으로 주어지는 경우가 많다.
포맷에 구애받지 말고 날짜 의미를 인식해 date_of_birth로 매핑한다.

우편번호

대한민국 우편번호는 항상 숫자 5자리다. 이 패턴을 가진 컬럼은 주소 보조 정보로 인식한다(필드가 따로 없다면 address로 통합 가능).

불필요/민감 데이터

주민등록번호는 resident_number로 매핑하되, 마스킹 전제(예: 999999-1****)**로 다뤄야 한다.
계좌번호·은행명은 각각 account_number, bank_name으로 매핑한다(숫자·하이픈 혼재 가능).

출력 형식

정확한 JSON만 응답. mapping 키는 “원본 컬럼명 → 표준 필드명” 딕셔너리여야 하고, 매핑 불가 항목은 "unmapped"로 표기한다.
confidence_score(0~1)를 포함한다.

name

한글·영문 이름 필드(예: 성명, 고객명, 영문명 등)는 name으로 매핑. 이메일 주소나 회사명이 섞여 있으면 name으로 매핑하지 말 것.

affiliation

회사/기관/부서/직장명은 affiliation. 개인 주소와 혼동 금지.

gender

입력 변형(남/여, M/F, male/female)은 남자/여자로 정규화 가정.

date_of_birth

YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD, YYYY.MM.DD 등 다양한 표기를 생년월일 의미면 date_of_birth로 매핑.
나이(만 35세 등)만 있으면 unmapped로 두고, 별도 파생 로직 대상.

interests

쉼표·슬래시 구분 목록이면 리스트로 간주. 단일 문자열만 있으면 단일 항목 리스트로 가정 가능.

life_events

결혼/출산/이사/취업/승진/퇴직/자녀진학 등 이벤트성 텍스트는 life_events로. 날짜·메모가 함께 있으면 하나의 객체로 해석(가능하면 (event, date, note) 구조를 상정).

insurance_products

“보유/기존 보험” 같은 요약형은 insurance_products로. 구체 항목(상품명·가입금액·일자)이 분리돼 있으면 product 필드들로 각각 매핑.

customer_type

값은 **‘가입’ / ‘미가입’**만. 유사표현(가입자/무가입/잠재/관심)은 의미상 매핑하되 애매하면 unmapped.

contact_channel

허용값: 가족, 지역, 소개, 지역마케팅, 인바운드, 제휴db, 단체계약, 방카, 개척, 기타. 대소문자/공백/하이픈/혼용은 동의어로 인식.

phone

**휴대폰 번호(010 + 8자리)**를 phone으로 매핑.
하이픈 유무와 공백은 무시(정규화 전제).

resident_number

13자리 숫자(하이픈 포함 가능)는 주민등록번호로 간주. LLM은 매핑만 하고, 마스킹은 서버에서 처리됨을 가정.

address

시/구/동/도로명/우편번호가 섞인 문자열은 address.
우편번호(5자리 숫자)만 단독 컬럼이면 address 보조로 보되, 컬럼명·내용이 모호하면 unmapped.

job_title

직책/직무(과장, 대리, 엔지니어 등)는 job_title. 회사명과 혼동 금지(회사명=affiliation).

bank_name / account_number

은행명은 bank_name(국문/영문/약칭 모두 허용), 숫자 위주 문자열은 account_number.
카드번호(16자리 패턴)는 account_number로 매핑하지 말 것(unmapped).

referrer

소개자/추천인/지인 이름은 referrer.

notes

위 어느 스키마에도 맞지 않는 자유 서술형 메모는 notes로.
"""

            # 엑셀 업로드 전용 LangChain 클라이언트 사용
            excel_llm_client = get_excel_upload_llm_client()
            if excel_llm_client:
                # LangSmith가 활성화된 경우, 엑셀 업로드 전용 클라이언트 사용
                logger.info(f"🔍 엑셀 업로드 LLM 클라이언트 사용 - 프로젝트: {langsmith_manager.get_excel_upload_project_name()}")
                response = await excel_llm_client.ainvoke(user_prompt)
            else:
                # LangSmith가 비활성화된 경우, 기본 클라이언트 사용
                logger.info("⚠️ 기본 LLM 클라이언트 사용 (LangSmith 비활성화)")
                response = await self.llm_client.ainvoke(user_prompt)
            result_text = response.content
            
            # JSON 파싱 (마크다운 코드 블록 제거)
            try:
                logger.info(f"LLM 응답 원본: {result_text}")
                
                # 마크다운 코드 블록 제거
                clean_text = result_text
                if '```json' in result_text and '```' in result_text:
                    # ```json과 ``` 사이의 내용 추출
                    import re
                    json_pattern = r'```json\s*(.*?)\s*```'
                    match = re.search(json_pattern, result_text, re.DOTALL)
                    if match:
                        clean_text = match.group(1).strip()
                        logger.info(f"마크다운 코드 블록에서 JSON 추출: {clean_text}")
                
                result = json.loads(clean_text)
                
                # 검증 및 기본값 설정 (mapping/mappings, confidence_score/confidence 모두 지원)
                mapping = result.get("mapping", result.get("mappings", {}))
                confidence_score = result.get("confidence_score", result.get("confidence", 0.5))
                
                # unmapped 컬럼들 추출
                unmapped_columns = [
                    col for col, mapped_field in mapping.items() 
                    if mapped_field == "unmapped"
                ]
                
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                logger.info(f"엑셀 컬럼 매핑 완료: 신뢰도 {confidence_score}")
                
                final_result = {
                    "mapping": mapping,
                    "unmapped_columns": unmapped_columns,
                    "confidence_score": min(max(confidence_score, 0.0), 1.0)
                }
                
                # A/B 테스트 결과 기록 (동적 프롬프트 사용 시)
                if self.use_dynamic_prompts and user_session:
                    try:
                        await prompt_loader.record_usage_result(
                            category=PromptCategory.COLUMN_MAPPING,
                            user_session=user_session,
                            input_data={"excel_columns": excel_columns, "standard_schema": self.standard_schema},
                            output_data=final_result,
                            response_time_ms=response_time_ms,
                            success=True,
                            quality_score=confidence_score,
                            db=db_session
                        )
                    except Exception as e:
                        logger.warning(f"A/B 테스트 결과 기록 실패: {e}")
                
                return final_result

            except json.JSONDecodeError:
                # JSON 파싱 실패 시 정규식으로 JSON 추출 시도
                logger.warning("JSON 파싱 실패, 정규식으로 JSON 추출 시도")
                import re
                
                # JSON 패턴 찾기
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                json_matches = re.findall(json_pattern, result_text, re.DOTALL)
                
                for json_str in json_matches:
                    try:
                        result = json.loads(json_str)
                        if "mapping" in result or "mappings" in result:
                            mapping = result.get("mapping", result.get("mappings", {}))
                            confidence_score = result.get("confidence_score", result.get("confidence", 0.5))
                            
                            unmapped_columns = [
                                col for col, mapped_field in mapping.items() 
                                if mapped_field == "unmapped"
                            ]
                            
                            logger.info(f"정규식으로 JSON 추출 성공: {len(mapping)}개 컬럼 매핑")
                            return {
                                "mapping": mapping,
                                "unmapped_columns": unmapped_columns,
                                "confidence_score": min(max(confidence_score, 0.0), 1.0)
                            }
                    except:
                        continue
                
                # 모든 시도 실패 시 기본 매핑 반환
                logger.warning("모든 JSON 파싱 시도 실패, 기본 매핑 반환")
                return {
                    "mapping": {col: "unmapped" for col in excel_columns},
                    "unmapped_columns": excel_columns,
                    "confidence_score": 0.0
                }

        except Exception as e:
            raise Exception(f"컬럼 매핑 중 오류가 발생했습니다: {str(e)}")

    @trace_excel_upload_call("excel_data_processing", metadata={"operation": "data_processing"})
    async def process_excel_data(self, df: pd.DataFrame, column_mapping: Dict[str, str], user_id: int, db_session: AsyncSession) -> Dict[str, Any]:
        """
        엑셀 데이터를 처리하여 고객 데이터를 생성/업데이트합니다.
        확장된 기능: 설계사별 처리, 가입상품 처리, 데이터 검증, 트랜잭션 처리
        """
        start_time = time.time()
        
        # 통계 변수들
        processed_rows = 0
        created_customers = 0
        updated_customers = 0
        total_products = 0
        created_products = 0
        failed_products = 0
        errors = []
        
        # 필드별 매핑 성공률 추적
        mapping_success_rate = {}
        field_attempts = defaultdict(int)
        field_successes = defaultdict(int)
        
        # 고객별 데이터 그룹화 (여러 행에 걸친 동일 고객 처리)
        customer_groups = defaultdict(list)
        
        try:
            # 설계사 존재 확인
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db_session.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                raise Exception(f"설계사 ID {user_id}를 찾을 수 없습니다.")
            
            logger.info(f"엑셀 데이터 처리 시작: 설계사 {user_id}, 총 {len(df)} 행")
            
            # 1단계: 데이터 추출 및 그룹화
            for index, row in df.iterrows():
                try:
                    # 매핑된 데이터 추출
                    row_data = self._extract_row_data(row, column_mapping, df.columns, index, field_attempts, field_successes)
                    
                    if not row_data:
                        continue
                        
                    # 고객 식별자 생성 (이름 + 전화번호 또는 주민번호)
                    customer_key = self._generate_customer_key(row_data)
                    if customer_key:
                        customer_groups[customer_key].append((index, row_data))
                    
                    processed_rows += 1
                    
                except Exception as e:
                    errors.append(f"행 {index + 2} 데이터 추출 오류: {str(e)}")
                    continue
            
            logger.info(f"데이터 추출 완료: {len(customer_groups)} 고객 그룹")
            
            # 2단계: 고객 및 상품 처리
            for customer_key, row_data_list in customer_groups.items():
                try:
                    # 고객 데이터 통합
                    merged_customer_data, products_data = self._merge_customer_data(row_data_list, user_id)
                    
                    # 기존 고객 확인 (중복 체크)
                    existing_customer = await self._find_existing_customer(merged_customer_data, user_id, db_session)
                    
                    if existing_customer:
                        # 기존 고객 업데이트
                        await self._update_existing_customer(existing_customer, merged_customer_data, db_session)
                        customer = existing_customer
                        updated_customers += 1
                    else:
                        # 새 고객 생성
                        customer = await self._create_new_customer(merged_customer_data, db_session)
                        created_customers += 1
                    
                    # 가입상품 처리
                    product_results = await self._process_customer_products(
                        customer, products_data, db_session
                    )
                    total_products += product_results['total']
                    created_products += product_results['created']
                    failed_products += product_results['failed']
                    
                    if product_results['errors']:
                        errors.extend(product_results['errors'])
                        
                except Exception as e:
                    errors.append(f"고객 {customer_key} 처리 오류: {str(e)}")
                    continue
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            # 필드별 매핑 성공률 계산
            for field in field_attempts:
                if field_attempts[field] > 0:
                    mapping_success_rate[field] = field_successes[field] / field_attempts[field]
            
            logger.info(f"엑셀 데이터 처리 완료: {created_customers}명 생성, {updated_customers}명 업데이트, {created_products}개 상품 생성")
            
            # 데이터 미리보기 생성
            try:
                original_data_preview = self._generate_original_data_preview(df, column_mapping)
                logger.info(f"원본 데이터 미리보기 생성됨: {len(original_data_preview.get('preview_rows', [])) if original_data_preview else 0} 행")
            except Exception as e:
                logger.error(f"원본 데이터 미리보기 생성 실패: {str(e)}")
                original_data_preview = None
                
            try:
                processed_data_preview = await self._generate_processed_data_preview(user_id, db_session)
                logger.info(f"처리된 데이터 미리보기 생성됨: 고객 {processed_data_preview.get('customers', {}).get('count', 0)}명, 상품 {processed_data_preview.get('products', {}).get('count', 0)}개")
            except Exception as e:
                logger.error(f"처리된 데이터 미리보기 생성 실패: {str(e)}")
                processed_data_preview = None
            
            result = {
                "success": True,
                "processed_rows": processed_rows,
                "created_customers": created_customers,
                "updated_customers": updated_customers,
                "errors": errors,
                "total_products": total_products,
                "created_products": created_products,
                "failed_products": failed_products,
                "mapping_success_rate": mapping_success_rate,
                "processing_time_seconds": round(processing_time, 2),
                "processed_at": datetime.now(),
                "original_data_preview": original_data_preview,
                "processed_data_preview": processed_data_preview
            }
            
            # 미리보기 데이터 상태를 로그로 기록 (LangSmith에는 추적되지만 브라우저에서도 확인 가능)
            preview_info = {
                "original_preview_available": original_data_preview is not None,
                "original_rows_count": len(original_data_preview.get('preview_rows', [])) if original_data_preview else 0,
                "processed_preview_available": processed_data_preview is not None,
                "processed_customers_count": processed_data_preview.get('customers', {}).get('count', 0) if processed_data_preview else 0,
                "processed_products_count": processed_data_preview.get('products', {}).get('count', 0) if processed_data_preview else 0
            }
            logger.info(f"📊 미리보기 데이터 상태: {preview_info}")
            
            return result

        except Exception as e:
            logger.error(f"엑셀 데이터 처리 중 심각한 오류: {str(e)}")
            raise Exception(f"엑셀 데이터 처리 중 오류가 발생했습니다: {str(e)}")
    
    def _extract_row_data(self, row, column_mapping: Dict[str, str], df_columns, index: int, 
                         field_attempts: defaultdict, field_successes: defaultdict) -> Dict[str, Any]:
        """행에서 데이터를 추출하고 검증합니다."""
        row_data = {}
        
        for excel_col, standard_field in column_mapping.items():
            if standard_field == "unmapped" or excel_col not in df_columns:
                continue
            
            value = row[excel_col]
            field_attempts[standard_field] += 1
            
            # 빈 값 처리
            if pd.isna(value) or value == "":
                continue
            
            try:
                # 데이터 타입별 처리 및 검증
                processed_value = self._process_field_value(standard_field, value)
                if processed_value is not None:
                    row_data[standard_field] = processed_value
                    field_successes[standard_field] += 1
                    
            except Exception as e:
                logger.warning(f"행 {index + 2}, 필드 {standard_field} 처리 실패: {str(e)}")
        
        return row_data
    
    def _process_field_value(self, field_name: str, value: Any) -> Any:
        """필드별 데이터 처리 및 검증"""
        if pd.isna(value) or value == "":
            return None
            
        str_value = str(value).strip()
        
        # 전화번호 처리
        if field_name == "phone":
            return self.normalize_phone(str_value)
        
        # 주민번호 처리
        elif field_name == "resident_number":
            return self.mask_resident_number(str_value)
        
        # 성별 처리
        elif field_name == "gender":
            return self.normalize_gender(str_value)
        
        # 날짜 필드 처리
        elif field_name in ["date_of_birth", "subscription_date", "expiry_renewal_date"]:
            return self.parse_date_formats(str_value)
        
        # 불린 필드 처리
        elif field_name == "policy_issued":
            return self.validate_policy_issued(str_value)
        
        # 리스트 필드 처리
        elif field_name in ["interests", "life_events", "insurance_products"]:
            if str_value.startswith('[') or str_value.startswith('{'):
                try:
                    return json.loads(str_value)
                except:
                    pass
            return [item.strip() for item in str_value.split(',') if item.strip()]
        
        # 기본 문자열 처리
        else:
            return str_value
    
    def _generate_customer_key(self, row_data: Dict[str, Any]) -> Optional[str]:
        """고객 식별을 위한 키 생성"""
        name = row_data.get('name', '').strip()
        phone = row_data.get('phone', '').strip()
        resident_number = row_data.get('resident_number', '').strip()
        
        if name and (phone or resident_number):
            return f"{name}_{phone or resident_number}"
        
        return None
    
    def _merge_customer_data(self, row_data_list: List[Tuple[int, Dict[str, Any]]], user_id: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """여러 행의 고객 데이터를 통합하고 상품 데이터를 분리합니다."""
        customer_data = {"user_id": user_id}
        products_data = []
        
        # 고객 필드들
        customer_fields = {'name', 'affiliation', 'gender', 'date_of_birth',
                          'interests', 'life_events', 'insurance_products', 'customer_type', 
                          'contact_channel', 'phone', 'resident_number', 'address', 'job_title',
                          'bank_name', 'account_number', 'referrer', 'notes'}
        
        # 상품 필드들
        product_fields = {'product_name', 'coverage_amount', 'subscription_date', 
                         'expiry_renewal_date', 'auto_transfer_date', 'policy_issued'}
        
        for index, row_data in row_data_list:
            # 고객 데이터 통합 (첫 번째로 발견된 값 우선)
            for field in customer_fields:
                if field in row_data and field not in customer_data:
                    customer_data[field] = row_data[field]
            
            # 상품 데이터 추출
            product_data = {}
            for field in product_fields:
                if field in row_data and row_data[field]:
                    product_data[field] = row_data[field]
            
            # 상품명이 있는 경우만 상품으로 처리
            if product_data.get('product_name'):
                product_data['source_row'] = index + 2  # 엑셀 행 번호
                products_data.append(product_data)
        
        return customer_data, products_data
    
    async def _find_existing_customer(self, customer_data: Dict[str, Any], user_id: int, db_session: AsyncSession) -> Optional[Customer]:
        """기존 고객 찾기 (중복 체크)"""
        conditions = []
        
        # 이름과 전화번호로 찾기
        if customer_data.get('name') and customer_data.get('phone'):
            conditions.append(
                and_(
                    Customer.user_id == user_id,
                    Customer.name == customer_data['name'],
                    Customer.phone == customer_data['phone']
                )
            )
        
        # 이름과 주민번호로 찾기  
        if customer_data.get('name') and customer_data.get('resident_number'):
            conditions.append(
                and_(
                    Customer.user_id == user_id,
                    Customer.name == customer_data['name'],
                    Customer.resident_number == customer_data['resident_number']
                )
            )
        
        if not conditions:
            return None
        
        stmt = select(Customer).where(or_(*conditions))
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _update_existing_customer(self, customer: Customer, customer_data: Dict[str, Any], db_session: AsyncSession):
        """기존 고객 정보 업데이트"""
        for field, value in customer_data.items():
            if field != 'user_id' and hasattr(customer, field):
                setattr(customer, field, value)
        
        customer.updated_at = datetime.now()
        await db_session.flush()
    
    async def _create_new_customer(self, customer_data: Dict[str, Any], db_session: AsyncSession) -> Customer:
        """새 고객 생성"""
        # 날짜 형식 변환
        if customer_data.get('date_of_birth') and isinstance(customer_data['date_of_birth'], date):
            customer_data['date_of_birth'] = datetime.combine(customer_data['date_of_birth'], datetime.min.time())
        
        customer = Customer(
            customer_id=uuid.uuid4(),
            **customer_data
        )
        
        db_session.add(customer)
        await db_session.flush()
        return customer
    
    async def _process_customer_products(self, customer: Customer, products_data: List[Dict[str, Any]], 
                                       db_session: AsyncSession) -> Dict[str, Any]:
        """고객의 가입상품들을 처리합니다."""
        results = {
            'total': len(products_data),
            'created': 0,
            'failed': 0,
            'errors': []
        }
        
        for product_data in products_data:
            try:
                # 중복 상품 체크
                if await self._is_duplicate_product(customer, product_data, db_session):
                    continue
                
                # 상품 데이터 정제
                clean_product_data = self._clean_product_data(product_data)
                
                # 새 상품 생성
                product = CustomerProduct(
                    product_id=uuid.uuid4(),
                    customer_id=customer.customer_id,
                    **clean_product_data
                )
                
                db_session.add(product)
                results['created'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"행 {product_data.get('source_row', '?')} 상품 처리 오류: {str(e)}")
        
        await db_session.flush()
        return results
    
    async def _is_duplicate_product(self, customer: Customer, product_data: Dict[str, Any], 
                                  db_session: AsyncSession) -> bool:
        """상품 중복 체크"""
        if not product_data.get('product_name'):
            return False
        
        stmt = select(CustomerProduct).where(
            and_(
                CustomerProduct.customer_id == customer.customer_id,
                CustomerProduct.product_name == product_data['product_name']
            )
        )
        
        # 가입일이 있는 경우 추가 조건
        if product_data.get('subscription_date'):
            stmt = stmt.where(CustomerProduct.subscription_date == product_data['subscription_date'])
        
        result = await db_session.execute(stmt)
        existing_product = result.scalar_one_or_none()
        
        return existing_product is not None
    
    def _clean_product_data(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """상품 데이터 정제"""
        clean_data = {}
        
        for field, value in product_data.items():
            if field == 'source_row':
                continue
                
            if field in ['subscription_date', 'expiry_renewal_date'] and isinstance(value, date):
                clean_data[field] = datetime.combine(value, datetime.min.time())
            elif field == 'policy_issued' and isinstance(value, str):
                clean_data[field] = self.validate_policy_issued(value)
            else:
                clean_data[field] = value
        
        return clean_data

    async def get_customer_list(self, db_session: AsyncSession, limit: int = 100, offset: int = 0) -> Tuple[List[Customer], int]:
        """
        고객 목록을 페이징하여 조회합니다.
        """
        try:
            # 전체 개수 조회
            count_stmt = select(Customer)
            count_result = await db_session.execute(count_stmt)
            total_count = len(count_result.scalars().all())

            # 페이징된 목록 조회
            stmt = select(Customer).offset(offset).limit(limit).order_by(Customer.updated_at.desc())
            result = await db_session.execute(stmt)
            customers = result.scalars().all()

            return customers, total_count

        except Exception as e:
            raise Exception(f"고객 목록 조회 중 오류가 발생했습니다: {str(e)}")

    async def delete_customer(self, customer_id: str, db_session: AsyncSession) -> bool:
        """
        고객을 삭제합니다.
        """
        try:
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")

            await db_session.delete(customer)
            await db_session.commit()

            return True

        except Exception as e:
            await db_session.rollback()
            raise Exception(f"고객 삭제 중 오류가 발생했습니다: {str(e)}")

    # ======================================
    # 가입상품 관련 메서드들
    # ======================================

    async def create_customer_product(self, customer_id: str, product_data: CustomerProductCreate, db_session: AsyncSession) -> CustomerProduct:
        """
        고객의 가입상품을 생성합니다.
        """
        try:
            # 고객 존재 여부 확인
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            
            # 중복 상품 체크
            if await self._is_duplicate_product(customer, product_data.model_dump(), db_session):
                raise Exception(f"동일한 상품이 이미 존재합니다: {product_data.product_name}")
            
            # 날짜 처리
            subscription_date = None
            expiry_renewal_date = None
            
            if product_data.subscription_date:
                subscription_date = datetime.combine(product_data.subscription_date, datetime.min.time())
            
            if product_data.expiry_renewal_date:
                expiry_renewal_date = datetime.combine(product_data.expiry_renewal_date, datetime.min.time())
            
            # 새 상품 생성
            product = CustomerProduct(
                product_id=uuid.uuid4(),
                customer_id=customer.customer_id,
                product_name=product_data.product_name,
                coverage_amount=product_data.coverage_amount,
                subscription_date=subscription_date,
                expiry_renewal_date=expiry_renewal_date,
                auto_transfer_date=product_data.auto_transfer_date,
                policy_issued=product_data.policy_issued or False
            )
            
            db_session.add(product)
            await db_session.commit()
            await db_session.refresh(product)
            
            return product
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"가입상품 생성 중 오류가 발생했습니다: {str(e)}")

    async def get_customer_products(self, customer_id: str, db_session: AsyncSession) -> List[CustomerProduct]:
        """
        고객의 모든 가입상품을 조회합니다.
        """
        try:
            # 고객 존재 여부 확인
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            
            stmt = select(CustomerProduct).where(
                CustomerProduct.customer_id == customer.customer_id
            ).order_by(CustomerProduct.created_at.desc())
            
            result = await db_session.execute(stmt)
            products = result.scalars().all()
            
            return products
            
        except Exception as e:
            raise Exception(f"가입상품 조회 중 오류가 발생했습니다: {str(e)}")

    async def update_customer_product(self, customer_id: str, product_id: str, product_data: CustomerProductCreate, db_session: AsyncSession) -> CustomerProduct:
        """
        고객의 가입상품을 수정합니다.
        """
        try:
            # 고객 존재 여부 확인
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            
            # 상품 조회
            product_uuid = uuid.UUID(product_id)
            stmt = select(CustomerProduct).where(
                and_(
                    CustomerProduct.product_id == product_uuid,
                    CustomerProduct.customer_id == customer.customer_id
                )
            )
            result = await db_session.execute(stmt)
            product = result.scalar_one_or_none()
            
            if not product:
                raise Exception(f"상품 ID {product_id}를 찾을 수 없습니다.")
            
            # 업데이트할 필드들 처리
            update_data = product_data.model_dump(exclude_unset=True)
            
            for field, value in update_data.items():
                if field in ['subscription_date', 'expiry_renewal_date'] and value:
                    if isinstance(value, date):
                        value = datetime.combine(value, datetime.min.time())
                
                setattr(product, field, value)
            
            product.updated_at = datetime.now()
            await db_session.commit()
            await db_session.refresh(product)
            
            return product
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"가입상품 수정 중 오류가 발생했습니다: {str(e)}")

    async def delete_customer_product(self, customer_id: str, product_id: str, db_session: AsyncSession) -> bool:
        """
        고객의 가입상품을 삭제합니다.
        """
        try:
            # 고객 존재 여부 확인
            customer = await self.get_customer_by_id(customer_id, db_session)
            if not customer:
                raise Exception(f"고객 ID {customer_id}를 찾을 수 없습니다.")
            
            # 상품 조회 및 삭제
            product_uuid = uuid.UUID(product_id)
            stmt = select(CustomerProduct).where(
                and_(
                    CustomerProduct.product_id == product_uuid,
                    CustomerProduct.customer_id == customer.customer_id
                )
            )
            result = await db_session.execute(stmt)
            product = result.scalar_one_or_none()
            
            if not product:
                raise Exception(f"상품 ID {product_id}를 찾을 수 없습니다.")
            
            await db_session.delete(product)
            await db_session.commit()
            
            return True
            
        except Exception as e:
            await db_session.rollback()
            raise Exception(f"가입상품 삭제 중 오류가 발생했습니다: {str(e)}")

    # ======================================
    # 고객 검색 로직 개선
    # ======================================

    async def search_customers_advanced(self, 
                                      query: Optional[str] = None,
                                      user_id: Optional[int] = None,
                                      customer_type: Optional[str] = None,
                                      contact_channel: Optional[str] = None,
                                      product_name: Optional[str] = None,
                                      limit: int = 50,
                                      offset: int = 0,
                                      db_session: AsyncSession = None) -> Tuple[List[Customer], int]:
        """
        고급 고객 검색 (설계사별, 고객유형별, 가입상품별 필터링)
        """
        try:
            base_query = select(Customer)
            count_query = select(func.count(Customer.customer_id))
            
            conditions = []
            
            # 설계사별 필터링
            if user_id:
                conditions.append(Customer.user_id == user_id)
            
            # 고객 유형별 필터링
            if customer_type:
                conditions.append(Customer.customer_type == customer_type)
            
            # 접점 채널별 필터링
            if contact_channel:
                conditions.append(Customer.contact_channel == contact_channel)
            
            # 텍스트 검색
            if query:
                search_conditions = [
                    Customer.name.ilike(f"%{query}%"),
                    Customer.phone.ilike(f"%{query}%"),
                    Customer.affiliation.ilike(f"%{query}%"),
                    Customer.address.ilike(f"%{query}%")
                ]
                conditions.append(or_(*search_conditions))
            
            # 가입상품별 검색
            if product_name:
                # 서브쿼리로 해당 상품을 가진 고객들만 필터링
                product_subquery = select(CustomerProduct.customer_id).where(
                    CustomerProduct.product_name.ilike(f"%{product_name}%")
                )
                conditions.append(Customer.customer_id.in_(product_subquery))
            
            # 조건 적용
            if conditions:
                base_query = base_query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))
            
            # 전체 개수 조회
            count_result = await db_session.execute(count_query)
            total_count = count_result.scalar()
            
            # 페이징 및 정렬 적용
            base_query = base_query.offset(offset).limit(limit).order_by(Customer.updated_at.desc())
            
            # 결과 조회
            result = await db_session.execute(base_query)
            customers = result.scalars().all()
            
            return customers, total_count
            
        except Exception as e:
            raise Exception(f"고급 고객 검색 중 오류가 발생했습니다: {str(e)}")

    # ======================================
    # 통계 메서드들
    # ======================================

    async def get_customer_statistics(self, user_id: Optional[int] = None, db_session: AsyncSession = None) -> Dict[str, Any]:
        """
        설계사별 고객 현황 통계
        """
        try:
            base_conditions = []
            if user_id:
                base_conditions.append(Customer.user_id == user_id)
            
            # 전체 고객 수
            total_query = select(func.count(Customer.customer_id))
            if base_conditions:
                total_query = total_query.where(and_(*base_conditions))
            
            total_result = await db_session.execute(total_query)
            total_customers = total_result.scalar()
            
            # 고객 유형별 분포
            type_query = select(
                Customer.customer_type,
                func.count(Customer.customer_id).label('count')
            ).group_by(Customer.customer_type)
            
            if base_conditions:
                type_query = type_query.where(and_(*base_conditions))
            
            type_result = await db_session.execute(type_query)
            customer_types = {row.customer_type or '미분류': row.count for row in type_result}
            
            # 접점 채널별 분포
            channel_query = select(
                Customer.contact_channel,
                func.count(Customer.customer_id).label('count')
            ).group_by(Customer.contact_channel)
            
            if base_conditions:
                channel_query = channel_query.where(and_(*base_conditions))
            
            channel_result = await db_session.execute(channel_query)
            contact_channels = {row.contact_channel or '미분류': row.count for row in channel_result}
            
            # 최근 등록된 고객 (30일 이내)
            recent_date = datetime.now() - pd.Timedelta(days=30)
            recent_query = select(func.count(Customer.customer_id)).where(
                Customer.created_at >= recent_date
            )
            if base_conditions:
                recent_query = recent_query.where(and_(*base_conditions))
            
            recent_result = await db_session.execute(recent_query)
            recent_customers = recent_result.scalar()
            
            return {
                "total_customers": total_customers,
                "customer_types": customer_types,
                "contact_channels": contact_channels,
                "recent_customers_30days": recent_customers,
                "statistics_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"고객 통계 조회 중 오류가 발생했습니다: {str(e)}")

    async def get_product_statistics(self, user_id: Optional[int] = None, db_session: AsyncSession = None) -> Dict[str, Any]:
        """
        가입상품별 통계
        """
        try:
            # 기본 조건 설정
            base_conditions = []
            if user_id:
                # 특정 설계사의 고객들만 필터링
                user_customers_subquery = select(Customer.customer_id).where(Customer.user_id == user_id)
                base_conditions.append(CustomerProduct.customer_id.in_(user_customers_subquery))
            
            # 전체 가입상품 수
            total_query = select(func.count(CustomerProduct.product_id))
            if base_conditions:
                total_query = total_query.where(and_(*base_conditions))
            
            total_result = await db_session.execute(total_query)
            total_products = total_result.scalar()
            
            # 상품별 가입 현황
            product_query = select(
                CustomerProduct.product_name,
                func.count(CustomerProduct.product_id).label('count')
            ).group_by(CustomerProduct.product_name).order_by(func.count(CustomerProduct.product_id).desc())
            
            if base_conditions:
                product_query = product_query.where(and_(*base_conditions))
            
            product_result = await db_session.execute(product_query)
            product_distribution = {row.product_name or '미분류': row.count for row in product_result}
            
            # 증권 발급 현황
            policy_query = select(
                CustomerProduct.policy_issued,
                func.count(CustomerProduct.product_id).label('count')
            ).group_by(CustomerProduct.policy_issued)
            
            if base_conditions:
                policy_query = policy_query.where(and_(*base_conditions))
            
            policy_result = await db_session.execute(policy_query)
            policy_status = {}
            for row in policy_result:
                key = '발급완료' if row.policy_issued else '미발급'
                policy_status[key] = row.count
            
            # 최근 가입 상품 (30일 이내)
            recent_date = datetime.now() - pd.Timedelta(days=30)
            recent_query = select(func.count(CustomerProduct.product_id)).where(
                CustomerProduct.created_at >= recent_date
            )
            if base_conditions:
                recent_query = recent_query.where(and_(*base_conditions))
            
            recent_result = await db_session.execute(recent_query)
            recent_products = recent_result.scalar()
            
            # 갱신 예정 상품 (30일 이내)
            renewal_date = datetime.now() + pd.Timedelta(days=30)
            renewal_query = select(func.count(CustomerProduct.product_id)).where(
                and_(
                    CustomerProduct.expiry_renewal_date.isnot(None),
                    CustomerProduct.expiry_renewal_date <= renewal_date,
                    CustomerProduct.expiry_renewal_date >= datetime.now()
                )
            )
            if base_conditions:
                renewal_query = renewal_query.where(and_(*base_conditions))
            
            renewal_result = await db_session.execute(renewal_query)
            renewal_products = renewal_result.scalar()
            
            return {
                "total_products": total_products,
                "product_distribution": product_distribution,
                "policy_status": policy_status,
                "recent_products_30days": recent_products,
                "renewal_due_30days": renewal_products,
                "statistics_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"상품 통계 조회 중 오류가 발생했습니다: {str(e)}")

    # ======================================
    # 비즈니스 로직 강화
    # ======================================

    async def check_duplicate_customer(self, name: str, phone: Optional[str] = None, resident_number: Optional[str] = None, user_id: Optional[int] = None, db_session: AsyncSession = None) -> List[Customer]:
        """
        중복 고객 체크
        """
        try:
            conditions = [Customer.name == name]
            
            # 설계사 필터링
            if user_id:
                conditions.append(Customer.user_id == user_id)
            
            # 전화번호 또는 주민번호로 추가 확인
            identity_conditions = []
            if phone:
                identity_conditions.append(Customer.phone == phone)
            if resident_number:
                identity_conditions.append(Customer.resident_number == resident_number)
            
            if identity_conditions:
                conditions.append(or_(*identity_conditions))
            
            stmt = select(Customer).where(and_(*conditions))
            result = await db_session.execute(stmt)
            duplicates = result.scalars().all()
            
            return duplicates
            
        except Exception as e:
            raise Exception(f"중복 고객 체크 중 오류가 발생했습니다: {str(e)}")

    async def get_renewal_alerts(self, user_id: Optional[int] = None, days_ahead: int = 30, db_session: AsyncSession = None) -> List[Dict[str, Any]]:
        """
        상품 갱신일 알림 조회
        """
        try:
            today = datetime.now().date()
            alert_date = today + pd.Timedelta(days=days_ahead)
            
            # 기본 쿼리
            query = select(CustomerProduct, Customer).join(
                Customer, CustomerProduct.customer_id == Customer.customer_id
            ).where(
                and_(
                    CustomerProduct.expiry_renewal_date.isnot(None),
                    CustomerProduct.expiry_renewal_date >= today,
                    CustomerProduct.expiry_renewal_date <= alert_date
                )
            )
            
            # 설계사 필터링
            if user_id:
                query = query.where(Customer.user_id == user_id)
            
            query = query.order_by(CustomerProduct.expiry_renewal_date.asc())
            
            result = await db_session.execute(query)
            alerts = []
            
            for product, customer in result:
                days_until_renewal = (product.expiry_renewal_date.date() - today).days
                alerts.append({
                    "customer_id": str(customer.customer_id),
                    "customer_name": customer.name,
                    "customer_phone": customer.phone,
                    "product_id": str(product.product_id),
                    "product_name": product.product_name,
                    "coverage_amount": product.coverage_amount,
                    "renewal_date": product.expiry_renewal_date.date(),
                    "days_until_renewal": days_until_renewal,
                    "priority": "high" if days_until_renewal <= 7 else "medium" if days_until_renewal <= 15 else "low"
                })
            
            return alerts
            
        except Exception as e:
            raise Exception(f"갱신 알림 조회 중 오류가 발생했습니다: {str(e)}")

    async def validate_data_quality(self, user_id: Optional[int] = None, db_session: AsyncSession = None) -> Dict[str, Any]:
        """
        데이터 품질 검증
        """
        try:
            base_conditions = []
            if user_id:
                base_conditions.append(Customer.user_id == user_id)
            
            # 전체 고객 수
            total_query = select(func.count(Customer.customer_id))
            if base_conditions:
                total_query = total_query.where(and_(*base_conditions))
            
            total_result = await db_session.execute(total_query)
            total_customers = total_result.scalar()
            
            quality_issues = {
                "missing_phone": 0,
                "missing_address": 0,
                "missing_customer_type": 0,
                "invalid_phone_format": 0,
                "missing_products": 0,
                "total_customers": total_customers
            }
            
            # 필수 정보 누락 체크
            missing_checks = [
                ("missing_phone", Customer.phone.is_(None) | (Customer.phone == "")),
                ("missing_address", Customer.address.is_(None) | (Customer.address == "")),
                ("missing_customer_type", Customer.customer_type.is_(None) | (Customer.customer_type == ""))
            ]
            
            for issue_key, condition in missing_checks:
                query = select(func.count(Customer.customer_id)).where(condition)
                if base_conditions:
                    query = query.where(and_(*base_conditions))
                
                result = await db_session.execute(query)
                quality_issues[issue_key] = result.scalar()
            
            # 전화번호 형식 체크
            phone_format_query = select(func.count(Customer.customer_id)).where(
                and_(
                    Customer.phone.isnot(None),
                    Customer.phone != "",
                    ~Customer.phone.regexp_match(r'^\d{3}-\d{4}-\d{4}$|^\d{2,3}-\d{3,4}-\d{4}$')
                )
            )
            if base_conditions:
                phone_format_query = phone_format_query.where(and_(*base_conditions))
            
            phone_format_result = await db_session.execute(phone_format_query)
            quality_issues["invalid_phone_format"] = phone_format_result.scalar()
            
            # 가입상품 없는 고객 수
            no_products_subquery = select(CustomerProduct.customer_id).distinct()
            no_products_query = select(func.count(Customer.customer_id)).where(
                Customer.customer_id.not_in(no_products_subquery)
            )
            if base_conditions:
                no_products_query = no_products_query.where(and_(*base_conditions))
            
            no_products_result = await db_session.execute(no_products_query)
            quality_issues["missing_products"] = no_products_result.scalar()
            
            # 품질 점수 계산 (0-100)
            if total_customers > 0:
                quality_score = max(0, 100 - sum([
                    (quality_issues["missing_phone"] / total_customers) * 20,
                    (quality_issues["missing_address"] / total_customers) * 15,
                    (quality_issues["missing_customer_type"] / total_customers) * 10,
                    (quality_issues["invalid_phone_format"] / total_customers) * 15,
                    (quality_issues["missing_products"] / total_customers) * 40
                ]))
            else:
                quality_score = 100
            
            return {
                "quality_score": round(quality_score, 2),
                "issues": quality_issues,
                "recommendations": self._generate_quality_recommendations(quality_issues, total_customers),
                "check_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"데이터 품질 검증 중 오류가 발생했습니다: {str(e)}")

    def _generate_quality_recommendations(self, issues: Dict[str, int], total_customers: int) -> List[str]:
        """데이터 품질 개선 권장사항 생성"""
        recommendations = []
        
        if total_customers == 0:
            return ["고객 데이터가 없습니다."]
        
        if issues["missing_phone"] > total_customers * 0.1:
            recommendations.append("전화번호가 누락된 고객이 많습니다. 연락처 정보를 보완해주세요.")
        
        if issues["missing_address"] > total_customers * 0.2:
            recommendations.append("주소 정보가 누락된 고객이 많습니다. 주소 정보를 수집해주세요.")
        
        if issues["missing_customer_type"] > total_customers * 0.1:
            recommendations.append("고객 유형이 미분류된 고객이 있습니다. 가입/미가입 상태를 확인해주세요.")
        
        if issues["invalid_phone_format"] > 0:
            recommendations.append("잘못된 전화번호 형식이 발견되었습니다. 000-0000-0000 형식으로 정정해주세요.")
        
        if issues["missing_products"] > total_customers * 0.3:
            recommendations.append("가입상품이 없는 고객이 많습니다. 상품 정보를 추가해주세요.")
        
        if not recommendations:
            recommendations.append("데이터 품질이 양호합니다.")
        
        return recommendations
    
    def _generate_original_data_preview(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """원본 엑셀 데이터 미리보기 생성 (첫 5행)"""
        try:
            # 첫 5행만 추출 (헤더 포함하여 총 6행)
            preview_df = df.head(5)
            
            # NaN 값을 빈 문자열로 변경
            preview_df = preview_df.fillna('')
            
            # 컬럼명과 데이터를 포함한 미리보기 생성
            preview_data = {
                "columns": df.columns.tolist(),
                "total_rows": len(df),
                "preview_rows": preview_df.values.tolist(),
                "column_mapping_applied": column_mapping,
                "mapped_fields": [column_mapping.get(col, "unmapped") for col in df.columns],
                "unmapped_columns": [col for col in df.columns if column_mapping.get(col, "unmapped") == "unmapped"]
            }
            
            return preview_data
            
        except Exception as e:
            logger.warning(f"원본 데이터 미리보기 생성 실패: {str(e)}")
            return {
                "columns": [],
                "total_rows": 0,
                "preview_rows": [],
                "error": str(e)
            }
    
    async def _generate_processed_data_preview(self, user_id: int, db_session: AsyncSession) -> Dict[str, Any]:
        """처리된 고객/상품 데이터 미리보기 생성 (최신 10개)"""
        try:
            # 최근 생성된 고객 10명 조회
            customers_stmt = select(Customer).where(
                Customer.user_id == user_id
            ).order_by(Customer.created_at.desc()).limit(10)
            
            customers_result = await db_session.execute(customers_stmt)
            recent_customers = customers_result.scalars().all()
            
            # 고객 테이블 컬럼 순서 정의 (customer_id 제외, DB 테이블 구조 순서)
            customer_columns = [
                "name", "affiliation", "gender", "date_of_birth",
                "interests", "life_events", "insurance_products", "created_at", "updated_at",
                "user_id", "customer_type", "contact_channel", "phone", "resident_number", 
                "address", "job_title", "bank_name", "account_number", "referrer", "notes"
            ]
            
            # 고객 데이터를 행렬 형태로 변환
            customers_rows = []
            for customer in recent_customers:
                row = []
                for column in customer_columns:
                    if column == "date_of_birth":
                        value = customer.date_of_birth.isoformat() if customer.date_of_birth else ""
                    elif column == "created_at":
                        value = customer.created_at.isoformat()
                    elif column == "updated_at":
                        value = customer.updated_at.isoformat()
                    elif column == "interests":
                        value = str(customer.interests or [])
                    elif column == "life_events":
                        value = str(customer.life_events or [])
                    elif column == "insurance_products":
                        value = str(customer.insurance_products or [])
                    else:
                        value = getattr(customer, column, "") or ""
                    row.append(str(value))
                customers_rows.append(row)
            
            # 최근 생성된 상품 10개 조회
            products_stmt = select(CustomerProduct).join(
                Customer, CustomerProduct.customer_id == Customer.customer_id
            ).where(
                Customer.user_id == user_id
            ).order_by(CustomerProduct.created_at.desc()).limit(10)
            
            products_result = await db_session.execute(products_stmt)
            recent_products = products_result.scalars().all()
            
            # 상품 테이블 컬럼 순서 정의 (product_id는 제외)
            product_columns = [
                "customer_id", "product_name", "coverage_amount", "subscription_date", 
                "expiry_renewal_date", "auto_transfer_date", "policy_issued", 
                "created_at", "updated_at"
            ]
            
            # 상품 데이터를 행렬 형태로 변환
            products_rows = []
            for product in recent_products:
                row = []
                for column in product_columns:
                    if column == "customer_id":
                        value = str(product.customer_id)
                    elif column == "subscription_date":
                        value = product.subscription_date.isoformat() if product.subscription_date else ""
                    elif column == "expiry_renewal_date":
                        value = product.expiry_renewal_date.isoformat() if product.expiry_renewal_date else ""
                    elif column == "created_at":
                        value = product.created_at.isoformat()
                    elif column == "updated_at":
                        value = product.updated_at.isoformat()
                    elif column == "policy_issued":
                        value = str(product.policy_issued) if product.policy_issued is not None else ""
                    else:
                        value = getattr(product, column, "") or ""
                    row.append(str(value))
                products_rows.append(row)
            
            return {
                "customers": {
                    "count": len(customers_rows),
                    "columns": customer_columns,
                    "rows": customers_rows
                },
                "products": {
                    "count": len(products_rows),
                    "columns": product_columns,
                    "rows": products_rows
                }
            }
            
        except Exception as e:
            logger.warning(f"처리된 데이터 미리보기 생성 실패: {str(e)}")
            return {
                "customers": {"count": 0, "columns": [], "rows": []},
                "products": {"count": 0, "columns": [], "rows": []},
                "error": str(e)
            }