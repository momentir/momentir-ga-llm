# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Development Commands

### Local Development Setup
- **Setup environment**: `./scripts/02-envrinment/01-setup-development.sh`
- **Start local server**: `./scripts/02-envrinment/02-start-local.sh`
- **Test API**: `./scripts/02-envrinment/03-test-api.sh`
- **Manual server start**: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Testing
- **Run all tests**: `pytest tests/`
- **Run with coverage**: `pytest --cov=app tests/`
- **Test specific module**: `pytest tests/services/test_intent_classifier.py`
- **Run test markers**: `pytest -m unit` or `pytest -m integration`
- **Test specific search functionality**: `python scripts/04-search/simple_nl_test.py`

### Docker Development
- **Build and run**: `docker-compose up --build`
- **Run tests in container**: `docker-compose -f docker-compose.test.yml up`

### Database Operations
- **Create migration**: `alembic revision --autogenerate -m "description"`
- **Apply migrations**: `alembic upgrade head`
- **Test DB connection**: `./scripts/02-envrinment/99-test-db-connection.sh`

## High-Level Architecture

### Core System Components
This is an insurance customer memo refinement system built on FastAPI with LLM-powered natural language processing.

**Main Application Stack**:
- **API Layer**: FastAPI with versioned routers in `app/routers/` (memo, customer, search, events, auth) - all endpoints prefixed with `/v1`
- **Business Logic**: Services in `app/services/` handle core functionality
- **Database**: PostgreSQL with pgvector for embeddings, SQLAlchemy ORM with async support
- **LLM Integration**: OpenAI GPT-4 via LangChain with LangSmith tracing

### Key Service Architecture

**LCEL SQL Pipeline** (`app/services/lcel_sql_pipeline.py`):
- Advanced NL-to-SQL conversion using LangChain Expression Language
- Retry logic with exponential backoff and fallback chains
- Streaming response support for real-time SQL generation
- Intent classification → SQL generation → validation chain

**Natural Language Search** (`app/services/nl_search_service.py`):
- Korean text processing with intent classification
- Multi-strategy search (customer info, memo search, event analysis, analytics)
- Vector similarity search using pgvector embeddings

**Memo Processing Pipeline**:
- **Quick Save**: Store raw memos (`/v1/api/memo/quick-save`)
- **AI Refinement**: Structure memos using LLM (`/v1/api/memo/refine`)
- **Conditional Analysis**: Context-aware memo analysis (`/v1/api/memo/analyze`)

**Excel Processing System**:
- Bulk customer data upload with intelligent column mapping
- Auto-detection of Korean column names → standardized fields
- Batch processing with validation and error handling

**Search Analytics System** (`app/services/search_analytics.py`):
- Real-time search performance tracking
- Popular query analysis and failure pattern detection
- Background task processing for analytics data

### Database Architecture
- **Main Models**: `app/db_models/` contains SQLAlchemy models
- **Async Operations**: All DB operations use async/await pattern
- **Read-Only Access**: Separate read-only database manager for queries
- **Vector Search**: pgvector extension for embedding-based search
- **Migrations**: Alembic for database schema management

### API Structure (All v1 Prefixed)
- **Memo API**: `/v1/api/memo/*` - Memo refinement and analysis
- **Customer API**: `/v1/api/customer/*` - Customer CRUD and Excel upload
- **Events API**: `/v1/api/events/*` - Event generation and management
- **Search API**: `/v1/api/search/*` - Natural language search with WebSocket streaming
- **LCEL SQL API**: `/v1/api/lcel-sql/*` - Advanced SQL generation pipeline
- **Search Analytics**: `/v1/api/search-analytics/*` - Search performance analytics
- **Authentication**: `/v1/auth/*` - JWT-based authentication
- **WebSocket**: `/ws/search/stream` - Real-time search streaming

### Development Environment
- **Local**: Uses PostgreSQL via Docker or scripts, OpenAI API for LLM
- **Test**: SQLite with in-memory database (configured in `conftest.py`)
- **Production**: AWS ECS deployment with RDS PostgreSQL

### Monitoring & Observability
- **CloudWatch**: Metrics and logging via `app/utils/cloudwatch_logger.py`
- **LangSmith**: LLM call tracing and debugging
- **Health Checks**: `/health` endpoint for system monitoring

## Environment Configuration

### Required Environment Variables
```bash
DATABASE_URL=postgresql://user:password@host:5432/database
OPENAI_API_KEY=your-openai-api-key
LANGSMITH_API_KEY=optional-langsmith-key  # For LLM tracing
LANGSMITH_PROJECT=insurance-memo-refiner
```

### Development Notes
- **KoNLPy Integration**: Korean NLP processing (may be disabled via `DISABLE_KONLPY=true`)
- **Mock Mode**: Set `OPENAI_API_KEY=test-key-for-local-development` for testing without API calls
- **SQL Logging**: Enable with `SQL_ECHO=true` for debugging database operations
- **Test Environment**: Automatically uses SQLite in test mode (see `conftest.py`)

## Key Service Interactions

### Memo Processing Flow
1. Raw memo input → `MemoRefinerService` 
2. LLM processing via LangChain → Structured output
3. Database storage with pgvector embeddings
4. Optional event generation via `EventService`

### Search Pipeline Flow
1. Natural language query → `IntentClassifier`
2. Multi-strategy execution (LLM-first, rule-based, hybrid)
3. SQL generation via `LCEL_SQL_Pipeline`
4. Query execution with read-only database manager
5. Results formatting and analytics tracking

### Customer Data Management
1. Excel upload → Column mapping via LLM
2. Data validation and transformation
3. Bulk customer creation with product associations
4. Search index updates for vector similarity

### Testing Strategy
- **Unit Tests**: Individual service testing with mocks
- **Integration Tests**: Full API endpoint testing
- **Performance Tests**: Search response time and concurrency
- **Search-Specific Tests**: Natural language query accuracy and SQL generation

## Critical Implementation Details

### Async Database Patterns
- All database operations use `AsyncSession`
- Read-only operations use separate connection pool
- Proper transaction management with rollback handling

### LLM Integration Patterns
- All LLM calls wrapped with retry logic and error handling
- LangSmith tracing for debugging and monitoring
- Streaming responses for real-time user feedback

### Search System Architecture
- Intent classification precedes SQL generation
- Multiple fallback strategies for query execution
- Real-time analytics collection via background tasks
- WebSocket streaming for progressive result delivery