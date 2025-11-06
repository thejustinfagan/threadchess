import os
from supabase import create_client
from dotenv import load_dotenv
import httpx
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing Supabase credentials in .env file. "
        "Please set SUPABASE_URL and SUPABASE_KEY environment variables."
    )

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Successfully connected to Supabase")
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")
    raise


def create_game(player1_id, player2_id, player1_board, player2_board, thread_id):
    """
    Create a new game in the database.

    Args:
        player1_id: Twitter user ID of player 1
        player2_id: Twitter user ID of player 2
        player1_board: Player 1's secret ship board (6x6 grid)
        player2_board: Player 2's secret ship board (6x6 grid)
        thread_id: Twitter thread ID (conversation ID)

    Returns:
        str: The thread_id of the newly created game

    Raises:
        Exception: If database operation fails
    """
    try:
        # Get the next sequential game number by counting all existing games
        total_games = supabase.table('games').select('thread_id', count='exact').execute()
        game_number = (total_games.count if total_games.count else 0) + 1

        # Insert new game into database
        game_data = {
            'player1_id': player1_id,
            'player2_id': player2_id,
            'player1_board': player1_board,
            'player2_board': player2_board,
            'turn': 'player1',
            'thread_id': thread_id
        }

        # Try to add optional columns if they exist
        try:
            game_data['game_state'] = 'active'
            game_data['bot_post_count'] = 0
            game_data['game_number'] = game_number
            response = supabase.table('games').insert(game_data).execute()
        except Exception as e:
            error_str = str(e)
            # Remove columns that don't exist and retry
            if 'game_state' in error_str:
                del game_data['game_state']
            if 'bot_post_count' in error_str:
                del game_data['bot_post_count']
            if 'game_number' in error_str:
                del game_data['game_number']
            response = supabase.table('games').insert(game_data).execute()

        logger.info(f"Successfully created game with thread_id {thread_id}")
        return thread_id

    except httpx.ConnectError as e:
        logger.error(f"Connection error creating game: {e}")
        raise Exception("Could not connect to database")
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        raise


def get_game_by_thread_id(thread_id):
    """
    Retrieve a game by its thread ID.

    Args:
        thread_id: The Twitter thread ID to search for

    Returns:
        dict: The complete game state row from the database, or None if not found
    """
    try:
        response = supabase.table('games').select('*').eq('thread_id', thread_id).execute()

        if response.data:
            return response.data[0]
        return None
    except httpx.ConnectError as e:
        logger.error(f"Connection error getting game: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting game by thread_id {thread_id}: {e}")
        return None


def update_game_after_shot(thread_id, board_to_update, updated_board, next_turn):
    """
    Update the game state after a shot has been taken.

    Args:
        thread_id: The thread ID of the game to update
        board_to_update: String indicating which board to update ("player1_board" or "player2_board")
        updated_board: The updated board with the shot result (6x6 grid)
        next_turn: String indicating whose turn is next ("player1" or "player2")

    Returns:
        dict: The updated game state
    """
    # Build update data
    update_data = {
        'turn': next_turn,
        board_to_update: updated_board
    }

    # Update the game in the database
    response = supabase.table('games').update(update_data).eq('thread_id', thread_id).execute()

    if response.data:
        return response.data[0]
    return None


def increment_bot_post_count(thread_id):
    """
    Increment the bot post count for a game and return the new count.

    Args:
        thread_id: The thread ID of the game

    Returns:
        int: The new bot post count (to use as the post number)
    """
    # Get current game
    game = get_game_by_thread_id(thread_id)
    if not game:
        return 1

    # Check if bot_post_count column exists
    if 'bot_post_count' not in game:
        # Column doesn't exist yet, use a simple counter starting from 1
        # This is a temporary fallback
        return 1

    # Increment the count
    current_count = game.get('bot_post_count', 0)
    new_count = current_count + 1

    # Try to update in database
    try:
        supabase.table('games').update({'bot_post_count': new_count}).eq('thread_id', thread_id).execute()
    except Exception as e:
        # If column doesn't exist, just return the count without updating
        if 'bot_post_count' in str(e):
            pass
        else:
            raise

    return new_count


def delete_all_games():
    """
    Delete all games from the database.
    
    Returns:
        int: Number of games deleted
    """
    try:
        # Get all games to count them - try to detect the primary key
        all_games = supabase.table('games').select('*').execute()
        
        if not all_games.data:
            print("No games found to delete")
            return 0
        
        total_count = len(all_games.data)
        print(f"Found {total_count} game(s) to delete")
        
        # Detect primary key - try common names
        first_game = all_games.data[0]
        primary_key = None
        for key in ['id', 'game_id', 'thread_id']:
            if key in first_game:
                primary_key = key
                break
        
        if not primary_key:
            print("⚠ Could not determine primary key. Trying to delete all rows...")
            # Try deleting without a filter (if RLS allows)
            try:
                result = supabase.table('games').delete().neq('created_at', '1900-01-01').execute()
                deleted_count = len(result.data) if result.data else total_count
                print(f"✓ Deleted {deleted_count} game(s)")
                return deleted_count
            except Exception as e:
                print(f"❌ Error: {e}")
                print("Please delete games manually via Supabase Dashboard")
                return 0
        
        print(f"Using primary key: {primary_key}")
        deleted_count = 0
        
        # Delete each game by primary key
        for game in all_games.data:
            try:
                key_value = game[primary_key]
                
                # First, try to delete related records in ocean_grids if they exist
                try:
                    # Try to delete from ocean_grids first (if table exists)
                    ocean_grids_result = supabase.table('ocean_grids').delete().eq('thread_id', key_value).execute()
                    if ocean_grids_result.data:
                        print(f"  Deleted related ocean_grids for {key_value}")
                except Exception as ocean_error:
                    # If table doesn't exist or no related records, that's fine
                    pass
                
                # Now delete the game
                result = supabase.table('games').delete().eq(primary_key, key_value).execute()
                if result.data:
                    deleted_count += 1
                    print(f"Deleted game {key_value} ({deleted_count}/{total_count})")
                else:
                    deleted_count += 1  # Assume deleted if no error
                    print(f"Deleted game {key_value} ({deleted_count}/{total_count})")
            except Exception as e:
                error_msg = str(e)
                if 'foreign key constraint' in error_msg.lower():
                    print(f"⚠ Game {game.get(primary_key, 'unknown')} has related records that couldn't be deleted automatically")
                    print(f"  Error: {error_msg}")
                else:
                    print(f"Error deleting game {game.get(primary_key, 'unknown')}: {e}")
        
        return deleted_count
    except httpx.ConnectError as e:
        print(f"Connection error: Could not connect to Supabase.")
        print(f"Please check your SUPABASE_URL in the .env file.")
        print(f"Error details: {e}")
        return 0
    except Exception as e:
        print(f"Error in delete_all_games: {e}")
        import traceback
        traceback.print_exc()
        return 0
