"""Quick script to cancel all active games."""
from db import cancel_all_active_games

if __name__ == "__main__":
    count = cancel_all_active_games()
    print(f"Done. {count} game(s) cancelled.")
