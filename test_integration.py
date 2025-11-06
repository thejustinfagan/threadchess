"""
Integration tests for Battle Dinghy - tests complete game flows.
"""
import unittest
import sys
import os

# Add the spec.md directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))

from game_logic import create_new_board, process_shot, get_ships_remaining, count_hits_and_misses


class TestShipSinking(unittest.TestCase):
    """Test that ships can actually be sunk in gameplay."""

    def test_small_dinghy_sinks(self):
        """Test that Small Dinghy (2 cells) sinks after 2 hits."""
        # Create board with Small Dinghy at known position
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[0][0] = 2  # Small Dinghy
        board[0][1] = 2

        # Verify ship is present
        ships = get_ships_remaining(board)
        self.assertEqual(ships['Small Dinghy'], True, "Small Dinghy should be afloat")
        self.assertEqual(ships['total'], 1)

        # First hit
        result1, board = process_shot('A1', board, board)
        self.assertIn("Hit", result1)
        self.assertNotIn("sunk", result1.lower(), "Ship should not be sunk after 1 hit")

        ships = get_ships_remaining(board)
        self.assertEqual(ships['Small Dinghy'], True, "Ship still afloat after 1 hit")
        self.assertEqual(ships['total'], 1)

        # Second hit - should sink
        result2, board = process_shot('A2', board, board)
        self.assertIn("sunk", result2.lower(), "Ship should be sunk after all cells hit")

        ships = get_ships_remaining(board)
        self.assertEqual(ships['Small Dinghy'], False, "Ship should be sunk")
        self.assertEqual(ships['total'], 0, "No ships should remain")

    def test_dinghy_sinks(self):
        """Test that Dinghy (3 cells) sinks after 3 hits."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[1][0] = 3  # Dinghy
        board[1][1] = 3
        board[1][2] = 3

        # Hit 1
        result1, board = process_shot('B1', board, board)
        self.assertIn("Hit", result1)
        self.assertEqual(get_ships_remaining(board)['total'], 1)

        # Hit 2
        result2, board = process_shot('B2', board, board)
        self.assertIn("Hit", result2)
        self.assertNotIn("sunk", result2.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 1)

        # Hit 3 - should sink
        result3, board = process_shot('B3', board, board)
        self.assertIn("sunk", result3.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 0)

    def test_big_dinghy_sinks(self):
        """Test that Big Dinghy (4 cells) sinks after 4 hits."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[2][0] = 4  # Big Dinghy
        board[2][1] = 4
        board[2][2] = 4
        board[2][3] = 4

        # 3 hits - not sunk
        process_shot('C1', board, board)
        process_shot('C2', board, board)
        result3, board = process_shot('C3', board, board)
        self.assertNotIn("sunk", result3.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 1)

        # 4th hit - should sink
        result4, board = process_shot('C4', board, board)
        self.assertIn("sunk", result4.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 0)


class TestCompleteGame(unittest.TestCase):
    """Test a complete game from start to finish."""

    def test_full_game_to_victory(self):
        """Play a complete game hitting all ships."""
        # Create board with all ships in known positions
        board = [[0 for _ in range(6)] for _ in range(6)]
        # Small Dinghy horizontal at A1-A2
        board[0][0] = 2
        board[0][1] = 2
        # Dinghy horizontal at B1-B3
        board[1][0] = 3
        board[1][1] = 3
        board[1][2] = 3
        # Big Dinghy vertical at D1-D4
        board[3][0] = 4
        board[4][0] = 4
        board[5][0] = 4
        board[5][1] = 4  # Extra cell for Big Dinghy

        # Initial state: 3 ships afloat
        ships = get_ships_remaining(board)
        self.assertEqual(ships['total'], 3)

        # Sink Small Dinghy
        process_shot('A1', board, board)
        result, board = process_shot('A2', board, board)
        self.assertIn("sunk", result.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 2)

        # Sink Dinghy
        process_shot('B1', board, board)
        process_shot('B2', board, board)
        result, board = process_shot('B3', board, board)
        self.assertIn("sunk", result.lower())
        self.assertEqual(get_ships_remaining(board)['total'], 1)

        # Sink Big Dinghy
        process_shot('D1', board, board)
        process_shot('E1', board, board)
        process_shot('F1', board, board)
        result, board = process_shot('F2', board, board)
        self.assertIn("sunk", result.lower())

        # Game should be over - no ships remaining
        ships = get_ships_remaining(board)
        self.assertEqual(ships['total'], 0, "All ships should be sunk")
        self.assertEqual(ships['Small Dinghy'], False)
        self.assertEqual(ships['Dinghy'], False)
        self.assertEqual(ships['Big Dinghy'], False)

    def test_hit_miss_counting(self):
        """Test that hits and misses are counted correctly."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[0][0] = 2
        board[0][1] = 2

        # Fire 2 hits and 3 misses
        process_shot('A1', board, board)  # Hit
        process_shot('A2', board, board)  # Hit
        process_shot('A3', board, board)  # Miss
        process_shot('B1', board, board)  # Miss
        result, board = process_shot('C1', board, board)  # Miss

        hits, misses = count_hits_and_misses(board)
        self.assertEqual(hits, 2, "Should count 2 hits")
        self.assertEqual(misses, 3, "Should count 3 misses")

    def test_cannot_fire_twice_at_same_spot(self):
        """Test that firing at the same coordinate twice is rejected."""
        board = [[0 for _ in range(6)] for _ in range(6)]
        board[0][0] = 2

        # First shot
        result1, board = process_shot('A1', board, board)
        self.assertIn("Hit", result1)

        # Second shot at same spot
        result2, board = process_shot('A1', board, board)
        self.assertIn("Already fired", result2)


class TestRandomBoardGeneration(unittest.TestCase):
    """Test that randomly generated boards work correctly."""

    def test_random_board_has_all_ships(self):
        """Test that create_new_board() places all ships."""
        board = create_new_board()

        # Count ships by ID
        ship_counts = {2: 0, 3: 0, 4: 0}
        for row in board:
            for cell in row:
                if cell in ship_counts:
                    ship_counts[cell] += 1

        self.assertEqual(ship_counts[2], 2, "Small Dinghy should have 2 cells")
        self.assertEqual(ship_counts[3], 3, "Dinghy should have 3 cells")
        self.assertEqual(ship_counts[4], 4, "Big Dinghy should have 4 cells")

    def test_random_board_ships_can_be_sunk(self):
        """Test that ships on a randomly generated board can be sunk."""
        board = create_new_board()
        initial_ships = get_ships_remaining(board)
        self.assertEqual(initial_ships['total'], 3)

        # Fire at all cells to sink all ships
        hits = 0
        for row in range(6):
            for col in range(6):
                coord = f"{chr(65 + row)}{col + 1}"
                result, board = process_shot(coord, board, board)
                if "Hit" in result:
                    hits += 1

        # Should have hit exactly 9 cells (2+3+4)
        self.assertEqual(hits, 9, "Should have 9 total ship cells")

        # All ships should be sunk
        final_ships = get_ships_remaining(board)
        self.assertEqual(final_ships['total'], 0, "All ships should be sunk")


if __name__ == '__main__':
    unittest.main()
