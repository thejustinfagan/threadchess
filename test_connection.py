"""Test Supabase connection"""
from db import supabase
import httpx

print("Testing Supabase connection...")
print(f"Supabase URL: {supabase.supabase_url}")

try:
    # Try a simple query
    result = supabase.table('games').select('id').limit(1).execute()
    print("✓ Connection successful!")
    print(f"✓ Can query games table")
    
    # Count total games
    all_games = supabase.table('games').select('id').execute()
    count = len(all_games.data) if all_games.data else 0
    print(f"✓ Found {count} game(s) in database")
    
except httpx.ConnectError as e:
    print(f"❌ Connection error: {e}")
    print("\nThis could mean:")
    print("1. The SUPABASE_URL is incorrect")
    print("2. Network connectivity issues")
    print("3. The Supabase project is paused or deleted")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


