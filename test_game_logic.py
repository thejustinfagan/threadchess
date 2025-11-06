"""
Unit tests for Battle Dinghy game logic.
"""
import unittest
import sys
import os

# Add the spec.md directory to the path to import game_logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))

from game_logic import (
    create_new_board,
    process_shot,
    copy_board,
    get_ships_remaining,
    count_hits_and_misses,
    FLEET_CONFIG
)


class TestBoardCreation(unittest.TestCase):
    """Test board creation functionality."""

    def test_create_new_board_dimensions(self):
        """Test that board has correct dimensions (6x6)."""
        board = create_new_board()
        self.assertEqual(len(board), 6, "Board should have 6 rows")
        for row in board:
            self.assertEqual(len(row), 6, "Each row should have 6 columns")

    def test_create_new_board_has_ships(self):
        """Test that board contains all ships."""
        board = create_new_board()

        # Count ship cells by ID
        ship_counts = {2: 0, 3: 0, 4: 0}
        for row in board:
            for cell in row:
                if cell in ship_counts:
                    ship_counts[cell] += 1

        # Verify ship sizes match FLEET_CONFIG
        self.assertEqual(ship_counts[2], 2, "Small Dinghy should have 2 cells")
        self.assertEqual(ship_counts[3], 3, "Dinghy should have 3 cells")
        self.assertEqual(ship_counts[4], 4, "Big Dinghy should have 4 cells")

    def test_create_new_board_no_overlaps(self):
        """Test that ships don't overlap."""
        board = create_new_board()

        # Each cell should be either water (0) or one ship ID (2, 3, 4)
        for row in board:
            for cell in row:
                self.assertIn(cell, [0, 2, 3, 4], "Cell should be water or a ship")


class TestShotProcessing(unittest.TestCase):
    """Test shot processing functionality."""

    def setUp(self):
        """Set up test boards."""
        # Create a simple board with known ship positions
        self.board = [[0 for _ in range(6)] for _ in range(6)]
        # Place Big Dinghy (4) horizontally at A1-A4
        for i in range(4):
            self.board[0][i] = 4

    def test_process_shot_miss(self):
        """Test processing a shot that misses."""
        result, updated_board = process_shot("F6", self.board, self.board)

        self.assertIn("Miss", result)
        self.assertEqual(updated_board[5][5], 9, "Cell should be marked as miss (9)")

    def test_process_shot_hit(self):
        """Test processing a shot that hits a ship."""
        result, updated_board = process_shot("A1", self.board, self.board)

        self.assertIn("Hit", result)
        self.assertEqual(updated_board[0][0], 14, "Cell should be marked as hit Big Dinghy (14 = 10+4)")

    def test_process_shot_already_fired(self):
        """Test firing at the same coordinate twice."""
        # First shot
        _, self.board = process_shot("A1", self.board, self.board)

        # Second shot at same location
        result, _ = process_shot("A1", self.board, self.board)

        self.assertIn("Already fired", result)

    def test_process_shot_invalid_coordinate(self):
        """Test invalid coordinate formats."""
        # Test out of range
        result, _ = process_shot("G1", self.board, self.board)
        self.assertIn("Row must be A-F", result)

        result, _ = process_shot("A7", self.board, self.board)
        self.assertIn("Column must be 1-6", result)

    def test_process_shot_sink_ship(self):
        """Test sinking a ship (all cells hit)."""
        # Place a Small Dinghy (2) at B1-B2
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[1][0] = 2
        board[1][1] = 2

        # Hit first cell - pass same board twice (new architecture)
        result1, board = process_shot("B1", board, board)
        self.assertIn("Hit", result1)
        self.assertNotIn("sunk", result1.lower())

        # Hit second cell - should sink
        result2, board = process_shot("B2", board, board)
        self.assertIn("sunk", result2.lower())


class TestBoardUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_copy_board(self):
        """Test that copy_board creates a deep copy."""
        original = [[1, 2], [3, 4]]
        copied = copy_board(original)

        # Modify copy
        copied[0][0] = 99

        # Original should be unchanged
        self.assertEqual(original[0][0], 1, "Original board should not be modified")

    def test_get_ships_remaining_all_alive(self):
        """Test ships remaining when all ships are intact."""
        board = create_new_board()
        ships = get_ships_remaining(board)

        self.assertEqual(ships['total'], 3, "All 3 ships should be alive")
        self.assertTrue(ships['Big Dinghy'])
        self.assertTrue(ships['Dinghy'])
        self.assertTrue(ships['Small Dinghy'])

    def test_get_ships_remaining_some_sunk(self):
        """Test ships remaining when some ships are sunk."""
        # Create board with Small Dinghy sunk
        board = [[0 for _ in range(6)] for _ in range(6)]
        # Big Dinghy still alive
        for i in range(4):
            board[0][i] = 4
        # Dinghy still alive
        for i in range(3):
            board[1][i] = 3
        # Small Dinghy fully hit (marked as 1)
        board[2][0] = 1
        board[2][1] = 1

        ships = get_ships_remaining(board)

        self.assertEqual(ships['total'], 2, "2 ships should remain")
        self.assertTrue(ships['Big Dinghy'])
        self.assertTrue(ships['Dinghy'])
        self.assertFalse(ships['Small Dinghy'])

    def test_count_hits_and_misses(self):
        """Test counting hits and misses on a board."""
        board = [[0 for _ in range(6)] for _ in range(6)]

        # Add 3 hits and 2 misses (hits are now 12-14, not 1)
        board[0][0] = 12  # Hit Small Dinghy
        board[0][1] = 13  # Hit Dinghy
        board[0][2] = 14  # Hit Big Dinghy
        board[1][0] = 9   # Miss
        board[1][1] = 9   # Miss

        hits, misses = count_hits_and_misses(board)

        self.assertEqual(hits, 3, "Should count 3 hits")
        self.assertEqual(misses, 2, "Should count 2 misses")


class TestCoordinateParsing(unittest.TestCase):
    """Test coordinate parsing and validation."""

    def test_uppercase_conversion(self):
        """Test that lowercase coordinates are converted to uppercase."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        hits = [[0 for _ in range(6)] for _ in range(6)]

        result, _ = process_shot("a1", board, hits)

        # Should not return format error
        self.assertNotIn("Invalid format", result)

    def test_coordinate_ranges(self):
        """Test valid coordinate ranges."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        hits = [[0 for _ in range(6)] for _ in range(6)]

        # Valid corner coordinates
        valid_coords = ["A1", "A6", "F1", "F6"]

        for coord in valid_coords:
            result, updated_hits = process_shot(coord, board, hits)
            # Should be either Hit or Miss, not an error
            self.assertTrue("Hit" in result or "Miss" in result,
                          f"Coordinate {coord} should be valid")
            hits = updated_hits


if __name__ == '__main__':
    unittest.main()
