#!/usr/bin/env python
"""
Simple test script to fetch news without database dependencies
"""
import sys
import os
from pathlib import Path

# Suppress DB connection errors
os.environ['DATABASE_URL'] = ''
os.environ['POSTGRES_URL'] = ''

try:
    from data.pipeline import _run_ngx_announcements, _run_businessday
    
    print("=" * 60)
    print("Testing NGX Announcements Fetcher...")
    print("=" * 60)
    try:
        _run_ngx_announcements()
        print("\n✓ NGX Announcements completed")
    except Exception as e:
        print(f"\n✗ NGX failed: {e}")
    
    print("\n" + "=" * 60)
    print("Testing BusinessDay Fetcher...")
    print("=" * 60)
    try:
        _run_businessday()
        print("\n✓ BusinessDay completed")
    except Exception as e:
        print(f"\n✗ BusinessDay failed: {e}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
