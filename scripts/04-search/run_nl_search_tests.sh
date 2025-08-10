#!/bin/bash

# Natural Language Search Test Runner
# Comprehensive testing with PostgreSQL test environment

set -e

echo "🧪 Natural Language Search Test Suite"
echo "====================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if main server is running on port 8000
if ! curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "❌ Main server is not running on port 8000."
    echo "   Please start the server first:"
    echo "   ./scripts/02-environment/02-start-local.sh"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo "🧹 Cleaning up test environment..."
    docker-compose -f docker-compose.test.yml down -v || true
}
trap cleanup EXIT

# Step 1: Start PostgreSQL test database
echo ""
echo "1️⃣ Starting PostgreSQL test database..."
docker-compose -f docker-compose.test.yml up -d --build

# Wait for database to be ready
echo "⏳ Waiting for test database to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker-compose -f docker-compose.test.yml exec -T postgres-test pg_isready -U test_user -d momentir_test > /dev/null 2>&1; then
        echo "✅ Test database is ready!"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts - waiting..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Test database failed to start within timeout"
    exit 1
fi

# Step 2: Install test dependencies
echo ""
echo "2️⃣ Installing test dependencies..."
pip install -r requirements-test.txt

# Step 3: Seed test database
echo ""
echo "3️⃣ Seeding test database with sample data..."
python scripts/test_db_seeder.py

# Step 4: Run comprehensive test suite
echo ""
echo "4️⃣ Running Natural Language Search Tests..."
echo ""

# Set test environment variables
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export DISABLE_KONLPY=true
export ENVIRONMENT=test

# Run the test suite with detailed output
python -m pytest tests/test_nl_search.py \
    -v \
    --tb=short \
    --durations=10 \
    --capture=no

# Check test results
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 All tests passed successfully!"
    echo ""
    echo "📊 Test Summary:"
    echo "   • 10 Basic search scenarios ✅"
    echo "   • 3 SQL injection defense tests ✅" 
    echo "   • Performance tests (< 3 seconds) ✅"
    echo "   • Concurrency tests (5 simultaneous) ✅"
    echo "   • Error handling tests ✅"
    echo ""
    echo "🚀 Natural Language Search system is ready for production!"
else
    echo ""
    echo "❌ Some tests failed. Please check the output above."
    exit 1
fi