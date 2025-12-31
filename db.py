import os
import random
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Debug: Print env var info (without revealing full values)
print(f"DEBUG: SUPABASE_URL is {'set' if SUPABASE_URL else 'NOT SET'}")
print(f"DEBUG: SUPABASE_URL length: {len(SUPABASE_URL) if SUPABASE_URL else 0}")
print(f"DEBUG: SUPABASE_URL first 10 chars: {SUPABASE_URL[:10] if SUPABASE_URL and len(SUPABASE_URL) > 10 else SUPABASE_URL}")
print(f"DEBUG: SUPABASE_KEY is {'set' if SUPABASE_KEY else 'NOT SET'}")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_next_game_number():
    """Get the next game number for a new game."""
    try:
        result = supabase.table('games').select('game_number').order('game_number', desc=True).limit(1).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]['game_number'] + 1
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

    # Randomly select who goes first for fairness
    first_turn = random.choice(['player1', 'player2'])

    game_data = {
        'game_number': game_number,
        'player1_id': player1_id,
        'player2_id': player2_id,
        'player1_board': player1_board,
        'player2_board': player2_board,
        'turn': first_turn,
        'game_state': 'active',
        'thread_id': thread_id,
        'bot_post_count': 0
    }

    response = supabase.table('games').insert(game_data).execute()

    # Return the thread_id for consistency with main_polling.py
    return thread_id


def get_game_state(game_id):
    """
    Retrieve the current state of a game by ID.

    Args:
        game_id: The ID of the game to retrieve

    Returns:
        dict: The complete game state row from the database
    """
    response = supabase.table('games').select('*').eq('id', game_id).execute()

    if response.data:
        return response.data[0]
    return None


def get_game_by_thread_id(thread_id):
    """
    Retrieve a game by its Twitter thread ID.

    Args:
        thread_id: The Twitter thread/conversation ID to search for

    Returns:
        dict: The complete game state row from the database, or None if not found
    """
    response = supabase.table('games').select('*').eq('thread_id', thread_id).execute()

    if response.data:
        return response.data[0]
    return None


def get_game_robust(tweet_id, conversation_id, author_id):
    """
    Robust game lookup with multiple fallback strategies.

    Tries to find a game by:
    1. Direct thread_id match with tweet_id
    2. Direct thread_id match with conversation_id
    3. Finding active game where author is a player

    Args:
        tweet_id: The tweet ID
        conversation_id: The conversation/thread ID
        author_id: The author's user ID

    Returns:
        dict: The game state, or None if not found
    """
    # Strategy 1: Try tweet_id as thread_id
    game = get_game_by_thread_id(tweet_id)
    if game and game.get('game_state') == 'active':
        return game

    # Strategy 2: Try conversation_id as thread_id
    if conversation_id:
        game = get_game_by_thread_id(conversation_id)
        if game and game.get('game_state') == 'active':
            return game

    # Strategy 3: Find active game where author is a player
    try:
        response = supabase.table('games').select('*').eq('game_state', 'active').or_(
            f'player1_id.eq.{author_id},player2_id.eq.{author_id}'
        ).execute()

        if response.data:
            # Return most recent active game for this player
            return response.data[0]
    except Exception as e:
        print(f"Error in robust game lookup: {e}")

    return None


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

        # Build update data
        update_data = {
            board_field: updated_board
        }

        if new_turn_or_state == 'completed':
            update_data['game_state'] = 'completed'
        else:
            update_data['turn'] = new_turn_or_state

        # Update the game
        response = supabase.table('games').update(update_data).eq('thread_id', thread_id).execute()

        if response.data:
            return response.data[0]
        return None
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
        # Get current count
        game = get_game_by_thread_id(thread_id)
        if not game:
            return 1

        current_count = game.get('bot_post_count', 0)
        new_count = current_count + 1

        # Update count
        supabase.table('games').update({'bot_post_count': new_count}).eq('thread_id', thread_id).execute()

        return new_count
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
        response = supabase.table('games').select('*').eq('game_state', 'active').execute()
        return response.data if response.data else []
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
        supabase.table('games').update({'last_checked_tweet_id': tweet_id}).eq('thread_id', thread_id).execute()
    except Exception as e:
        print(f"Error updating last_checked_tweet_id: {e}")


def delete_all_games():
    """
    Delete all games from the database.
    USE WITH CAUTION - for development/testing only.
    """
    try:
        # Delete all rows by selecting all and deleting
        supabase.table('games').delete().neq('id', 0).execute()
        print("All games deleted")
    except Exception as e:
        print(f"Error deleting games: {e}")
