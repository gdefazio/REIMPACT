#!/usr/bin/env python3
"""
Script to check your Scopus API quota status.

Usage:
    python check_scopus_quota.py YOUR_SCOPUS_API_KEY
"""

import sys
import requests


def check_api_key_resources(api_key: str):
    """Check which Elsevier resources (databases) the API key can access."""
    
    print()
    print("=" * 70)
    print("🔑 CHECKING API KEY RESOURCE ACCESS")
    print("=" * 70)
    print()
    
    # Different Elsevier API endpoints to test with appropriate queries
    resources = {
        "Scopus Search": {
            "url": "https://api.elsevier.com/content/search/scopus",
            "params": {"query": "TITLE(test)", "count": 1}
        },
        "ScienceDirect Search": {
            "url": "https://api.elsevier.com/content/search/sciencedirect",
            "params": {"query": "test", "count": 1}
        },
        "Abstract Retrieval": {
            "url": "https://api.elsevier.com/content/abstract/scopus_id/85021798849",
            "params": {}
        },
        "Author Search": {
            "url": "https://api.elsevier.com/content/search/author",
            "params": {"query": "authlast(smith)", "count": 1}
        },
        "Affiliation Search": {
            "url": "https://api.elsevier.com/content/search/affiliation",
            "params": {"query": "affil(university)", "count": 1}
        }
    }
    
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json"
    }
    
    print("Testing access to different Elsevier databases/resources...")
    print("-" * 70)
    
    accessible_resources = []
    inaccessible_resources = []
    
    for resource_name, resource_config in resources.items():
        try:
            url = resource_config["url"]
            params = resource_config["params"]
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                accessible_resources.append(resource_name)
                print(f"  ✅ {resource_name:<30} ACCESSIBLE")
            elif response.status_code == 401:
                inaccessible_resources.append(resource_name)
                print(f"  ❌ {resource_name:<30} NOT AUTHORIZED")
            elif response.status_code == 404:
                # 404 might mean the endpoint exists but resource not found (still accessible)
                accessible_resources.append(resource_name)
                print(f"  ✅ {resource_name:<30} ACCESSIBLE (404 - resource not found, but authorized)")
            else:
                inaccessible_resources.append(resource_name)
                print(f"  ? {resource_name:<30} UNKNOWN (status {response.status_code})")
                
        except requests.RequestException as e:
            print(f"  ❌ {resource_name:<30} ERROR: {type(e).__name__}")
            inaccessible_resources.append(resource_name)
    
    print("-" * 70)
    print()
    print(f"📊 SUMMARY:")
    print(f"  Accessible resources: {len(accessible_resources)}/{len(resources)}")
    if accessible_resources:
        print(f"  ✅ You can access: {', '.join(accessible_resources)}")
    if inaccessible_resources:
        print(f"  ❌ Not accessible: {', '.join(inaccessible_resources)}")
    print()
    
    return accessible_resources


