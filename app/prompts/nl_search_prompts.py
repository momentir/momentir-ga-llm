"""
Natural Language to SQL 프롬프트 템플릿
OpenAI 2025 최신 프롬프트 엔지니어링 가이드라인 적용
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

from jinja2 import Template, Environment, BaseLoader
from sqlalchemy import inspect, MetaData, Table
from sqlalchemy.engine import Engine

from app.database import db_manager

logger = logging.getLogger(__name__)


@dataclass
class TableSchema:
    """테이블 스키마 정보"""
    name: str
    columns: List[Dict[str, Any]]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    indexes: List[str]


@dataclass
class FewShotExample:
    """Few-shot 학습 예제"""
    natural_language: str
    sql_query: str
    explanation: str
    complexity: int  # 1-5 (간단→복잡)
    reasoning_steps: List[str]


class NLSearchPromptManager:
    """자연어-SQL 변환 프롬프트 관리자"""
    
    def __init__(self):
        """프롬프트 관리자 초기화"""
        self.jinja_env = Environment(loader=BaseLoader())
        self.schema_cache: Optional[List[TableSchema]] = None
        self.cache_timestamp: Optional[datetime] = None
        self.cache_ttl_seconds = 3600  # 1시간 캐시
        
        # Few-shot 예제들 (간단→복잡 순서)
        self.few_shot_examples = [
            # 예제 1: 단순 조회 (복잡도 1)
            FewShotExample(
                natural_language="모든 고객의 이름과 전화번호를 보여주세요",
                sql_query="SELECT name, phone FROM customers;",
                explanation="고객 테이블에서 이름과 전화번호 컬럼만 조회하는 단순한 SELECT 문입니다.",
                complexity=1,
                reasoning_steps=[
                    "1. 사용자가 '모든 고객'을 요청했으므로 customers 테이블을 사용",
                    "2. '이름과 전화번호'가 필요하므로 name, phone 컬럼 선택",
                    "3. 조건이 없으므로 WHERE 절 없이 전체 데이터 조회",
                    "4. 단순한 SELECT 문으로 작성"
                ]
            ),
            
            # 예제 1-2: 존재하지 않는 컬럼 요청 처리 (복잡도 1)
            FewShotExample(
                natural_language="모든 고객의 이름과 이메일을 보여주세요",
                sql_query="SELECT name, phone FROM customers;",
                explanation="사용자가 '이메일'을 요청했지만 customers 테이블에는 email 컬럼이 없습니다. 대신 연락처 정보인 phone 컬럼을 사용합니다.",
                complexity=1,
                reasoning_steps=[
                    "1. 사용자가 '모든 고객'을 요청했으므로 customers 테이블을 사용",
                    "2. '이메일'을 요청했지만 customers 테이블에 email 컬럼이 존재하지 않음",
                    "3. 대신 연락처 정보인 phone 컬럼을 사용",
                    "4. name, phone 컬럼으로 SELECT 문 작성"
                ]
            ),
            
            # 예제 2: 조건부 필터링 (복잡도 2)
            FewShotExample(
                natural_language="최근 30일 내에 가입한 고객들을 찾아주세요",
                sql_query="SELECT customer_id, name, phone, created_at FROM customers WHERE created_at >= CURRENT_DATE - INTERVAL '30 days' ORDER BY created_at DESC;",
                explanation="날짜 조건을 사용하여 최근 가입한 고객을 조회하고 가입일 역순으로 정렬합니다.",
                complexity=2,
                reasoning_steps=[
                    "1. '최근 30일'이라는 시간 조건 식별",
                    "2. customers 테이블의 created_at 컬럼 사용",
                    "3. CURRENT_DATE - INTERVAL '30 days'로 30일 전 날짜 계산",
                    "4. WHERE 절로 조건 적용",
                    "5. ORDER BY created_at DESC로 최신순 정렬"
                ]
            ),
            
            # 예제 3: JOIN 연산 (복잡도 3)
            FewShotExample(
                natural_language="각 고객이 작성한 메모의 개수를 보여주세요",
                sql_query="SELECT c.customer_id, c.name, COUNT(m.id) as memo_count FROM customers c LEFT JOIN memos m ON c.customer_id = m.customer_id GROUP BY c.customer_id, c.name ORDER BY memo_count DESC;",
                explanation="고객과 메모 테이블을 조인하여 각 고객별 메모 개수를 집계합니다. 메모가 없는 고객도 포함하기 위해 LEFT JOIN을 사용합니다.",
                complexity=3,
                reasoning_steps=[
                    "1. 고객 정보가 필요하므로 customers 테이블 선택",
                    "2. 메모 개수가 필요하므로 memos 테이블과 조인 필요",
                    "3. '각 고객'이므로 GROUP BY를 통한 그룹화 필요",
                    "4. COUNT(m.id)로 메모 개수 계산",
                    "5. LEFT JOIN으로 메모가 없는 고객도 포함",
                    "6. ORDER BY memo_count DESC로 메모가 많은 순으로 정렬"
                ]
            ),
            
            # 예제 4: 복합 조건과 서브쿼리 (복잡도 4)
            FewShotExample(
                natural_language="메모를 5개 이상 작성하고, 우선순위가 높은 이벤트가 있는 고객들의 상세 정보를 보여주세요",
                sql_query="""
                SELECT DISTINCT c.customer_id, c.name, c.phone, 
                       memo_counts.memo_count,
                       high_priority_events.event_count as high_priority_event_count
                FROM customers c
                INNER JOIN (
                    SELECT customer_id, COUNT(*) as memo_count 
                    FROM memos 
                    GROUP BY customer_id 
                    HAVING COUNT(*) >= 5
                ) memo_counts ON c.customer_id = memo_counts.customer_id
                INNER JOIN (
                    SELECT customer_id, COUNT(*) as event_count
                    FROM events 
                    WHERE priority = 'high'
                    GROUP BY customer_id
                    HAVING COUNT(*) > 0
                ) high_priority_events ON c.customer_id = high_priority_events.customer_id
                ORDER BY memo_counts.memo_count DESC, high_priority_events.event_count DESC;
                """.strip(),
                explanation="복합 조건을 만족하는 고객을 찾기 위해 서브쿼리와 다중 JOIN을 사용합니다. 메모 개수 조건과 우선순위 이벤트 조건을 각각 서브쿼리로 처리합니다.",
                complexity=4,
                reasoning_steps=[
                    "1. '메모를 5개 이상'이라는 집계 조건 식별",
                    "2. '우선순위가 높은 이벤트'라는 추가 조건 식별",
                    "3. 첫 번째 서브쿼리로 메모 개수가 5개 이상인 고객 찾기",
                    "4. 두 번째 서브쿼리로 우선순위 높은 이벤트가 있는 고객 찾기",
                    "5. INNER JOIN으로 두 조건을 모두 만족하는 고객만 조회",
                    "6. DISTINCT로 중복 제거",
                    "7. 메모 개수와 이벤트 개수 내림차순으로 정렬"
                ]
            ),
            
            # 예제 5: 시간 범위와 집계 분석 (복잡도 5)
            FewShotExample(
                natural_language="지난 3개월 동안 월별로 신규 고객 수, 평균 메모 길이, 그리고 완료되지 않은 이벤트 비율을 분석해주세요",
                sql_query="""
                WITH monthly_stats AS (
                    SELECT 
                        DATE_TRUNC('month', c.created_at) as month,
                        COUNT(DISTINCT c.id) as new_customers,
                        AVG(LENGTH(m.content)) as avg_memo_length,
                        COUNT(DISTINCT CASE WHEN e.status != 'completed' THEN e.id END) as incomplete_events,
                        COUNT(DISTINCT e.id) as total_events
                    FROM customers c
                    LEFT JOIN memos m ON c.id = m.customer_id
                    LEFT JOIN events e ON c.id = e.customer_id
                    WHERE c.created_at >= CURRENT_DATE - INTERVAL '3 months'
                    GROUP BY DATE_TRUNC('month', c.created_at)
                )
                SELECT 
                    month,
                    new_customers,
                    ROUND(avg_memo_length, 2) as avg_memo_length,
                    CASE 
                        WHEN total_events = 0 THEN 0 
                        ELSE ROUND((incomplete_events::DECIMAL / total_events * 100), 2) 
                    END as incomplete_event_percentage
                FROM monthly_stats
                ORDER BY month DESC;
                """.strip(),
                explanation="CTE(Common Table Expression)를 사용하여 복잡한 월별 분석을 수행합니다. 다중 테이블 조인, 조건부 집계, 비율 계산 등을 포함합니다.",
                complexity=5,
                reasoning_steps=[
                    "1. '지난 3개월'이라는 시간 범위 조건 식별",
                    "2. '월별로' 분석하므로 DATE_TRUNC('month') 사용",
                    "3. '신규 고객 수' = 월별 고객 생성 건수",
                    "4. '평균 메모 길이' = AVG(LENGTH(content))",
                    "5. '완료되지 않은 이벤트 비율' = 조건부 집계와 백분율 계산",
                    "6. CTE로 복잡한 로직을 단계별로 분리",
                    "7. LEFT JOIN으로 모든 데이터 포함",
                    "8. CASE문으로 0으로 나누기 오류 방지",
                    "9. 최근 월부터 내림차순 정렬"
                ]
            )
        ]
        
        logger.info("✅ NLSearchPromptManager 초기화 완료")
    
    async def get_database_schema(self, force_refresh: bool = False) -> List[TableSchema]:
        """
        데이터베이스 스키마를 자동으로 읽어옵니다.
        
        Args:
            force_refresh: 캐시를 무시하고 강제로 새로고침
        
        Returns:
            List[TableSchema]: 테이블 스키마 정보 목록
        """
        try:
            # 캐시 확인
            if not force_refresh and self.schema_cache and self.cache_timestamp:
                cache_age = (datetime.now() - self.cache_timestamp).total_seconds()
                if cache_age < self.cache_ttl_seconds:
                    logger.debug("스키마 캐시 사용")
                    return self.schema_cache
            
            logger.info("데이터베이스 스키마 읽기 시작")
            schemas = []
            
            # SQLAlchemy 엔진을 통해 스키마 정보 읽기
            async with db_manager.engine.begin() as conn:
                # MetaData로 테이블 정보 읽기
                metadata = MetaData()
                await conn.run_sync(metadata.reflect)
                
                for table_name, table in metadata.tables.items():
                    # 허용된 테이블만 포함
                    allowed_tables = {'customers', 'memos', 'events', 'users', 'prompts', 
                                    'prompt_templates', 'prompt_logs', 'customer_analytics'}
                    
                    if table_name not in allowed_tables:
                        continue
                    
                    # 컬럼 정보 수집
                    columns = []
                    for column in table.columns:
                        col_info = {
                            'name': column.name,
                            'type': str(column.type),
                            'nullable': column.nullable,
                            'default': str(column.default) if column.default else None,
                            'description': column.comment if hasattr(column, 'comment') else None
                        }
                        columns.append(col_info)
                    
                    # Primary Key 정보
                    primary_keys = [col.name for col in table.primary_key]
                    
                    # Foreign Key 정보
                    foreign_keys = []
                    for fk in table.foreign_keys:
                        fk_info = {
                            'column': fk.parent.name,
                            'references_table': fk.column.table.name,
                            'references_column': fk.column.name
                        }
                        foreign_keys.append(fk_info)
                    
                    # Index 정보
                    indexes = [idx.name for idx in table.indexes if idx.name]
                    
                    schema = TableSchema(
                        name=table_name,
                        columns=columns,
                        primary_keys=primary_keys,
                        foreign_keys=foreign_keys,
                        indexes=indexes
                    )
                    schemas.append(schema)
            
            # 캐시 업데이트
            self.schema_cache = schemas
            self.cache_timestamp = datetime.now()
            
            logger.info(f"데이터베이스 스키마 읽기 완료: {len(schemas)}개 테이블")
            return schemas
        
        except Exception as e:
            logger.error(f"데이터베이스 스키마 읽기 실패: {e}")
            # 기본 스키마 반환
            return self._get_fallback_schema()
    
    def _get_fallback_schema(self) -> List[TableSchema]:
        """데이터베이스 연결 실패 시 사용할 기본 스키마"""
        return [
            TableSchema(
                name="customers",
                columns=[
                    {"name": "customer_id", "type": "UUID", "nullable": False},
                    {"name": "name", "type": "VARCHAR(100)", "nullable": True},
                    {"name": "affiliation", "type": "VARCHAR(200)", "nullable": True},
                    {"name": "gender", "type": "VARCHAR(10)", "nullable": True},
                    {"name": "date_of_birth", "type": "TIMESTAMP", "nullable": True},
                    {"name": "phone", "type": "VARCHAR(20)", "nullable": True},
                    {"name": "address", "type": "VARCHAR(500)", "nullable": True},
                    {"name": "job_title", "type": "VARCHAR(100)", "nullable": True},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                    {"name": "updated_at", "type": "TIMESTAMP", "nullable": False}
                ],
                primary_keys=["customer_id"],
                foreign_keys=[],
                indexes=["idx_customers_name"]
            ),
            TableSchema(
                name="memos",
                columns=[
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "customer_id", "type": "UUID", "nullable": False},
                    {"name": "content", "type": "TEXT", "nullable": False},
                    {"name": "refined_content", "type": "TEXT", "nullable": True},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
                    {"name": "updated_at", "type": "TIMESTAMP", "nullable": False}
                ],
                primary_keys=["id"],
                foreign_keys=[{"column": "customer_id", "references_table": "customers", "references_column": "customer_id"}],
                indexes=["idx_memos_customer_id"]
            ),
            TableSchema(
                name="events",
                columns=[
                    {"name": "id", "type": "INTEGER", "nullable": False},
                    {"name": "customer_id", "type": "UUID", "nullable": False},
                    {"name": "event_type", "type": "VARCHAR", "nullable": False},
                    {"name": "priority", "type": "VARCHAR", "nullable": False},
                    {"name": "status", "type": "VARCHAR", "nullable": False},
                    {"name": "due_date", "type": "DATE", "nullable": True},
                    {"name": "created_at", "type": "TIMESTAMP", "nullable": False}
                ],
                primary_keys=["id"],
                foreign_keys=[{"column": "customer_id", "references_table": "customers", "references_column": "customer_id"}],
                indexes=["idx_events_customer_id", "idx_events_priority"]
            )
        ]
    
    def _format_schema_for_prompt(self, schemas: List[TableSchema]) -> str:
        """스키마 정보를 프롬프트용 문자열로 포맷"""
        schema_text = "## 데이터베이스 스키마\n\n"
        
        for schema in schemas:
            schema_text += f"### {schema.name} 테이블\n"
            schema_text += "**컬럼:**\n"
            
            for col in schema.columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f" DEFAULT {col['default']}" if col['default'] else ""
                schema_text += f"- `{col['name']}`: {col['type']} {nullable}{default}\n"
            
            if schema.primary_keys:
                schema_text += f"**Primary Key:** {', '.join(schema.primary_keys)}\n"
            
            if schema.foreign_keys:
                fk_text = []
                for fk in schema.foreign_keys:
                    fk_text.append(f"{fk['column']} → {fk['references_table']}.{fk['references_column']}")
                schema_text += f"**Foreign Keys:** {', '.join(fk_text)}\n"
            
            schema_text += "\n"
        
        return schema_text
    
    def _format_examples_for_prompt(self) -> str:
        """Few-shot 예제를 프롬프트용 문자열로 포맷"""
        examples_text = "## Few-Shot Examples\n\n"
        
        # 복잡도 순으로 정렬
        sorted_examples = sorted(self.few_shot_examples, key=lambda x: x.complexity)
        
        for i, example in enumerate(sorted_examples, 1):
            examples_text += f"### Example {i} (복잡도: {example.complexity}/5)\n\n"
            examples_text += f"**자연어 질의:** {example.natural_language}\n\n"
            
            examples_text += "**추론 과정:**\n"
            for step in example.reasoning_steps:
                examples_text += f"{step}\n"
            examples_text += "\n"
            
            examples_text += f"**SQL 쿼리:**\n```sql\n{example.sql_query}\n```\n\n"
            examples_text += f"**설명:** {example.explanation}\n\n"
            examples_text += "---\n\n"
        
        return examples_text
    
    async def generate_intent_analysis_prompt(self, user_query: str, context: Dict[str, Any] = None) -> str:
        """의도 분석용 프롬프트 생성"""
        
        template_str = """# 자연어 쿼리 의도 분석

