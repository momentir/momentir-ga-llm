#!/usr/bin/env python3
"""
Simple Natural Language Search Test
Quick validation of core functionality
"""
import asyncio
import httpx
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def simple_test():
    """Run a simple test of NL search functionality"""
    
    print("🧪 Simple Natural Language Search Test")
    print("=====================================")
    
    # Test server health first
    print("\n1️⃣ Checking server health...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://127.0.0.1:8000/health")
            if response.status_code != 200:
                print("❌ Server is not healthy")
                return False
            print("✅ Server is running")
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            print("   Make sure the server is running on port 8000")
            return False
    
    # Test basic search functionality
    print("\n2️⃣ Testing basic search functionality...")
    
    test_queries = [
        "고객 목록",
        "홍길동 정보",
        "화재보험 고객"
    ]
    
    search_endpoint = "http://127.0.0.1:8000/api/search/natural-language"
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n   Test {i}: '{query}'")
        
        request_data = {
            "query": query,
            "options": {"strategy": "llm_first"},
            "limit": 5
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                start_time = time.time()
                response = await client.post(search_endpoint, json=request_data)
                end_time = time.time()
                
                response_time = end_time - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        data_count = len(result.get("data", []))
                        print(f"   ✅ Success - {data_count} records found ({response_time:.2f}s)")
                    else:
                        print(f"   ⚠️  Query processed but no results: {result.get('error', 'Unknown')}")
                else:
                    print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}...")
            
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
                return False
    
    print("\n🎉 Simple test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(simple_test())
    if not success:
        sys.exit(1)