import os
import random
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Get database URL from Railway (auto-injected) or local .env
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Add a PostgreSQL database in Railway.")
    print("Railway auto-injects DATABASE_URL when you add a Postgres database.")

def get_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Create the games and processed_tweets tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id SERIAL PRIMARY KEY,
            game_number INTEGER,
            player1_id TEXT,
            player2_id TEXT,
            player1_board JSONB,
            player2_board JSONB,
            turn TEXT,
            game_state TEXT DEFAULT 'active',
            thread_id TEXT UNIQUE,
            bot_post_count INTEGER DEFAULT 0,
            last_checked_tweet_id TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # Table to track processed tweets (survives restarts)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_tweets (
            tweet_id TEXT PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized successfully")

# Initialize database on import
if DATABASE_URL:
    try:
        init_db()
    except Exception as e:
        print(f"Error initializing database: {e}")


def get_next_game_number():
    """Get the next game number for a new game."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT game_number FROM games ORDER BY game_number DESC LIMIT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            return result['game_number'] + 1
        return 1
    except Exception as e:
        print(f"Error getting next game number: {e}")
        return 1


def create_game(player1_id, player2_id, player1_board, player2_board, thread_id):
    """
    Create a new game in the database.

    Args:
        player1_id: ID of player 1
        player2_id: ID of player 2
        player1_board: Player 1's secret ship board (6x6 grid)
        player2_board: Player 2's secret ship board (6x6 grid)
        thread_id: Twitter thread/conversation ID for the game

    Returns:
        str: The thread_id of the newly created game
    """
    game_number = get_next_game_number()
    first_turn = random.choice(['player1', 'player2'])

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO games (game_number, player1_id, player2_id, player1_board, player2_board, turn, game_state, thread_id, bot_post_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id) DO NOTHING
        """, (game_number, player1_id, player2_id, json.dumps(player1_board), json.dumps(player2_board), first_turn, 'active', thread_id, 0))
        conn.commit()
        print(f"Successfully created game with thread_id {thread_id}")
    except Exception as e:
        conn.rollback()
        print(f"Error creating game: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    return thread_id


def get_game_state(game_id):
    """
    Retrieve the current state of a game by ID.

    Args:
        game_id: The ID of the game to retrieve

    Returns:
        dict: The complete game state row from the database
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM games WHERE id = %s", (game_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return dict(result) if result else None


def get_game_by_thread_id(thread_id):
    """
    Retrieve a game by its Twitter thread ID.

    Args:
        thread_id: The Twitter thread/conversation ID to search for

    Returns:
        dict: The complete game state row from the database, or None if not found
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM games WHERE thread_id = %s", (thread_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return dict(result) if result else None


def update_game_after_shot(thread_id, board_field, updated_board, new_turn_or_state, expected_turn=None):
    """
    Update the game state after a shot has been taken.
    Includes turn validation to prevent race conditions.

    Args:
        thread_id: The thread ID of the game
        board_field: Which board to update ('player1_board' or 'player2_board')
        updated_board: The updated board state (6x6 grid)
        new_turn_or_state: Either 'player1', 'player2', or 'completed'
        expected_turn: Optional - the turn we expect (for race condition detection)

    Returns:
        dict: The updated game state, or None if update failed
    """
    try:
        # If expected_turn provided, verify it matches current state
        if expected_turn:
            current_game = get_game_by_thread_id(thread_id)
            if not current_game:
                return None
            if current_game.get('turn') != expected_turn:
                print(f"Race condition detected: expected {expected_turn}, got {current_game.get('turn')}")
                return None
            if current_game.get('game_state') != 'active':
                print(f"Game no longer active")
                return None

        conn = get_connection()
        cur = conn.cursor()

        if new_turn_or_state == 'completed':
            cur.execute(f"""
                UPDATE games SET {board_field} = %s, game_state = 'completed'
                WHERE thread_id = %s RETURNING *
            """, (json.dumps(updated_board), thread_id))
        else:
            cur.execute(f"""
                UPDATE games SET {board_field} = %s, turn = %s
                WHERE thread_id = %s RETURNING *
            """, (json.dumps(updated_board), new_turn_or_state, thread_id))

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        print(f"Error updating game after shot: {e}")
        return None


def increment_bot_post_count(thread_id):
    """
    Increment and return the bot post count for a game thread.

    Args:
        thread_id: The thread ID of the game

    Returns:
        int: The new post count (for use as post number)
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE games SET bot_post_count = bot_post_count + 1
            WHERE thread_id = %s RETURNING bot_post_count
        """, (thread_id,))
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result['bot_post_count'] if result else 1
    except Exception as e:
        print(f"Error incrementing bot post count: {e}")
        return 1


def get_active_games():
    """
    Get all active games for monitoring.

    Returns:
        list: List of active game records
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM games WHERE game_state = 'active'")
        results = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"Error getting active games: {e}")
        return []


def update_last_checked_tweet_id(thread_id, tweet_id):
    """
    Update the last checked tweet ID for a game thread.
    Used for monitoring game threads without requiring @mentions.

    Args:
        thread_id: The thread ID of the game
        tweet_id: The last processed tweet ID
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE games SET last_checked_tweet_id = %s WHERE thread_id = %s
        """, (tweet_id, thread_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error updating last_checked_tweet_id: {e}")


def delete_all_games():
    """
    Delete all games from the database.
    USE WITH CAUTION - for development/testing only.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM games")
        conn.commit()
        cur.close()
        conn.close()
        print("All games deleted")
    except Exception as e:
        print(f"Error deleting games: {e}")


def is_tweet_processed(tweet_id):
    """
    Check if a tweet has already been processed.

    Args:
        tweet_id: The tweet ID to check

    Returns:
        bool: True if already processed, False otherwise
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM processed_tweets WHERE tweet_id = %s", (str(tweet_id),))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Error checking processed tweet: {e}")
        return False


def mark_tweet_processed(tweet_id):
    """
    Mark a tweet as processed in the database.

    Args:
        tweet_id: The tweet ID to mark as processed
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO processed_tweets (tweet_id) VALUES (%s)
            ON CONFLICT (tweet_id) DO NOTHING
        """, (str(tweet_id),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error marking tweet as processed: {e}")


def cleanup_old_processed_tweets(hours=24):
    """
    Remove processed tweet records older than specified hours.
    Called periodically to prevent table growth.

    Args:
        hours: Number of hours after which to delete records (default 24)
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM processed_tweets
            WHERE processed_at < NOW() - INTERVAL '%s hours'
        """, (hours,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if deleted > 0:
            print(f"Cleaned up {deleted} old processed tweet records")
    except Exception as e:
        print(f"Error cleaning up processed tweets: {e}")


def cancel_all_active_games():
    """
    Cancel all active games by setting their state to 'cancelled'.
    Returns the number of games cancelled.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE games SET game_state = 'cancelled'
            WHERE game_state = 'active'
            RETURNING thread_id
        """)
        cancelled = cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        count = len(cancelled) if cancelled else 0
        print(f"Cancelled {count} active game(s)")
        return count
    except Exception as e:
        print(f"Error cancelling games: {e}")
        return 0
