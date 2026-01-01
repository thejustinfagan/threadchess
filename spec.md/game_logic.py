import random

# Grid size constant
GRID_SIZE = 5

# Fleet configuration: ship_name -> size
# Ship IDs are based on size: Giant=3, Average=2, Tiny=1
FLEET_CONFIG = {
    'Giant Dinghy': 3,
    'Average Dinghy': 2,
    'Tiny Dinghy': 1
}


def create_new_board():
    """
    Creates a 5x5 game board and randomly places all ships from FLEET_CONFIG.

    Returns:
        list: A 5x5 grid (list of lists) with ships placed on it.
              0 represents water, other numbers represent different ships.
    """
    # Create empty 5x5 grid filled with 0s (water)
    board = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

    # Assign ship IDs based on their size (ID = size for simplicity)
    ship_ids = {
        'Giant Dinghy': 3,
        'Average Dinghy': 2,
        'Tiny Dinghy': 1
    }

    # Try to place each ship
    for ship_name, ship_size in FLEET_CONFIG.items():
        ship_id = ship_ids[ship_name]
        placed = False
        attempts = 0
        max_attempts = 100  # Prevent infinite loop

        while not placed and attempts < max_attempts:
            attempts += 1

            # Random orientation: horizontal or vertical
            orientation = random.choice(['horizontal', 'vertical'])

            if orientation == 'horizontal':
                # Random starting position for horizontal ship
                row = random.randint(0, GRID_SIZE - 1)
                col = random.randint(0, GRID_SIZE - ship_size)

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
                row = random.randint(0, GRID_SIZE - ship_size)
                col = random.randint(0, GRID_SIZE - 1)

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
        secret_board: The opponent's secret ship board (5x5 grid)
        hits_board: The current player's hits tracking board (5x5 grid)

    Returns:
        tuple: (result_message, updated_hits_board, ship_name_if_hit)
               result_message is a string like "MISS" or "HIT" or "SUNK"
               updated_hits_board is the modified hits board
               ship_name_if_hit is the ship name if hit, None otherwise
    """
    # Input validation and sanitization
    if not isinstance(coordinate, str):
        return ("INVALID", hits_board, None)

    # Sanitize input - remove potentially dangerous characters
    coordinate = ''.join(c for c in coordinate if c.isalnum() or c.isspace())
    coordinate = coordinate.strip().upper()

    # Length check to prevent buffer overflow attempts
    if len(coordinate) > 10:
        return ("INVALID", hits_board, None)

    if len(coordinate) < 2:
        return ("INVALID", hits_board, None)

    # Parse the coordinate (e.g., "A1" -> row=0, col=0)
    row_letter = coordinate[0]
    try:
        col_number = int(coordinate[1:])
    except ValueError:
        return ("INVALID", hits_board, None)

    # Validate row (A-E) and column (1-5)
    if row_letter < 'A' or row_letter > 'E':
        return ("INVALID", hits_board, None)
    if col_number < 1 or col_number > 5:
        return ("INVALID", hits_board, None)

    # Convert to 0-indexed grid coordinates
    row = ord(row_letter) - ord('A')
    col = col_number - 1

    # Check if this coordinate was already fired upon
    # Values: 0=water, 1-3=ships, 9=miss, 11-13=hit ships
    cell_value = hits_board[row][col]
    if cell_value == 9 or cell_value >= 11:  # Miss or hit
        return ("ALREADY_FIRED", hits_board, None)

    # Check what's at this coordinate (could be water=0, or ship=1/2/3)
    if cell_value == 0:
        # Water - it's a miss
        hits_board[row][col] = 9  # Mark as miss
        return ("MISS", hits_board, None)
    else:
        # Hit a ship (cell_value is 1, 2, or 3)
        ship_id = cell_value
        # Mark as hit by adding 10 to preserve ship identity
        # 1 becomes 11, 2 becomes 12, 3 becomes 13
        hits_board[row][col] = 10 + ship_id  # Mark as HIT ship (preserves which ship)

        # Determine which ship was hit
        ship_name = None
        for name, sid in [('Giant Dinghy', 3), ('Average Dinghy', 2), ('Tiny Dinghy', 1)]:
            if sid == ship_id:
                ship_name = name
                break

        # Check if the ship is sunk by counting all positions of this ship
        ship_positions = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                # Find ship by checking both unhit (1-3) and hit (11-13) positions
                board_val = hits_board[r][c]
                if board_val == ship_id or board_val == (10 + ship_id):
                    ship_positions.append((r, c))

        # Check if all positions of this ship are hit (value = 10 + ship_id)
        all_hit = True
        for r, c in ship_positions:
            if hits_board[r][c] != (10 + ship_id):  # Not marked as hit yet
                all_hit = False
                break

        if all_hit:
            # Ship is sunk
            return ("SUNK", hits_board, ship_name)
        else:
            # Ship hit but not sunk
            return ("HIT", hits_board, ship_name)


def copy_board(board):
    """
    Create a deep copy of a board.

    Args:
        board: 5x5 grid to copy

    Returns:
        list: A new 5x5 grid with the same values
    """
    return [row[:] for row in board]


def get_ships_remaining(board):
    """
    Count how many ships are still afloat (not fully sunk) on a board.

    Board values: 0=water, 1-3=unhit ships, 9=miss, 11-13=hit ships

    Args:
        board: 5x5 grid with ship positions and hit/miss markers

    Returns:
        dict: {'Giant Dinghy': bool, 'Average Dinghy': bool, 'Tiny Dinghy': bool, 'total': int}
              True means ship is still afloat, False means sunk
    """
    ships_status = {
        'Giant Dinghy': False,
        'Average Dinghy': False,
        'Tiny Dinghy': False
    }

    # Check each ship type
    for ship_name, ship_id in [('Giant Dinghy', 3), ('Average Dinghy', 2), ('Tiny Dinghy', 1)]:
        # Find all positions of this ship (both unhit and hit)
        ship_positions = []
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                cell_val = board[r][c]
                # Ship exists if cell is ship_id (unhit) or 10+ship_id (hit)
                if cell_val == ship_id or cell_val == (10 + ship_id):
                    ship_positions.append((r, c))

        # If ship exists on board, check if it's still afloat
        if ship_positions:
            # Afloat if ANY position is NOT hit (still has value ship_id, not 10+ship_id)
            afloat = any(board[r][c] == ship_id for r, c in ship_positions)
            ships_status[ship_name] = afloat

    ships_status['total'] = sum(1 for status in [ships_status['Giant Dinghy'], ships_status['Average Dinghy'], ships_status['Tiny Dinghy']] if status)
    return ships_status


def get_detailed_ship_status(board):
    """
    Get detailed hit/sunk status for each ship type on a board.

    Board values: 0=water, 1=Tiny Dinghy, 2=Average Dinghy, 3=Giant Dinghy, 9=miss
                  11=hit Tiny, 12=hit Average, 13=hit Giant

    Args:
        board: 5x5 grid with ship positions and hit/miss markers

    Returns:
        dict: {
            'giant': {'hits': 0-3, 'sunk': bool, 'size': 3},
            'average': {'hits': 0-2, 'sunk': bool, 'size': 2},
            'tiny': {'hits': 0-1, 'sunk': bool, 'size': 1}
        }
    """
    # Ship definitions: (display_key, ship_id, size)
    ships = [
        ('giant', 3, 3),    # Giant Dinghy: id=3, size=3
        ('average', 2, 2),  # Average Dinghy: id=2, size=2
        ('tiny', 1, 1),     # Tiny Dinghy: id=1, size=1
    ]

    result = {}

    for key, ship_id, size in ships:
        unhit_count = 0
        hit_count = 0

        for row in board:
            for cell in row:
                if cell == ship_id:  # Unhit ship segment
                    unhit_count += 1
                elif cell == (10 + ship_id):  # Hit ship segment
                    hit_count += 1

        # Ship is sunk if all segments are hit (no unhit segments remain)
        is_sunk = (unhit_count == 0 and hit_count > 0)

        result[key] = {
            'hits': hit_count,
            'sunk': is_sunk,
            'size': size
        }

    return result


def count_hits_and_misses(board):
    """
    Count the number of hits and misses on a board.

    Board values: 0=water, 1-3=unhit ships, 9=miss, 11-13=hit ships

    Args:
        board: 5x5 grid with hit/miss markers

    Returns:
        tuple: (hits_count, misses_count)
    """
    hits = 0
    misses = 0

    for row in board:
        for cell in row:
            if cell >= 11:  # Hit ships (11, 12, 13)
                hits += 1
            elif cell == 9:  # Miss
                misses += 1

    return (hits, misses)
