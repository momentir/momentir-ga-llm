"""
프롬프트 관리 시스템 서비스
"""
import hashlib
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, Integer, update
from sqlalchemy.orm import selectinload

from app.db_models.prompt_models import PromptTemplate, PromptVersion, PromptABTest, PromptTestResult
from app.models.prompt_models import (
    PromptTemplateCreate, PromptTemplateUpdate, PromptVersionCreate, 
    ABTestCreate, TestResultCreate, PromptRenderRequest, PromptRenderResponse,
    ABTestStats, PromptCategory
)
import uuid
import logging
from jinja2 import Template, TemplateError

logger = logging.getLogger(__name__)


class PromptService:
    """프롬프트 관리 및 A/B 테스트 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # === 프롬프트 템플릿 관리 ===
    
    async def create_template(self, template_data: PromptTemplateCreate) -> PromptTemplate:
        """새 프롬프트 템플릿 생성"""
        db_template = PromptTemplate(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category.value,
            template_content=template_data.template_content,
            variables=template_data.variables,
            created_by=template_data.created_by
        )
        
        self.db.add(db_template)
        await self.db.commit()
        await self.db.refresh(db_template)
        
        # 첫 번째 버전 자동 생성
        await self.create_version(PromptVersionCreate(
            template_id=db_template.id,
            template_content=template_data.template_content,
            variables=template_data.variables,
            change_notes="Initial version",
            created_by=template_data.created_by
        ))
        
        return db_template
    
    async def get_templates(
        self, 
        category: Optional[PromptCategory] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PromptTemplate]:
        """프롬프트 템플릿 목록 조회"""
        query = select(PromptTemplate)
        
        if category:
            query = query.where(PromptTemplate.category == category.value)
        if is_active is not None:
            query = query.where(PromptTemplate.is_active == is_active)
            
        query = query.offset(skip).limit(limit).order_by(desc(PromptTemplate.updated_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_template(self, template_id: uuid.UUID) -> Optional[PromptTemplate]:
        """특정 프롬프트 템플릿 조회"""
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_template(
        self, 
        template_id: uuid.UUID, 
        update_data: PromptTemplateUpdate
    ) -> Optional[PromptTemplate]:
        """프롬프트 템플릿 업데이트"""
        template = await self.get_template(template_id)
        if not template:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(template)
        return template
    
    async def delete_template(self, template_id: uuid.UUID) -> bool:
        """프롬프트 템플릿 삭제 (소프트 삭제)"""
        template = await self.get_template(template_id)
        if not template:
            return False
        
        template.is_active = False
        await self.db.commit()
        return True
    
    # === 버전 관리 ===
    
    async def create_version(self, version_data: PromptVersionCreate) -> PromptVersion:
        """새 프롬프트 버전 생성"""
        # 다음 버전 번호 계산
        query = select(func.max(PromptVersion.version_number)).where(
            PromptVersion.template_id == version_data.template_id
        )
        result = await self.db.execute(query)
        max_version = result.scalar() or 0
        
        db_version = PromptVersion(
            template_id=version_data.template_id,
            version_number=max_version + 1,
            template_content=version_data.template_content,
            variables=version_data.variables,
            change_notes=version_data.change_notes,
            created_by=version_data.created_by
        )
        
        self.db.add(db_version)
        await self.db.commit()
        await self.db.refresh(db_version)
        return db_version
    
    async def get_versions(self, template_id: uuid.UUID) -> List[PromptVersion]:
        """템플릿의 모든 버전 조회"""
        query = select(PromptVersion).where(
            PromptVersion.template_id == template_id
        ).order_by(desc(PromptVersion.version_number))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_published_version(self, template_id: uuid.UUID) -> Optional[PromptVersion]:
        """게시된 버전 조회"""
        query = select(PromptVersion).where(
            and_(
                PromptVersion.template_id == template_id,
                PromptVersion.is_published == True
            )
        ).order_by(desc(PromptVersion.version_number))
        
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def publish_version(self, version_id: uuid.UUID) -> Optional[PromptVersion]:
        """버전 게시 (이전 게시된 버전은 비활성화)"""
        query = select(PromptVersion).where(PromptVersion.id == version_id)
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()
        
        if not version:
            return None
        
        # 동일 템플릿의 다른 게시된 버전들 비활성화
        await self.db.execute(
            update(PromptVersion).where(
                and_(
                    PromptVersion.template_id == version.template_id,
                    PromptVersion.is_published == True
                )
            ).values(is_published=False)
        )
        
        version.is_published = True
        await self.db.commit()
        await self.db.refresh(version)
        return version
    
    # === A/B 테스트 ===
    
    async def create_ab_test(self, test_data: ABTestCreate) -> PromptABTest:
        """A/B 테스트 생성"""
        db_test = PromptABTest(
            test_name=test_data.test_name,
            description=test_data.description,
            category=test_data.category.value,
            version_a_id=test_data.version_a_id,
            version_b_id=test_data.version_b_id,
            traffic_split=test_data.traffic_split,
            start_date=test_data.start_date,
            end_date=test_data.end_date,
            success_metric=test_data.success_metric,
            created_by=test_data.created_by
        )
        
        self.db.add(db_test)
        await self.db.commit()
        await self.db.refresh(db_test)
        return db_test
    
    async def get_active_ab_test(self, category: PromptCategory) -> Optional[PromptABTest]:
        """활성 A/B 테스트 조회"""
        now = datetime.utcnow()
        query = select(PromptABTest).options(
            selectinload(PromptABTest.version_a),
            selectinload(PromptABTest.version_b)
        ).where(
            and_(
                PromptABTest.category == category.value,
                PromptABTest.is_active == True,
                PromptABTest.start_date <= now,
                func.coalesce(PromptABTest.end_date, now + timedelta(days=1)) > now
            )
        )
        
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def record_test_result(self, result_data: TestResultCreate) -> PromptTestResult:
        """A/B 테스트 결과 기록"""
        db_result = PromptTestResult(
            test_id=result_data.test_id,
            version_id=result_data.version_id,
            user_session=result_data.user_session,
            input_data=result_data.input_data,
            output_data=result_data.output_data,
            response_time_ms=result_data.response_time_ms,
            tokens_used=result_data.tokens_used,
            success=result_data.success,
            quality_score=result_data.quality_score
        )
        
        self.db.add(db_result)
        await self.db.commit()
        return db_result
    
    async def get_ab_test_stats(self, test_id: uuid.UUID) -> Optional[ABTestStats]:
        """A/B 테스트 통계 조회"""
        # 기본 테스트 정보
        test_query = select(PromptABTest).where(PromptABTest.id == test_id)
        test_result = await self.db.execute(test_query)
        test = test_result.scalar_one_or_none()
        
        if not test:
            return None
        
        # 통계 쿼리
        stats_query = select(
            PromptTestResult.version_id,
            func.count().label('total_runs'),
            func.avg(func.cast(PromptTestResult.success, Integer)).label('success_rate'),
            func.avg(PromptTestResult.response_time_ms).label('avg_response_time'),
            func.avg(PromptTestResult.quality_score).label('avg_quality')
        ).where(
            PromptTestResult.test_id == test_id
        ).group_by(PromptTestResult.version_id)
        
        stats_result = await self.db.execute(stats_query)
        stats_data = {row.version_id: row for row in stats_result}
        
        # 결과 구성
        version_a_stats = stats_data.get(test.version_a_id)
        version_b_stats = stats_data.get(test.version_b_id)
        
        return ABTestStats(
            test_id=test_id,
            test_name=test.test_name,
            total_runs=sum(row.total_runs for row in stats_data.values()),
            version_a_runs=version_a_stats.total_runs if version_a_stats else 0,
            version_b_runs=version_b_stats.total_runs if version_b_stats else 0,
            version_a_success_rate=float(version_a_stats.success_rate or 0) if version_a_stats else 0,
            version_b_success_rate=float(version_b_stats.success_rate or 0) if version_b_stats else 0,
            version_a_avg_response_time=float(version_a_stats.avg_response_time or 0) if version_a_stats else None,
            version_b_avg_response_time=float(version_b_stats.avg_response_time or 0) if version_b_stats else None,
            version_a_avg_quality=float(version_a_stats.avg_quality or 0) if version_a_stats else None,
            version_b_avg_quality=float(version_b_stats.avg_quality or 0) if version_b_stats else None
        )
    
    # === 프롬프트 렌더링 ===
    
    async def render_prompt(self, request: PromptRenderRequest) -> Optional[PromptRenderResponse]:
        """프롬프트 렌더링 (A/B 테스트 지원)"""
        version = None
        test_id = None
        is_ab_test = False
        version_label = None
        
        if request.template_id:
            # 특정 템플릿 사용
            version = await self.get_published_version(request.template_id)
        elif request.category:
            # 카테고리로 자동 선택 (A/B 테스트 확인)
            ab_test = await self.get_active_ab_test(request.category)
            
            if ab_test and request.user_session:
                # A/B 테스트 실행
                is_ab_test = True
                test_id = ab_test.id
                
                # 사용자 세션 기반 버전 선택 (일관성 보장)
                session_hash = hashlib.md5(request.user_session.encode()).hexdigest()
                session_value = int(session_hash[:8], 16) / (16**8)  # 0~1 범위
                
                if session_value < ab_test.traffic_split:
                    version = ab_test.version_a
                    version_label = "A"
                else:
                    version = ab_test.version_b
                    version_label = "B"
            else:
                # 기본 게시된 버전 사용
                templates = await self.get_templates(category=request.category, is_active=True, limit=1)
                if templates:
                    version = await self.get_published_version(templates[0].id)
        
        if not version:
            return None
        
        try:
            # Jinja2 템플릿으로 렌더링
            template = Template(version.template_content)
            rendered_content = template.render(**request.variables)
            
            return PromptRenderResponse(
                rendered_content=rendered_content,
                template_id=version.template_id,
                version_id=version.id,
                is_ab_test=is_ab_test,
                test_id=test_id,
                version_label=version_label
            )
            
        except TemplateError as e:
            logger.error(f"Template rendering error: {e}")
            return None
    
    async def get_template_by_category(self, category: PromptCategory) -> Optional[PromptTemplate]:
        """카테고리별 활성 템플릿 조회"""
        query = select(PromptTemplate).where(
            and_(
                PromptTemplate.category == category.value,
                PromptTemplate.is_active == True
            )
        ).order_by(desc(PromptTemplate.updated_at))
        
        result = await self.db.execute(query)
        return result.scalars().first()