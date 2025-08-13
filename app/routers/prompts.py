"""
프롬프트 관리 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.prompt_service import PromptService
from app.models.prompt_models import (
    PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateList,
    PromptVersion, PromptVersionCreate,
    ABTest, ABTestCreate, ABTestStats,
    PromptRenderRequest, PromptRenderResponse,
    TestResultCreate, PromptCategory
)
import uuid

router = APIRouter(prefix="/v1/api/prompts", tags=["prompts"])


# === 프롬프트 템플릿 관리 ===

@router.post("/templates", response_model=PromptTemplate)
async def create_template(
    template_data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """새 프롬프트 템플릿 생성"""
    service = PromptService(db)
    return await service.create_template(template_data)


@router.get("/templates", response_model=List[PromptTemplate])
async def get_templates(
    category: Optional[PromptCategory] = Query(None, description="프롬프트 카테고리"),
    is_active: Optional[bool] = Query(None, description="활성 상태"),
    skip: int = Query(0, ge=0, description="건너뛸 개수"),
    limit: int = Query(100, ge=1, le=1000, description="가져올 개수"),
    db: AsyncSession = Depends(get_db)
):
    """프롬프트 템플릿 목록 조회"""
    service = PromptService(db)
    return await service.get_templates(category, is_active, skip, limit)


@router.get("/templates/{template_id}", response_model=PromptTemplate)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """특정 프롬프트 템플릿 조회"""
    service = PromptService(db)
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=PromptTemplate)
async def update_template(
    template_id: uuid.UUID,
    update_data: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db)
):
    """프롬프트 템플릿 업데이트"""
    service = PromptService(db)
    template = await service.update_template(template_id, update_data)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """프롬프트 템플릿 삭제 (소프트 삭제)"""
    service = PromptService(db)
    success = await service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}


# === 버전 관리 ===

@router.post("/templates/{template_id}/versions", response_model=PromptVersion)
async def create_version(
    template_id: uuid.UUID,
    version_data: PromptVersionCreate,
    db: AsyncSession = Depends(get_db)
):
    """새 프롬프트 버전 생성"""
    # template_id 일치 확인
    if version_data.template_id != template_id:
        raise HTTPException(status_code=400, detail="Template ID mismatch")
    
    service = PromptService(db)
    return await service.create_version(version_data)


@router.get("/templates/{template_id}/versions", response_model=List[PromptVersion])
async def get_versions(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """템플릿의 모든 버전 조회"""
    service = PromptService(db)
    return await service.get_versions(template_id)


@router.get("/templates/{template_id}/versions/published", response_model=PromptVersion)
async def get_published_version(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """게시된 버전 조회"""
    service = PromptService(db)
    version = await service.get_published_version(template_id)
    if not version:
        raise HTTPException(status_code=404, detail="No published version found")
    return version


@router.post("/versions/{version_id}/publish", response_model=PromptVersion)
async def publish_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """버전 게시"""
    service = PromptService(db)
    version = await service.publish_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


# === A/B 테스트 ===

@router.post("/ab-tests", response_model=ABTest)
async def create_ab_test(
    test_data: ABTestCreate,
    db: AsyncSession = Depends(get_db)
):
    """A/B 테스트 생성"""
    service = PromptService(db)
    return await service.create_ab_test(test_data)


@router.get("/ab-tests/{test_id}/stats", response_model=ABTestStats)
async def get_ab_test_stats(
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """A/B 테스트 통계 조회"""
    service = PromptService(db)
    stats = await service.get_ab_test_stats(test_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Test not found")
    return stats


@router.post("/ab-tests/{test_id}/results")
async def record_test_result(
    test_id: uuid.UUID,
    result_data: TestResultCreate,
    db: AsyncSession = Depends(get_db)
):
    """A/B 테스트 결과 기록"""
    # test_id 일치 확인
    if result_data.test_id != test_id:
        raise HTTPException(status_code=400, detail="Test ID mismatch")
    
    service = PromptService(db)
    result = await service.record_test_result(result_data)
    return {"message": "Test result recorded", "result_id": result.id}


# === 프롬프트 렌더링 ===

@router.post("/render", response_model=PromptRenderResponse)
async def render_prompt(
    request: PromptRenderRequest,
    db: AsyncSession = Depends(get_db)
):
    """프롬프트 렌더링 (A/B 테스트 지원)"""
    service = PromptService(db)
    response = await service.render_prompt(request)
    if not response:
        raise HTTPException(status_code=404, detail="Template not found or rendering failed")
    return response


# === 유틸리티 ===

@router.get("/categories")
async def get_categories():
    """사용 가능한 프롬프트 카테고리 목록"""
    return [{"value": cat.value, "label": cat.value.replace("_", " ").title()} 
            for cat in PromptCategory]


@router.get("/templates/category/{category}", response_model=PromptTemplate)
async def get_template_by_category(
    category: PromptCategory,
    db: AsyncSession = Depends(get_db)
):
    """카테고리별 활성 템플릿 조회"""
    service = PromptService(db)
    template = await service.get_template_by_category(category)
    if not template:
        raise HTTPException(status_code=404, detail=f"No active template found for category: {category.value}")
    return template