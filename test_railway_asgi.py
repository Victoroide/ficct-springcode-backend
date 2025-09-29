#!/usr/bin/env python
"""
Test script para verificar Railway ASGI deployment
"""

import asyncio
import websockets
import json
import requests
from urllib.parse import urljoin

# Configuración 
BASE_URL = "https://dev.api.diagrams.ficct.com"
WS_URL = "wss://dev.api.diagrams.ficct.com"

async def test_websocket_connection():
    """Test básico de conexión WebSocket"""
    print("🔌 Testing WebSocket Connection...")
    
    # Crear un diagrama primero para obtener ID válido
    try:
        api_response = requests.get(f"{BASE_URL}/api/diagrams/")
        if api_response.status_code == 200:
            diagrams = api_response.json().get('results', [])
            if diagrams:
                diagram_id = diagrams[0]['id']
                print(f"✅ Using existing diagram: {diagram_id}")
            else:
                print("⚠️  No diagrams found, creating test WebSocket URL")
                diagram_id = "test-diagram-id"
        else:
            print(f"❌ API call failed: {api_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False

    # Test WebSocket connection
    ws_url = f"{WS_URL}/ws/diagrams/{diagram_id}/test-session/"
    
    try:
        print(f"📡 Connecting to: {ws_url}")
        
        async with websockets.connect(
            ws_url,
            timeout=10,
            ping_interval=20,
            ping_timeout=10
        ) as websocket:
            print("✅ WebSocket connected successfully!")
            
            # Send test message
            test_message = {
                "type": "ping",
                "timestamp": "2025-01-01T00:00:00Z"
            }
            
            await websocket.send(json.dumps(test_message))
            print("📤 Test message sent")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Response received: {response}")
                return True
                
            except asyncio.TimeoutError:
                print("⚠️  No response within 5 seconds (might be normal)")
                return True  # Connection worked, no response is OK
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
        return False
        
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False

def test_http_api():
    """Test HTTP API endpoints"""
    print("\n🌐 Testing HTTP API...")
    
    endpoints = [
        "/api/health/",
        "/api/diagrams/",
        "/docs/",
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            url = urljoin(BASE_URL, endpoint)
            response = requests.get(url, timeout=10)
            
            if response.status_code < 400:
                print(f"✅ {endpoint} - Status: {response.status_code}")
                results.append(True)
            else:
                print(f"❌ {endpoint} - Status: {response.status_code}")
                results.append(False)
                
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")
            results.append(False)
    
    return all(results)

async def main():
    """Run all tests"""
    print("🚀 Railway ASGI Deployment Test")
    print("=" * 40)
    
    # Test HTTP API
    http_ok = test_http_api()
    
    # Test WebSocket
    ws_ok = await test_websocket_connection()
    
    # Summary
    print("\n" + "=" * 40)
    print("📋 Test Results:")
    print(f"   HTTP API: {'✅ PASS' if http_ok else '❌ FAIL'}")
    print(f"   WebSocket: {'✅ PASS' if ws_ok else '❌ FAIL'}")
    
    if http_ok and ws_ok:
        print("\n🎉 Railway ASGI deployment working correctly!")
        print("✅ Both HTTP and WebSocket on same domain/port")
    else:
        print("\n⚠️  Issues detected with Railway deployment")
        
        if not http_ok:
            print("   - Check Railway deployment logs")
            print("   - Verify environment variables")
            
        if not ws_ok:
            print("   - Check WebSocket routing")
            print("   - Verify ASGI application config")

if __name__ == "__main__":
    asyncio.run(main())
