"""
Script to clear all games from the database
"""

from db import delete_all_games

if __name__ == "__main__":
    print("Clearing all games from the database...")
    
    deleted_count = delete_all_games()
    
    print(f"✓ Deleted {deleted_count} game(s) from the database")






