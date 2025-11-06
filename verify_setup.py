"""
Verify that everything is set up correctly after improvements
"""
import sys
import os

print("=" * 60)
print("Verifying Setup After Improvements")
print("=" * 60)

# 1. Check imports
print("\n1. Checking imports...")
try:
    from db import create_game, get_game_by_thread_id, update_game_after_shot, increment_bot_post_count
    print("   ✓ db.py imports work")
except Exception as e:
    print(f"   ❌ db.py import error: {e}")
    sys.exit(1)

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))
    from game_logic import create_new_board, process_shot, copy_board
    print("   ✓ game_logic.py imports work")
except Exception as e:
    print(f"   ❌ game_logic.py import error: {e}")
    sys.exit(1)

try:
    from image_generator import generate_board_image
    print("   ✓ image_generator.py imports work")
except Exception as e:
    print(f"   ❌ image_generator.py import error: {e}")
    sys.exit(1)

# 2. Check environment variables
print("\n2. Checking environment variables...")
from dotenv import load_dotenv
load_dotenv()

required_vars = [
    'SUPABASE_URL', 'SUPABASE_KEY',
    'BEARER_TOKEN', 'X_API_KEY', 'X_API_SECRET',
    'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET'
]

missing = []
for var in required_vars:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print(f"   ⚠ Missing: {', '.join(missing)}")
else:
    print("   ✓ All required environment variables are set")

# 3. Check database connection
print("\n3. Checking database connection...")
try:
    from db import supabase
    result = supabase.table('games').select('thread_id').limit(1).execute()
    print("   ✓ Database connection works")
    print(f"   ✓ Can query games table")
except Exception as e:
    print(f"   ❌ Database connection error: {e}")

# 4. Check database schema vs code expectations
print("\n4. Checking database schema compatibility...")
try:
    # Try to get a sample game structure
    sample = supabase.table('games').select('*').limit(1).execute()
    if sample.data:
        columns = list(sample.data[0].keys())
        print(f"   ✓ Database columns: {', '.join(columns)}")
        
        # Check for expected columns
        expected = ['thread_id', 'player1_id', 'player2_id', 'player1_board', 'player2_board', 'turn']
        found = [col for col in expected if col in columns]
        missing_cols = [col for col in expected if col not in columns]
        
        if missing_cols:
            print(f"   ⚠ Missing expected columns: {', '.join(missing_cols)}")
            print(f"   ⚠ Code expects these columns but database may have different schema")
        else:
            print(f"   ✓ All expected columns present")
    else:
        print("   ✓ Table exists (empty)")
except Exception as e:
    print(f"   ⚠ Could not check schema: {e}")

# 5. Test game logic functions
print("\n5. Testing game logic functions...")
try:
    board = create_new_board()
    if len(board) == 6 and len(board[0]) == 6:
        print("   ✓ create_new_board() works (returns 6x6 grid)")
    else:
        print(f"   ⚠ create_new_board() returned wrong size: {len(board)}x{len(board[0]) if board else 0}")
    
    # Test process_shot
    result, updated = process_shot('A1', board, [[0]*6 for _ in range(6)])
    print(f"   ✓ process_shot() works (result: {result})")
except Exception as e:
    print(f"   ❌ Game logic error: {e}")

print("\n" + "=" * 60)
print("Verification complete!")
print("=" * 60)