def check_scopus_quota(api_key: str):
    """Check Scopus API quota by inspecting response headers."""
    
    print("=" * 70)
    print("🔍 CHECKING SCOPUS API QUOTA")
    print("=" * 70)
    print()
    
    # Use the Scopus Search API with a minimal query
    url = "https://api.elsevier.com/content/search/scopus"
    
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json"
    }
    
    params = {
        "query": "TITLE(test)",
        "count": 1  # Minimal result count
    }
    
    try:
        print("📡 Making test request to Scopus API...")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        print(f"✅ Response Status: {response.status_code} {response.reason}")
        print()
        
        # Extract quota information from headers
        print("📊 QUOTA INFORMATION:")
        print("-" * 70)
        
        quota_headers = {
            'X-RateLimit-Limit': 'Weekly Quota Limit',
            'X-RateLimit-Remaining': 'Weekly Quota Remaining',
            'X-RateLimit-Reset': 'Quota Reset Timestamp (Unix)',
            'X-ELS-Status': 'API Status',
            'X-ELS-ReqId': 'Request ID'
        }
        
        found_quota_info = False
        for header_key, description in quota_headers.items():
            value = response.headers.get(header_key)
            if value:
                found_quota_info = True
                print(f"  {description:.<40} {value}")
        
        if not found_quota_info:
            print("  ⚠️  No quota headers found in response")
            print()
            print("  Available headers:")
            for key in sorted(response.headers.keys()):
                print(f"    - {key}: {response.headers[key]}")
        
        print("-" * 70)
        print()
        
        # Calculate percentage if we have the data
        remaining = response.headers.get('X-RateLimit-Remaining')
        limit = response.headers.get('X-RateLimit-Limit')
        
        if remaining and limit:
            try:
                remaining_int = int(remaining)
                limit_int = int(limit)
                used = limit_int - remaining_int
                percentage_used = (used / limit_int) * 100
                percentage_remaining = (remaining_int / limit_int) * 100
                
                print(f"📈 USAGE SUMMARY:")
                print(f"  Total Weekly Limit: {limit_int:,} requests")
                print(f"  Used This Week: {used:,} requests ({percentage_used:.1f}%)")
                print(f"  Remaining: {remaining_int:,} requests ({percentage_remaining:.1f}%)")
                print()
                
                # Visual bar
                bar_length = 50
                filled = int(bar_length * percentage_used / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(f"  [{bar}] {percentage_used:.1f}%")
                print()
                
                if percentage_remaining < 10:
                    print("  ⚠️  WARNING: Less than 10% quota remaining!")
                elif percentage_remaining < 25:
                    print("  ⚡ CAUTION: Less than 25% quota remaining")
                else:
                    print("  Quota status: Good ✅")
                    
            except ValueError:
                print("  ⚠️  Unable to parse quota numbers")
        
        print()
        
        # Show reset time if available
        reset_timestamp = response.headers.get('X-RateLimit-Reset')
        if reset_timestamp:
            try:
                import datetime
                reset_time = datetime.datetime.fromtimestamp(int(reset_timestamp))
                now = datetime.datetime.now()
                time_until_reset = reset_time - now
                
                print(f"⏰ RESET INFORMATION:")
                print(f"  Quota resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                if time_until_reset.total_seconds() > 0:
                    hours = int(time_until_reset.total_seconds() // 3600)
                    minutes = int((time_until_reset.total_seconds() % 3600) // 60)
                    print(f"  Time until reset: {hours}h {minutes}m")
                else:
                    print(f"  Quota should have reset (check again)")
                    
            except (ValueError, OSError):
                print(f"  ⚠️  Unable to parse reset timestamp: {reset_timestamp}")
        
        print()
        print("=" * 70)
        
        # Check if request was successful
        if response.status_code == 200:
            print("✅ API key is valid and working")
            return True
        elif response.status_code == 401:
            print("❌ ERROR: Invalid API key or unauthorized")
            return False
        elif response.status_code == 429:
            print("❌ ERROR: Rate limit exceeded - quota exhausted!")
            return False
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ ERROR: Unable to connect to Scopus API")
        print(f"   {type(e).__name__}: {e}")
        print()
        print("   Possible causes:")
        print("   - No internet connection")
        print("   - Firewall blocking access")
        print("   - Need to be on institutional network")
        print("   - VPN/proxy not supported by Scopus")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_scopus_quota.py YOUR_SCOPUS_API_KEY")
        print()
        sys.exit(1)
    
    api_key = sys.argv[1]
    
    if not api_key or len(api_key) < 20:
        print("ERROR: API key seems invalid (too short)")
        sys.exit(1)
    
    # First check which resources are accessible
    accessible = check_api_key_resources(api_key)
    
    # Then check quota if Scopus is accessible
    if "Scopus Search" in accessible:
        success = check_scopus_quota(api_key)
    else:
        print("⚠️  Skipping quota check - Scopus Search not accessible")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
