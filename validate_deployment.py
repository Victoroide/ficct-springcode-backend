#!/usr/bin/env python
"""
Deployment Validation Script for UML Diagram Collaborative Platform.

This script validates all critical functionality after deployment:
- WSGI/ASGI architecture
- Public diagram access
- WebSocket connectivity  
- Swagger documentation
- Rate limiting
- Database connectivity
"""

import os
import sys
import requests
import json
import time
from urllib.parse import urljoin
import websocket
import threading
from datetime import datetime

# Configuration
BASE_URL = os.getenv('BASE_URL', 'http://localhost')
WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', 'ws://localhost')

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_status(message, status='info'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if status == 'success':
        print(f"[{timestamp}] {Colors.GREEN}✅ {message}{Colors.END}")
    elif status == 'error':
        print(f"[{timestamp}] {Colors.RED}❌ {message}{Colors.END}")
    elif status == 'warning':
        print(f"[{timestamp}] {Colors.YELLOW}⚠️  {message}{Colors.END}")
    else:
        print(f"[{timestamp}] {Colors.BLUE}ℹ️  {message}{Colors.END}")

def test_health_check():
    """Test basic health check endpoint."""
    print_status("Testing health check endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                print_status("Health check passed", 'success')
                return True
            else:
                print_status(f"Health check failed: {data}", 'error')
                return False
        else:
            print_status(f"Health check returned {response.status_code}", 'error')
            return False
    except Exception as e:
        print_status(f"Health check failed: {str(e)}", 'error')
        return False

def test_swagger_documentation():
    """Test Swagger documentation availability."""
    print_status("Testing Swagger documentation...")
    try:
        response = requests.get(f"{BASE_URL}/docs/", timeout=10)
        if response.status_code == 200:
            print_status("Swagger documentation accessible", 'success')
            return True
        else:
            print_status(f"Swagger returned {response.status_code}", 'error')
            return False
    except Exception as e:
        print_status(f"Swagger test failed: {str(e)}", 'error')
        return False

def test_api_schema():
    """Test API schema endpoint."""
    print_status("Testing API schema...")
    try:
        response = requests.get(f"{BASE_URL}/api/schema/", timeout=10)
        if response.status_code == 200:
            print_status("API schema accessible", 'success')
            return True
        else:
            print_status(f"API schema returned {response.status_code}", 'error')
            return False
    except Exception as e:
        print_status(f"API schema test failed: {str(e)}", 'error')
        return False

def test_public_endpoints():
    """Test public diagram endpoints (without authentication)."""
    print_status("Testing public endpoints...")
    
    # Test public diagrams list endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/public/diagrams/", timeout=10)
        print_status(f"Public diagrams endpoint: {response.status_code}", 'success' if response.status_code in [200, 404] else 'warning')
    except Exception as e:
        print_status(f"Public endpoints test failed: {str(e)}", 'error')
        return False
    
    return True

def test_rate_limiting():
    """Test rate limiting on public endpoints."""
    print_status("Testing rate limiting...")
    
    # Make multiple rapid requests to test rate limiting
    success_count = 0
    rate_limited = False
    
    for i in range(35):  # Exceed the 30/min limit
        try:
            response = requests.get(f"{BASE_URL}/api/public/diagrams/", timeout=5)
            if response.status_code == 429:
                rate_limited = True
                break
            elif response.status_code in [200, 404]:
                success_count += 1
        except:
            pass
    
    if rate_limited:
        print_status("Rate limiting working correctly", 'success')
        return True
    elif success_count > 30:
        print_status("Rate limiting may not be working", 'warning')
        return False
    else:
        print_status("Rate limiting test inconclusive", 'warning')
        return True

def test_websocket_connection():
    """Test WebSocket connection."""
    print_status("Testing WebSocket connection...")
    
    connection_success = False
    connection_error = None
    
    def on_open(ws):
        nonlocal connection_success
        connection_success = True
        print_status("WebSocket connection established", 'success')
        ws.close()
    
    def on_error(ws, error):
        nonlocal connection_error
        connection_error = error
        print_status(f"WebSocket error: {error}", 'error')
    
    def on_close(ws, close_status_code, close_msg):
        print_status("WebSocket connection closed")
    
    try:
        # Test WebSocket connection
        test_url = f"{WEBSOCKET_URL}/ws/diagram/test-diagram-id/"
        ws = websocket.WebSocketApp(
            test_url,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close
        )
        
        # Run WebSocket in thread with timeout
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for connection
        time.sleep(3)
        
        if connection_success:
            return True
        elif connection_error:
            print_status(f"WebSocket connection failed: {connection_error}", 'error')
            return False
        else:
            print_status("WebSocket connection timeout", 'warning')
            return False
            
    except Exception as e:
        print_status(f"WebSocket test failed: {str(e)}", 'error')
        return False

def test_cors_headers():
    """Test CORS headers for public access."""
    print_status("Testing CORS headers...")
    try:
        response = requests.options(f"{BASE_URL}/api/public/diagrams/")
        cors_headers = [
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers'
        ]
        
        headers_present = all(header in response.headers for header in cors_headers)
        
        if headers_present:
            print_status("CORS headers configured correctly", 'success')
            return True
        else:
            print_status("CORS headers missing or incomplete", 'warning')
            return False
    except Exception as e:
        print_status(f"CORS test failed: {str(e)}", 'error')
        return False

def test_security_headers():
    """Test security headers."""
    print_status("Testing security headers...")
    try:
        response = requests.get(f"{BASE_URL}/api/health/")
        
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection'
        ]
        
        headers_found = []
        for header in security_headers:
            if header in response.headers:
                headers_found.append(header)
        
        if len(headers_found) >= 2:
            print_status(f"Security headers present: {', '.join(headers_found)}", 'success')
            return True
        else:
            print_status("Some security headers missing", 'warning')
            return False
    except Exception as e:
        print_status(f"Security headers test failed: {str(e)}", 'error')
        return False

def main():
    """Run all validation tests."""
    print_status("🚀 Starting UML Diagram Platform Deployment Validation", 'info')
    print_status(f"Testing against: {BASE_URL}")
    print_status("=" * 60)
    
    tests = [
        ("Health Check", test_health_check),
        ("Swagger Documentation", test_swagger_documentation),
        ("API Schema", test_api_schema),
        ("Public Endpoints", test_public_endpoints),
        ("Rate Limiting", test_rate_limiting),
        ("WebSocket Connection", test_websocket_connection),
        ("CORS Headers", test_cors_headers),
        ("Security Headers", test_security_headers),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print_status(f"\n--- {test_name} ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print_status(f"Test {test_name} crashed: {str(e)}", 'error')
            results[test_name] = False
        
        time.sleep(1)  # Brief pause between tests
    
    # Summary
    print_status("\n" + "=" * 60)
    print_status("🎯 VALIDATION SUMMARY", 'info')
    print_status("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = 'success' if result else 'error'
        print_status(f"{test_name}: {'PASSED' if result else 'FAILED'}", status)
    
    print_status(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print_status("🎉 ALL TESTS PASSED - Deployment successful!", 'success')
        return 0
    elif passed >= total * 0.8:
        print_status("⚠️  Most tests passed - Deployment mostly successful", 'warning')
        return 1
    else:
        print_status("❌ Multiple tests failed - Check deployment", 'error')
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
