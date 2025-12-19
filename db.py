import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_game(player1_id, player2_id, player1_board, player2_board, conversation_id):
    """
    Create a new game in the database.

    Args:
        player1_id: ID of player 1
        player2_id: ID of player 2
        player1_board: Player 1's secret ship board (6x6 grid)
        player2_board: Player 2's secret ship board (6x6 grid)
        conversation_id: Twitter conversation ID for the game thread

    Returns:
        str: The game_id of the newly created game
    """
    # Create blank 6x6 grids for tracking hits
    blank_hits_board = [[0 for _ in range(6)] for _ in range(6)]

    # Insert new game into database
    game_data = {
        'player1_id': player1_id,
        'player2_id': player2_id,
        'player1_board': player1_board,
        'player2_board': player2_board,
        'player1_hits': blank_hits_board,
        'player2_hits': blank_hits_board,
        'current_turn': player1_id,
        'conversation_id': conversation_id
    }

    response = supabase.table('games').insert(game_data).execute()

    # Return the game_id from the inserted row
    return response.data[0]['id']


def get_game_state(game_id):
    """
    Retrieve the current state of a game.

    Args:
        game_id: The ID of the game to retrieve

    Returns:
        dict: The complete game state row from the database
    """
    response = supabase.table('games').select('*').eq('id', game_id).execute()

    if response.data:
        return response.data[0]
    return None


def update_game_state(game_id, hits_board_to_update, new_hits_board, next_turn_id):
    """
    Update the game state after a shot has been taken.

    Args:
        game_id: The ID of the game to update
        hits_board_to_update: String indicating which board to update ("player1_hits" or "player2_hits")
        new_hits_board: The updated hits board (6x6 grid)
        next_turn_id: The ID of the player whose turn is next

    Returns:
        dict: The updated game state
    """
    # Build update data
    update_data = {
        'current_turn': next_turn_id,
        hits_board_to_update: new_hits_board
    }

    # Update the game in the database
    response = supabase.table('games').update(update_data).eq('id', game_id).execute()

    if response.data:
        return response.data[0]
    return None


def get_game_by_conversation_id(conversation_id):
    """
    Retrieve a game by its conversation ID.

    Args:
        conversation_id: The Twitter conversation ID to search for

    Returns:
        dict: The complete game state row from the database, or None if not found
    """
    response = supabase.table('games').select('*').eq('conversation_id', conversation_id).execute()

    if response.data:
        return response.data[0]
    return None
