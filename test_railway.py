#!/usr/bin/env python
"""
Test script to validate Railway deployment configuration.
"""
import os
import sys
import django
from django.conf import settings

def test_railway_config():
    """Test Railway deployment configuration."""
    
    # Set environment for production
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
    os.environ.setdefault('DEBUG', 'False')
    os.environ.setdefault('PORT', '8000')
    
    # Initialize Django
    django.setup()
    
    print("PASS Django Configuration Test")
    print(f"DEBUG: {settings.DEBUG}")
    print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    print(f"SECRET_KEY: {'SET' if settings.SECRET_KEY else 'NOT SET'}")
    
    # Test database connection
    try:
        from django.db import connection
        connection.ensure_connection()
        print("PASS Database connection: OK")
    except Exception as e:
        print(f"FAIL Database connection: {e}")
    
    # Test health endpoint
    try:
        from base.urls import api_health_check
        print("PASS Health endpoint: Available")
    except Exception as e:
        print(f"FAIL Health endpoint: {e}")
    
    # Test API endpoint
    try:
        from base.api_schema import api_schema_view
        print("PASS API schema endpoint: Available")
    except Exception as e:
        print(f"FAIL API schema endpoint: {e}")

if __name__ == '__main__':
    test_railway_config()
