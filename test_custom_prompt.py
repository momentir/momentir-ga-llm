#!/usr/bin/env python3
import requests
import json
import time

def test_custom_prompt():
    url = "http://localhost:8000/api/memo/refine"
    
    # Test 1: Without custom_prompt
    print("=== Test 1: Without custom_prompt ===")
    data1 = {"memo": "테스트 메모"}
    try:
        response1 = requests.post(url, json=data1, timeout=10)
        print(f"Status: {response1.status_code}")
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"Summary: {result1.get('summary', 'N/A')}")
        else:
            print(f"Error: {response1.text}")
    except Exception as e:
        print(f"Exception: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: With custom_prompt
    print("=== Test 2: With custom_prompt ===")
    data2 = {
        "memo": "테스트 메모", 
        "custom_prompt": "간단히 말하면: {memo}"
    }
    try:
        print("Sending request...")
        response2 = requests.post(url, json=data2, timeout=15)
        print(f"Status: {response2.status_code}")
        if response2.status_code == 200:
            result2 = response2.json()
            print(f"Summary: {result2.get('summary', 'N/A')}")
        else:
            print(f"Error: {response2.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_custom_prompt()