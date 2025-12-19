import random
from typing import Dict, List, Tuple, Union


def place_dinghies() -> Dict[str, Union[List[List[int]], Dict[str, List[Tuple[int, int]]], Dict[str, str]]]:
    """
    Randomly place a fleet of ships (dinghies) on a 6x6 grid.
    Fleet: 1x Big Dinghy (3 squares), 2x Dinghy (2 squares each), 1x Small Dinghy (1 square)

    Returns:
        Dict containing:
        - 'grid': 6x6 list where 0=water, ship_id=ship number (1-4)
        - 'ships': Dict mapping ship_id to list of coordinates
        - 'ship_names': Dict mapping ship_id to ship name
    """
    grid = [[0 for _ in range(6)] for _ in range(6)]
    ships = {}
    ship_names = {}
    # Fleet: one Big Dinghy (3), two Dinghy (2), one Small Dinghy (1)
    fleet = [
        (3, "Big Dinghy"),
        (2, "Dinghy"),
        (2, "Dinghy"),
        (1, "Small Dinghy")
    ]
    
    for ship_id, (size, name) in enumerate(fleet, 1):
        placed = False
        attempts = 0
        max_attempts = 1000
        
        while not placed and attempts < max_attempts:
            # Random starting position and direction
            row = random.randint(0, 5)
            col = random.randint(0, 5)
            horizontal = random.choice([True, False])
            
            # Check if ship can be placed
            coordinates = []
            valid = True
            
            for i in range(size):
                if horizontal:
                    new_row, new_col = row, col + i
                else:
                    new_row, new_col = row + i, col
                
                # Check bounds
                if new_row >= 6 or new_col >= 6:
                    valid = False
                    break
                
                # Check for overlaps
                if grid[new_row][new_col] != 0:
                    valid = False
                    break
                
                coordinates.append((new_row, new_col))
            
            if valid:
                # Place the ship
                for r, c in coordinates:
                    grid[r][c] = ship_id
                ships[ship_id] = coordinates
                ship_names[ship_id] = name
                placed = True
            
            attempts += 1
        
        if not placed:
            raise Exception(f"Could not place {name} after {max_attempts} attempts")
    
    return {'grid': grid, 'ships': ships, 'ship_names': ship_names}


def process_shot(grid_data: Dict, coordinate: str) -> str:
    """
    Process a shot at the given coordinate.
    
    Args:
        grid_data: Dictionary containing grid and ships data from place_dinghies()
        coordinate: String like 'B5' (letter A-F, number 1-6)
    
    Returns:
        'hit', 'miss', or ship name if sunk (e.g., 'Big Dinghy', 'Dinghy', 'Small Dinghy')
    """
    # Parse coordinate
    if len(coordinate) < 2:
        return 'miss'
    
    letter = coordinate[0].upper()
    try:
        number = int(coordinate[1:])
    except ValueError:
        return 'miss'
    
    # Convert to grid coordinates (A-F, 1-6)
    if letter < 'A' or letter > 'F' or number < 1 or number > 6:
        return 'miss'
    
    row = ord(letter) - ord('A')
    col = number - 1
    
    grid = grid_data['grid']
    ships = grid_data['ships']
    ship_names = grid_data['ship_names']
    
    # Check if already hit/missed
    cell_value = grid[row][col]
    
    if cell_value == -1:  # Already missed
        return 'miss'
    elif cell_value == -2:  # Already hit
        return 'hit'
    elif cell_value == 0:  # Water
        grid[row][col] = -1  # Mark as miss
        return 'miss'
    else:  # Hit a ship
        ship_id = cell_value
        grid[row][col] = -2  # Mark as hit
        
        # Check if ship is sunk
        ship_coordinates = ships[ship_id]
        for ship_row, ship_col in ship_coordinates:
            if grid[ship_row][ship_col] != -2:  # Found unhit part
                return 'hit'
        
        # All parts hit - ship is sunk, return ship name
        return ship_names[ship_id]


# Minimal test
if __name__ == "__main__":
    game_data = place_dinghies()
    print(f"Placed {len(game_data['ships'])} ships on 6x6 grid")
    
    result = process_shot(game_data, "A1")
    print(f"Shot at A1: {result}")
