"""Check the games table structure"""
from db import supabase

print("Checking games table structure...")

try:
    # Try to get all columns by selecting all
    result = supabase.table('games').select('*').limit(1).execute()
    
    if result.data and len(result.data) > 0:
        print("\n✓ Table structure:")
        for key in result.data[0].keys():
            print(f"  - {key}")
        
        # Get the primary key - try common names
        first_row = result.data[0]
        possible_keys = ['id', 'game_id', 'gameid', 'pk', 'uuid']
        found_key = None
        for key in possible_keys:
            if key in first_row:
                found_key = key
                break
        
        if found_key:
            print(f"\n✓ Primary key appears to be: {found_key}")
        else:
            print(f"\n⚠ Could not identify primary key. Columns: {list(first_row.keys())}")
            
        # Count games
        all_games = supabase.table('games').select('*').execute()
        count = len(all_games.data) if all_games.data else 0
        print(f"\n✓ Found {count} game(s) in database")
        
    else:
        print("✓ Table exists but is empty (no rows)")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


