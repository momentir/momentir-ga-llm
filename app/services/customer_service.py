import os
import uuid
import pandas as pd
import openai
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.db_models import Customer
from app.models import CustomerCreateRequest, CustomerUpdateRequest
from app.utils.langsmith_config import langsmith_manager, trace_llm_call
from app.utils.dynamic_prompt_loader import get_column_mapping_prompt, prompt_loader
from app.models.prompt_models import PromptCategory
from datetime import datetime, date
import json
import re
import logging
import time

logger = logging.getLogger(__name__)


class CustomerService:
    def __init__(self):
        # Azure OpenAI 클라이언트 설정
        api_type = os.getenv("OPENAI_API_TYPE", "openai")
        
        if api_type == "azure":
            self.client = openai.AsyncAzureOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
            )
            self.chat_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4")
        else:
            self.client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.chat_model = "gpt-4"
        
        # 표준 고객 스키마 정의
        self.standard_schema = {
            "name": "고객 이름",
            "contact": "연락처 (전화번호, 이메일 등)",
            "affiliation": "소속 (회사, 기관 등)",
            "occupation": "직업",
            "gender": "성별",
            "date_of_birth": "생년월일",
            "interests": "관심사 (리스트)",
            "life_events": "인생 이벤트 (결혼, 출산 등)",
            "insurance_products": "보험 상품 정보"
        }
        
        # 동적 프롬프트 로딩을 위한 설정
        self.use_dynamic_prompts = True

    async def create_customer(self, customer_data: CustomerCreateRequest, db_session: AsyncSession) -> Customer:
        """
        새 고객을 생성합니다.
        """
        try:
            # 생년월일 처리
            date_of_birth_dt = None
            if customer_data.date_of_birth:
                if isinstance(customer_data.date_of_birth, date):
                    date_of_birth_dt = datetime.combine(customer_data.date_of_birth, datetime.min.time())
                elif isinstance(customer_data.date_of_birth, str):
                    try:
                        parsed_date = datetime.strptime(customer_data.date_of_birth, "%Y-%m-%d")
                        date_of_birth_dt = parsed_date
                    except ValueError:
                        pass

            # Customer 객체 생성
            customer = Customer(
                customer_id=uuid.uuid4(),
                name=customer_data.name,
                contact=customer_data.contact,
                affiliation=customer_data.affiliation,
                occupation=customer_data.occupation,
                gender=customer_data.gender,
                date_of_birth=date_of_birth_dt,
                interests=customer_data.interests or [],
                life_events=customer_data.life_events or [],
                insurance_products=customer_data.insurance_products or []
            )

            db_session.add(customer)
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
                if field == "date_of_birth" and value:
                    if isinstance(value, date):
                        value = datetime.combine(value, datetime.min.time())
                    elif isinstance(value, str):
                        try:
                            value = datetime.strptime(value, "%Y-%m-%d")
                        except ValueError:
                            continue
                
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
                Customer.contact.ilike(f"%{query}%"),
                Customer.affiliation.ilike(f"%{query}%"),
                Customer.occupation.ilike(f"%{query}%")
            ]

            stmt = select(Customer).where(
                or_(*search_conditions)
            ).limit(limit).order_by(Customer.updated_at.desc())

            result = await db_session.execute(stmt)
            customers = result.scalars().all()

            return customers

        except Exception as e:
            raise Exception(f"고객 검색 중 오류가 발생했습니다: {str(e)}")

    async def map_excel_columns(self, excel_columns: List[str], user_session: str = None, db_session: AsyncSession = None) -> Dict[str, Any]:
        """
        LLM을 사용하여 엑셀 컬럼명을 표준 스키마로 매핑합니다. (동적 프롬프트 지원)
        """
        try:
            logger.info(f"엑셀 컬럼 매핑 시작: {excel_columns}")
            start_time = time.time()
            
            # 동적 프롬프트 로딩
            if self.use_dynamic_prompts:
                user_prompt = await get_column_mapping_prompt(
                    excel_columns, 
                    self.standard_schema, 
                    user_session, 
                    db_session
                )
            else:
                # 폴백 프롬프트 (하드코딩)
                user_prompt = f"""당신은 엑셀 컬럼명을 표준 고객 스키마로 매핑하는 전문가입니다.

표준 스키마:
{json.dumps(self.standard_schema, ensure_ascii=False, indent=2)}

엑셀 컬럼명들을 표준 스키마로 매핑해주세요:

엑셀 컬럼: {excel_columns}

각 엑셀 컬럼이 어떤 표준 필드에 해당하는지 매핑하고,
매핑할 수 없는 컬럼은 'unmapped'로 표시하세요.

JSON 형식으로 응답해주세요:
{{
  "mappings": {{
    "엑셀컬럼명": "표준필드명",
    "매핑불가컬럼": "unmapped"
  }},
  "confidence": 0.95,
  "suggestions": ["매핑 개선 제안"]
}}"""

            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )

            result_text = response.choices[0].message.content
            
            # JSON 파싱
            try:
                result = json.loads(result_text)
                
                # 검증 및 기본값 설정
                mapping = result.get("mapping", {})
                confidence_score = result.get("confidence_score", 0.5)
                
                # unmapped 컬럼들 추출
                unmapped_columns = [
                    col for col, mapped_field in mapping.items() 
                    if mapped_field == "unmapped"
                ]
                
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                # LangSmith에 수동 로깅
                langsmith_manager.log_llm_call(
                    model=self.chat_model,
                    prompt=f"컬럼 매핑: {json.dumps(excel_columns, ensure_ascii=False)}",
                    response=result_text,
                    metadata={
                        "function": "map_excel_columns",
                        "input_columns": excel_columns,
                        "mapped_count": len([v for v in mapping.values() if v != "unmapped"]),
                        "unmapped_count": len(unmapped_columns),
                        "confidence_score": confidence_score,
                        "response_time_ms": response_time_ms,
                        "use_dynamic_prompts": self.use_dynamic_prompts
                    }
                )
                
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
                # JSON 파싱 실패 시 기본 매핑 반환
                logger.warning("JSON 파싱 실패, 기본 매핑 반환")
                return {
                    "mapping": {col: "unmapped" for col in excel_columns},
                    "unmapped_columns": excel_columns,
                    "confidence_score": 0.0
                }

        except Exception as e:
            raise Exception(f"컬럼 매핑 중 오류가 발생했습니다: {str(e)}")

    async def process_excel_data(self, df: pd.DataFrame, column_mapping: Dict[str, str], db_session: AsyncSession) -> Dict[str, Any]:
        """
        엑셀 데이터를 처리하여 고객 데이터를 생성/업데이트합니다.
        """
        try:
            processed_rows = 0
            created_customers = 0
            updated_customers = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    # 매핑된 데이터 추출
                    customer_data = {}
                    
                    for excel_col, standard_field in column_mapping.items():
                        if standard_field != "unmapped" and excel_col in df.columns:
                            value = row[excel_col]
                            
                            # 빈 값 처리
                            if pd.isna(value) or value == "":
                                continue
                            
                            # 데이터 타입별 처리
                            if standard_field == "date_of_birth":
                                try:
                                    # 다양한 날짜 형식 처리
                                    if isinstance(value, str):
                                        # 일반적인 날짜 형식들 시도
                                        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
                                            try:
                                                parsed_date = datetime.strptime(value.strip(), fmt)
                                                customer_data[standard_field] = parsed_date.date()
                                                break
                                            except ValueError:
                                                continue
                                    elif isinstance(value, datetime):
                                        customer_data[standard_field] = value.date()
                                except:
                                    pass  # 날짜 파싱 실패 시 무시
                            
                            elif standard_field in ["interests", "life_events", "insurance_products"]:
                                # 리스트나 JSON 데이터 처리
                                if isinstance(value, str):
                                    try:
                                        # JSON 형태인지 확인
                                        if value.startswith('[') or value.startswith('{'):
                                            customer_data[standard_field] = json.loads(value)
                                        else:
                                            # 쉼표로 구분된 문자열을 리스트로 변환
                                            customer_data[standard_field] = [item.strip() for item in value.split(',') if item.strip()]
                                    except:
                                        customer_data[standard_field] = [str(value)]
                                else:
                                    customer_data[standard_field] = [str(value)]
                            
                            else:
                                # 문자열 필드들
                                customer_data[standard_field] = str(value).strip()

                    # 고객 데이터가 있는 경우에만 처리
                    if customer_data:
                        # 기존 고객 확인 (이름과 연락처로)
                        existing_customer = None
                        if customer_data.get("name") and customer_data.get("contact"):
                            stmt = select(Customer).where(
                                and_(
                                    Customer.name == customer_data["name"],
                                    Customer.contact == customer_data["contact"]
                                )
                            )
                            result = await db_session.execute(stmt)
                            existing_customer = result.scalar_one_or_none()

                        if existing_customer:
                            # 기존 고객 업데이트
                            update_request = CustomerUpdateRequest(**customer_data)
                            await self.update_customer(str(existing_customer.customer_id), update_request, db_session)
                            updated_customers += 1
                        else:
                            # 새 고객 생성
                            create_request = CustomerCreateRequest(**customer_data)
                            await self.create_customer(create_request, db_session)
                            created_customers += 1

                    processed_rows += 1

                except Exception as e:
                    errors.append(f"행 {index + 2}: {str(e)}")

            return {
                "success": True,
                "processed_rows": processed_rows,
                "created_customers": created_customers,
                "updated_customers": updated_customers,
                "errors": errors
            }

        except Exception as e:
            await db_session.rollback()
            raise Exception(f"엑셀 데이터 처리 중 오류가 발생했습니다: {str(e)}")

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