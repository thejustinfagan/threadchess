import random

FLEET_CONFIG = {
    'Big Dinghy': 4,
    'Dinghy': 3,
    'Small Dinghy': 2
}


def create_new_board():
    """
    Creates a 6x6 game board and randomly places all ships from FLEET_CONFIG.

    Returns:
        list: A 6x6 grid (list of lists) with ships placed on it.
              0 represents water, other numbers represent different ships.
    """
    # Create empty 6x6 grid filled with 0s (water)
    board = [[0 for _ in range(6)] for _ in range(6)]

    # Assign ship IDs based on their size
    ship_ids = {
        'Big Dinghy': 4,
        'Dinghy': 3,
        'Small Dinghy': 2
    }

    # Try to place each ship
    for ship_name, ship_size in FLEET_CONFIG.items():
        ship_id = ship_ids[ship_name]
        placed = False
        attempts = 0
        max_attempts = 100  # Prevent infinite loop

        while not placed and attempts < max_attempts:
            attempts += 1

            # Random orientation: 0 = horizontal, 1 = vertical
            orientation = random.choice(['horizontal', 'vertical'])

            if orientation == 'horizontal':
                # Random starting position for horizontal ship
                row = random.randint(0, 5)
                col = random.randint(0, 6 - ship_size)

                # Check if placement is valid (no overlaps)
                valid = True
                for c in range(col, col + ship_size):
                    if board[row][c] != 0:
                        valid = False
                        break

                # Place the ship if valid
                if valid:
                    for c in range(col, col + ship_size):
                        board[row][c] = ship_id
                    placed = True

            else:  # vertical
                # Random starting position for vertical ship
                row = random.randint(0, 6 - ship_size)
                col = random.randint(0, 5)

                # Check if placement is valid (no overlaps)
                valid = True
                for r in range(row, row + ship_size):
                    if board[r][col] != 0:
                        valid = False
                        break

                # Place the ship if valid
                if valid:
                    for r in range(row, row + ship_size):
                        board[r][col] = ship_id
                    placed = True

        if not placed:
            # If we couldn't place a ship after max attempts, start over
            return create_new_board()

    return board


def process_shot(coordinate, secret_board, hits_board):
    """
    Process a shot at the given coordinate.

    Args:
        coordinate: String coordinate like "A1", "C3", etc.
        secret_board: The opponent's secret ship board (6x6 grid)
        hits_board: The current player's hits tracking board (6x6 grid)

    Returns:
        tuple: (result_message, updated_hits_board)
               result_message is a string like "Miss! ⭕️" or "Hit! 💥"
               updated_hits_board is the modified hits board
    """
    # Input validation and sanitization
    if not isinstance(coordinate, str):
        return ("🎯 Invalid coordinate format! Use A1-F6.", hits_board)

    # Sanitize input - remove potentially dangerous characters
    coordinate = ''.join(c for c in coordinate if c.isalnum() or c.isspace())
    coordinate = coordinate.strip().upper()

    # Length check to prevent buffer overflow attempts
    if len(coordinate) > 10:
        return ("🎯 Coordinate too long! Use format A1-F6.", hits_board)

    if len(coordinate) < 2:
        return ("🎯 Oops! Need a coordinate like A1-F6. Try again!", hits_board)

    # Parse the coordinate (e.g., "A1" -> row=0, col=0)
    row_letter = coordinate[0]
    try:
        col_number = int(coordinate[1:])
    except ValueError:
        return ("🎯 Invalid format! Use A1-F6 (letter + number). Try again!", hits_board)

    # Validate row (A-F) and column (1-6)
    if row_letter < 'A' or row_letter > 'F':
        return ("🎯 Row must be A-F! Try a coordinate like A1 or D4.", hits_board)
    if col_number < 1 or col_number > 6:
        return ("🎯 Column must be 1-6! Try a coordinate like A1 or D4.", hits_board)

    # Convert to 0-indexed grid coordinates
    row = ord(row_letter) - ord('A')
    col = col_number - 1

    # Check if this coordinate was already fired upon
    if hits_board[row][col] != 0:
        return (f"🔄 Already fired at {coordinate.upper()}! Pick a new spot.", hits_board)

    # Check what's at this coordinate on the secret board
    cell_value = secret_board[row][col]

    if cell_value == 0:
        # Water - it's a miss
        hits_board[row][col] = 9  # Mark as miss
        return ("Miss! ⭕️", hits_board)
    else:
        # Hit a ship (cell_value is 2, 3, or 4)
        ship_id = cell_value
        hits_board[row][col] = 1  # Mark as hit

        # Determine which ship was hit
        ship_name = None
        for name, sid in [('Big Dinghy', 4), ('Dinghy', 3), ('Small Dinghy', 2)]:
            if sid == ship_id:
                ship_name = name
                break

        # Check if the ship is sunk by counting all positions of this ship
        ship_positions = []
        for r in range(6):
            for c in range(6):
                if secret_board[r][c] == ship_id:
                    ship_positions.append((r, c))

        # Check if all positions of this ship are hit
        all_hit = True
        for r, c in ship_positions:
            if hits_board[r][c] != 1:
                all_hit = False
                break

        if all_hit:
            # Ship is sunk
            return (f"Hit! You sunk their {ship_name}! 💥🚢", hits_board)
        else:
            # Ship hit but not sunk
            return (f"Hit {ship_name}! 💥", hits_board)


def copy_board(board):
    """
    Create a deep copy of a board.

    Args:
        board: 6x6 grid to copy

    Returns:
        list: A new 6x6 grid with the same values
    """
    return [row[:] for row in board]


def get_ships_remaining(board):
    """
    Count how many ships are still afloat (not fully sunk) on a board.

    Args:
        board: 6x6 grid with ship positions and hit/miss markers

    Returns:
        dict: {'Big Dinghy': bool, 'Dinghy': bool, 'Small Dinghy': bool, 'total': int}
              True means ship is still afloat, False means sunk
    """
    ships_status = {
        'Big Dinghy': False,
        'Dinghy': False,
        'Small Dinghy': False
    }

    # Check each ship type
    for ship_name, ship_id in [('Big Dinghy', 4), ('Dinghy', 3), ('Small Dinghy', 2)]:
        # Find all positions of this ship
        ship_positions = []
        for r in range(6):
            for c in range(6):
                if board[r][c] == ship_id:
                    ship_positions.append((r, c))

        # If ship exists on board, check if it's still afloat
        if ship_positions:
            # Check if any position is not hit (not marked as 1)
            afloat = any(board[r][c] != 1 for r, c in ship_positions)
            ships_status[ship_name] = afloat

    ships_status['total'] = sum(1 for status in [ships_status['Big Dinghy'], ships_status['Dinghy'], ships_status['Small Dinghy']] if status)
    return ships_status


def count_hits_and_misses(board):
    """
    Count the number of hits and misses on a board.

    Args:
        board: 6x6 grid with hit/miss markers

    Returns:
        tuple: (hits_count, misses_count)
    """
    hits = 0
    misses = 0

    for row in board:
        for cell in row:
            if cell == 1:  # Hit
                hits += 1
            elif cell == 9:  # Miss
                misses += 1

    return (hits, misses)