당신은 자연어 쿼리의 의도를 분석하는 전문가입니다. 사용자의 질의를 분석하여 검색 의도와 유형을 정확히 파악하세요.

## 분석 단계 (Chain-of-Thought)

1. **키워드 추출**: 사용자 질의에서 핵심 키워드와 개체명을 추출
2. **의도 분류**: 다음 중 하나로 분류
   - customer_info: 고객 정보 검색
   - memo_search: 메모 검색  
   - event_analysis: 이벤트 분석
   - analytics: 통계/분석
   - unknown: 알 수 없음

3. **검색 유형 결정**: 
   - simple_filter: 단순 필터링
   - complex_join: 복잡한 조인
   - aggregation: 집계 연산
   - time_series: 시계열 분석

4. **엔터티 추출**: 날짜, 이름, 수량 등 구체적인 정보 추출
5. **신뢰도 평가**: 분석 결과의 확실성 평가 (0.0-1.0)

## 사용자 질의
"{{ user_query }}"

{% if context %}
## 추가 컨텍스트
{% for key, value in context.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

## 요구 출력 형식

다음 JSON 형식으로 응답하세요:

```json
{
    "intent": "분류된 의도",
    "search_type": "검색 유형", 
    "entities": {
        "키": "값"
    },
    "confidence": 0.95,
    "reasoning": "분석 근거를 상세히 설명"
}
```

## 중요 지침

- 반드시 Chain-of-Thought 추론을 통해 단계별로 분석
- 불확실한 경우 confidence를 낮게 설정
- reasoning에서 분석 과정을 구체적으로 설명
- JSON 형식을 정확히 준수"""

        template = self.jinja_env.from_string(template_str)
        return template.render(user_query=user_query, context=context or {})
    
    async def generate_sql_generation_prompt(self, user_query: str, intent_analysis: Dict[str, Any], 
                                           context: Dict[str, Any] = None) -> str:
        """SQL 생성용 프롬프트 생성"""
        
        # 데이터베이스 스키마 가져오기
        schemas = await self.get_database_schema()
        schema_text = self._format_schema_for_prompt(schemas)
        examples_text = self._format_examples_for_prompt()
        
        template_str = """# 자연어를 PostgreSQL 쿼리로 변환

당신은 자연어를 정확한 PostgreSQL SQL 쿼리로 변환하는 전문가입니다. OpenAI 2025 최신 가이드라인을 따라 고품질의 SQL을 생성하세요.

{{ schema_text }}

{{ examples_text }}

## Chain-of-Thought SQL 생성 과정

다음 단계를 따라 체계적으로 SQL을 생성하세요:

### 1단계: 요구사항 분석
- 사용자가 원하는 정보가 무엇인지 파악
- 필요한 테이블들 식별
- 조건과 필터링 요구사항 분석

### 2단계: 테이블 관계 분석  
- Primary/Foreign Key 관계 확인
- JOIN이 필요한지 판단
- JOIN 유형 결정 (INNER, LEFT, RIGHT, FULL)

### 3단계: 조건 및 필터 설계
- WHERE 절 조건 설계
- 날짜, 숫자, 텍스트 조건 처리
- 파라미터 바인딩 설계

### 4단계: 집계 및 그룹화
- GROUP BY 필요성 판단
- 집계 함수 선택 (COUNT, SUM, AVG 등)
- HAVING 절 필요성 검토

### 5단계: 정렬 및 제한
- ORDER BY 설계
- LIMIT 절 추가
- 성능 최적화 고려

### 6단계: 최종 검증
- SQL 문법 정확성 확인
- 보안 취약점 검토
- 성능 최적화 가능성 검토

## 현재 요청 분석

**사용자 질의:** "{{ user_query }}"

**의도 분석 결과:**
- 의도: {{ intent_analysis.intent }}
- 검색 유형: {{ intent_analysis.search_type }}
- 추출된 엔터티: {{ intent_analysis.entities }}
- 분석 근거: {{ intent_analysis.reasoning }}

{% if context %}
**추가 컨텍스트:**
{% for key, value in context.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

## 요구 출력 형식

다음 JSON 형식으로 응답하세요:

```json
{
    "sql": "생성된 PostgreSQL 쿼리",
    "parameters": {
        "파라미터명": "값"
    },
    "explanation": "쿼리 동작 방식 설명",
    "estimated_complexity": "low|medium|high",
    "reasoning_steps": [
        "1단계: 요구사항 분석 결과",
        "2단계: 테이블 관계 분석 결과",
        "3단계: 조건 설계 결과", 
        "4단계: 집계 설계 결과",
        "5단계: 정렬 설계 결과",
        "6단계: 최종 검증 결과"
    ]
}
```

## 중요 원칙

1. **보안 최우선**: 항상 파라미터 바인딩 사용, SQL Injection 방지
2. **읽기 전용**: SELECT 문만 생성, DML/DDL 금지
3. **성능 고려**: 적절한 인덱스 활용, 불필요한 데이터 제한
4. **PostgreSQL 문법**: PostgreSQL 전용 함수와 문법 활용
5. **명확성**: 가독성 좋은 쿼리 작성
6. **정확성**: 스키마와 관계를 정확히 반영

위 단계를 따라 체계적으로 분석하고 최적의 SQL 쿼리를 생성하세요."""

        template = self.jinja_env.from_string(template_str)
        return template.render(
            user_query=user_query,
            intent_analysis=intent_analysis,
            context=context or {},
            schema_text=schema_text,
            examples_text=examples_text
        )


# 싱글톤 인스턴스
nl_prompt_manager = NLSearchPromptManager()