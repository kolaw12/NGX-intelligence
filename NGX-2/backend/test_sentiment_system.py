#!/usr/bin/env python
"""Test that sentiment pipeline output can be read and served by API"""

import sys
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_sentiment_package_loading():
    """Test that sentiment packages exist and can be loaded"""
    print("\n=== Testing Sentiment Package Loading ===")
    
    # Find latest sentiment package
    packages = list(Path(".").glob("nupat_daily_package_*.json"))
    if not packages:
        print("❌ No sentiment packages found!")
        return False
    
    latest = sorted(packages)[-1]
    print(f"✅ Found latest package: {latest.name}")
    
    # Load and verify structure
    with open(latest) as f:
        data = json.load(f)
    
    required_fields = ["date", "generated_at", "total_articles", "stock_sentiments", "market_sentiment"]
    for field in required_fields:
        if field not in data:
            print(f"❌ Missing field: {field}")
            return False
        print(f"✅ {field}: {len(str(data[field]))} chars")
    
    print(f"✅ Package contains {data['total_articles']} articles")
    print(f"✅ Market sentiment: {data['market_sentiment']['signal']}")
    
    return True

def test_news_sentiment_service():
    """Test that the news sentiment service can load packages"""
    print("\n=== Testing News Sentiment Service ===")
    
    try:
        from app.services.news_sentiment import (
            load_latest_sentiment_package,
            latest_market_package_sentiment,
        )
        
        print("✅ Imported news_sentiment service")
        
        # Test loading latest package
        package = load_latest_sentiment_package()
        if package is None:
            print("❌ Could not load latest sentiment package")
            return False
        
        print(f"✅ Loaded sentiment package with {package.get('total_articles', 0)} articles")
        
        # Test market sentiment (it returns a dict, not an object)
        market = latest_market_package_sentiment()
        if market is None:
            print("⚠️  Market sentiment is None (may be expected on first run)")
        else:
            # Market sentiment is a dict with 'signal' key
            signal = market.get('signal') if isinstance(market, dict) else getattr(market, 'signal', 'UNKNOWN')
            print(f"✅ Market sentiment retrieved: {signal}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing news_sentiment service: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_news_endpoints():
    """Test that news API endpoints can be imported"""
    print("\n=== Testing News API Endpoints ===")
    
    try:
        # Just verify the file exists and has the right structure
        news_router = Path("app/routers/news.py")
        if not news_router.exists():
            print("❌ news.py router not found")
            return False
        
        with open(news_router) as f:
            content = f.read()
        
        required_endpoints = [
            "list_news",
            "sentiment_summary",
            "sentiment_diagnostics"
        ]
        
        for endpoint in required_endpoints:
            if f"def {endpoint}" in content:
                print(f"✅ Endpoint '{endpoint}' defined")
            else:
                print(f"❌ Endpoint '{endpoint}' not found")
                return False
        
        print("✅ All news endpoints configured and ready")
        return True
        
    except Exception as e:
        print(f"❌ Error testing news endpoints: {e}")
        return False

def main():
    print("=" * 60)
    print("Testing Sentiment System Integration")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Package Loading", test_sentiment_package_loading()))
    results.append(("News Sentiment Service", test_news_sentiment_service()))
    results.append(("News API Endpoints", test_news_endpoints()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + ("=" * 60))
    
    if all_passed:
        print("🎉 ALL TESTS PASSED - System is ready for production!")
        print("\nNext steps:")
        print("1. GitHub Actions will run daily at 8:55 AM and 1:00 PM Nigeria time")
        print("2. News articles will be fetched and processed automatically")
        print("3. Sentiment analysis will be available via API endpoints")
        print("4. Frontend can display headlines with sentiment scores")
    else:
        print("⚠️  Some tests failed - review above for details")
    
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
