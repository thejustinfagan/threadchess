"""
Diagnostic script to check Supabase connection and provide solutions
"""
from dotenv import load_dotenv
import os
import socket

load_dotenv()

print("=" * 60)
print("Supabase Connection Diagnostic")
print("=" * 60)

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print(f"\n1. Checking credentials...")
print(f"   SUPABASE_URL: {url if url else '❌ NOT SET'}")
print(f"   SUPABASE_KEY: {'✓ SET' if key else '❌ NOT SET'} ({len(key) if key else 0} chars)")

if not url or not key:
    print("\n❌ Missing credentials! Please check your .env file.")
    exit(1)

# Extract hostname from URL
try:
    hostname = url.replace('https://', '').replace('http://', '').split('/')[0]
    print(f"\n2. Testing DNS resolution for: {hostname}")
    
    try:
        ip = socket.gethostbyname(hostname)
        print(f"   ✓ DNS resolved to: {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS resolution FAILED: {e}")
        print(f"\n   This means the Supabase project is likely:")
        print(f"   - PAUSED (free tier projects pause after inactivity)")
        print(f"   - DELETED")
        print(f"   - URL is INCORRECT")
        print(f"\n   SOLUTION:")
        print(f"   1. Go to https://app.supabase.com")
        print(f"   2. Check if your project exists and is active")
        print(f"   3. If paused, click 'Restore project'")
        print(f"   4. Verify the Project URL in Settings → API")
        exit(1)
    
    print(f"\n3. Testing Supabase connection...")
    from db import supabase
    try:
        result = supabase.table('games').select('id').limit(1).execute()
        print(f"   ✓ Connection successful!")
        
        # Count games
        all_games = supabase.table('games').select('id').execute()
        count = len(all_games.data) if all_games.data else 0
        print(f"   ✓ Found {count} game(s) in database")
        
        if count > 0:
            print(f"\n   You can now run: python clear_games.py")
        else:
            print(f"\n   Database is already empty!")
            
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print(f"\n   Even though DNS works, the API connection failed.")
        print(f"   Check your SUPABASE_KEY in the .env file.")
        
except Exception as e:
    print(f"\n❌ Error parsing URL: {e}")

print("\n" + "=" * 60)


