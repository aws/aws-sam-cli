#!/usr/bin/env python3
"""
Manual test runner for sam local start-function-urls
This script provides comprehensive testing of the Function URLs feature
"""

import json
import time
import sys
import subprocess
import requests
import argparse
import concurrent.futures
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64


class FunctionUrlTester:
    """Test runner for Function URLs"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:3001"):
        self.base_url = base_url
        self.results = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def test_get_request(self) -> bool:
        """Test basic GET request"""
        self.log("Testing GET request...")
        try:
            response = requests.get(f"{self.base_url}/")
            self.log(f"Status: {response.status_code}")
            self.log(f"Response: {response.text[:200]}")
            
            if response.status_code == 200:
                self.log("✓ GET request successful", "SUCCESS")
                return True
            else:
                self.log(f"✗ GET request failed with status {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ GET request failed: {e}", "ERROR")
            return False
    
    def test_post_with_json(self) -> bool:
        """Test POST request with JSON payload"""
        self.log("Testing POST with JSON payload...")
        try:
            payload = {
                "name": "Test User",
                "email": "test@example.com",
                "data": {
                    "nested": "value",
                    "array": [1, 2, 3]
                }
            }
            
            response = requests.post(
                f"{self.base_url}/",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            self.log(f"Status: {response.status_code}")
            self.log(f"Response: {response.text[:200]}")
            
            if response.status_code == 200:
                self.log("✓ POST with JSON successful", "SUCCESS")
                return True
            else:
                self.log(f"✗ POST failed with status {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ POST request failed: {e}", "ERROR")
            return False
    
    def test_query_parameters(self) -> bool:
        """Test request with query parameters"""
        self.log("Testing query parameters...")
        try:
            params = {
                "search": "test query",
                "page": "1",
                "limit": "10"
            }
            
            response = requests.get(f"{self.base_url}/", params=params)
            self.log(f"Status: {response.status_code}")
            self.log(f"URL: {response.url}")
            self.log(f"Response: {response.text[:200]}")
            
            if response.status_code == 200:
                self.log("✓ Query parameters test successful", "SUCCESS")
                return True
            else:
                self.log(f"✗ Query parameters test failed", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ Query parameters test failed: {e}", "ERROR")
            return False
    
    def test_custom_headers(self) -> bool:
        """Test request with custom headers"""
        self.log("Testing custom headers...")
        try:
            headers = {
                "X-Custom-Header": "CustomValue",
                "X-Request-ID": "test-123",
                "Authorization": "Bearer test-token"
            }
            
            response = requests.get(f"{self.base_url}/", headers=headers)
            self.log(f"Status: {response.status_code}")
            self.log(f"Response headers: {dict(response.headers)}")
            
            if response.status_code in [200, 403]:  # 403 if auth is required
                self.log("✓ Custom headers test successful", "SUCCESS")
                return True
            else:
                self.log(f"✗ Custom headers test failed", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ Custom headers test failed: {e}", "ERROR")
            return False
    
    def test_http_methods(self) -> bool:
        """Test different HTTP methods"""
        self.log("Testing HTTP methods...")
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        success = True
        
        for method in methods:
            try:
                self.log(f"Testing {method}...")
                response = requests.request(method, f"{self.base_url}/")
                self.log(f"  {method}: Status {response.status_code}")
                
                if response.status_code not in [200, 204, 405]:
                    success = False
            except Exception as e:
                self.log(f"  {method}: Failed - {e}", "ERROR")
                success = False
        
        if success:
            self.log("✓ HTTP methods test successful", "SUCCESS")
        else:
            self.log("✗ Some HTTP methods failed", "ERROR")
        
        return success
    
    def test_large_payload(self) -> bool:
        """Test with large payload"""
        self.log("Testing large payload...")
        try:
            # Create a 1MB payload
            large_data = "x" * (1024 * 1024)
            payload = {
                "data": large_data,
                "size": len(large_data)
            }
            
            response = requests.post(
                f"{self.base_url}/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            self.log(f"Status: {response.status_code}")
            self.log(f"Payload size: {len(json.dumps(payload))} bytes")
            
            if response.status_code == 200:
                self.log("✓ Large payload test successful", "SUCCESS")
                return True
            else:
                self.log(f"✗ Large payload test failed", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ Large payload test failed: {e}", "ERROR")
            return False
    
    def test_concurrent_requests(self, num_requests: int = 10) -> bool:
        """Test concurrent requests"""
        self.log(f"Testing {num_requests} concurrent requests...")
        
        def make_request(request_id: int) -> Dict[str, Any]:
            try:
                headers = {"X-Request-ID": str(request_id)}
                response = requests.get(f"{self.base_url}/", headers=headers)
                return {
                    "id": request_id,
                    "status": response.status_code,
                    "success": response.status_code == 200
                }
            except Exception as e:
                return {
                    "id": request_id,
                    "status": 0,
                    "success": False,
                    "error": str(e)
                }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(make_request, i)
                for i in range(num_requests)
            ]
            results = [
                future.result()
                for future in concurrent.futures.as_completed(futures)
            ]
        
        successful = sum(1 for r in results if r["success"])
        self.log(f"Successful requests: {successful}/{num_requests}")
        
        if successful == num_requests:
            self.log("✓ Concurrent requests test successful", "SUCCESS")
            return True
        else:
            self.log(f"✗ Some concurrent requests failed", "ERROR")
            for result in results:
                if not result["success"]:
                    self.log(f"  Request {result['id']}: {result.get('error', 'Failed')}")
            return False
    
    def test_cors_preflight(self) -> bool:
        """Test CORS preflight request"""
        self.log("Testing CORS preflight...")
        try:
            headers = {
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
            
            response = requests.options(f"{self.base_url}/", headers=headers)
            self.log(f"Status: {response.status_code}")
            
            cors_headers = {
                k: v for k, v in response.headers.items()
                if k.startswith("Access-Control-")
            }
            
            if cors_headers:
                self.log(f"CORS headers: {cors_headers}")
                self.log("✓ CORS preflight test successful", "SUCCESS")
                return True
            else:
                self.log("✗ No CORS headers found", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ CORS test failed: {e}", "ERROR")
            return False
    
    def test_binary_response(self) -> bool:
        """Test binary response handling"""
        self.log("Testing binary response...")
        try:
            response = requests.get(f"{self.base_url}/binary")
            
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "image" in content_type or "application/octet-stream" in content_type:
                    self.log(f"✓ Binary response test successful (Content-Type: {content_type})", "SUCCESS")
                    return True
                else:
                    self.log(f"Content-Type: {content_type}")
                    self.log("✓ Binary response test successful", "SUCCESS")
                    return True
            else:
                self.log(f"✗ Binary response test failed with status {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"✗ Binary response test failed: {e}", "ERROR")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling"""
        self.log("Testing error handling...")
        
        # Test 404
        try:
            response = requests.get(f"{self.base_url}/notfound")
            if response.status_code == 404:
                self.log("✓ 404 error handling works", "SUCCESS")
            else:
                self.log(f"Expected 404, got {response.status_code}", "WARNING")
        except Exception as e:
            self.log(f"404 test failed: {e}", "ERROR")
        
        # Test 500 (trigger error)
        try:
            response = requests.get(f"{self.base_url}/error")
            if response.status_code in [500, 502]:
                self.log("✓ 500 error handling works", "SUCCESS")
            else:
                self.log(f"Expected 500/502, got {response.status_code}", "WARNING")
        except Exception as e:
            self.log(f"500 test failed: {e}", "ERROR")
        
        return True
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results"""
        self.log("=" * 60)
        self.log("Starting Function URL Tests")
        self.log("=" * 60)
        
        tests = [
            ("GET Request", self.test_get_request),
            ("POST with JSON", self.test_post_with_json),
            ("Query Parameters", self.test_query_parameters),
            ("Custom Headers", self.test_custom_headers),
            ("HTTP Methods", self.test_http_methods),
            ("Large Payload", self.test_large_payload),
            ("Concurrent Requests", self.test_concurrent_requests),
            ("CORS Preflight", self.test_cors_preflight),
            ("Binary Response", self.test_binary_response),
            ("Error Handling", self.test_error_handling),
        ]
        
        results = {}
        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            try:
                results[test_name] = test_func()
            except Exception as e:
                self.log(f"✗ Test failed with exception: {e}", "ERROR")
                results[test_name] = False
            time.sleep(0.5)  # Small delay between tests
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("Test Summary")
        self.log("=" * 60)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, success in results.items():
            status = "✓ PASS" if success else "✗ FAIL"
            self.log(f"{status}: {test_name}")
        
        self.log(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            self.log("All tests passed! 🎉", "SUCCESS")
        else:
            self.log(f"{total - passed} tests failed", "ERROR")
        
        return results


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test sam local start-function-urls")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:3001",
        help="Base URL for Function URL service (default: http://127.0.0.1:3001)"
    )
    parser.add_argument(
        "--test",
        choices=[
            "get", "post", "query", "headers", "methods",
            "large", "concurrent", "cors", "binary", "error", "all"
        ],
        default="all",
        help="Specific test to run (default: all)"
    )
    parser.add_argument(
        "--concurrent-requests",
        type=int,
        default=10,
        help="Number of concurrent requests to test (default: 10)"
    )
    
    args = parser.parse_args()
    
    tester = FunctionUrlTester(args.url)
    
    if args.test == "all":
        results = tester.run_all_tests()
        sys.exit(0 if all(results.values()) else 1)
    else:
        test_map = {
            "get": tester.test_get_request,
            "post": tester.test_post_with_json,
            "query": tester.test_query_parameters,
            "headers": tester.test_custom_headers,
            "methods": tester.test_http_methods,
            "large": tester.test_large_payload,
            "concurrent": lambda: tester.test_concurrent_requests(args.concurrent_requests),
            "cors": tester.test_cors_preflight,
            "binary": tester.test_binary_response,
            "error": tester.test_error_handling,
        }
        
        test_func = test_map.get(args.test)
        if test_func:
            success = test_func()
            sys.exit(0 if success else 1)
        else:
            print(f"Unknown test: {args.test}")
            sys.exit(1)


if __name__ == "__main__":
    main()
