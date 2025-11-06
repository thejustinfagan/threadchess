# text_board_generator.py

# A mapping from the internal game state to the visual emoji.
# This makes the code clean and easy to update.
STATE_TO_EMOJI = {
    "water": "🟦",
    "miss": "⭕️",
    "hit": "💥",
    "sunk": "💥",  # Sunk ships also use the 'hit' emoji per the spec
    "dinghy": "🚤",  # Dinghy emoji
}

# Column headers are pre-defined for consistency.
COLUMN_HEADERS = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟"
ROW_LABELS = "ABCDEFGHIJ"


def generate_text_board(board_state, title="Opponent Waters"):
    """
    Generates a text-based Battle Dinghys game board from a 2D list.

    Args:
        board_state (list[list[str]]): A 10x10 list of lists representing the
                                       grid, with states like "water", "hit", etc.
        title (str): The title to be displayed above the board.

    Returns:
        str: A fully formatted string representing the game board, ready to be posted.
    """
    
    # Start building the final output string as a list of lines.
    output_lines = []

    # 1. Add the code block start and title
    output_lines.append("```")
    output_lines.append(title)
    
    # 2. Add the column header line
    # Two leading spaces for alignment with row labels
    output_lines.append(f"  {COLUMN_HEADERS}")

    # 3. Build each grid row
    for i, row_data in enumerate(board_state):
        row_label = ROW_LABELS[i]
        
        # Convert the list of states (e.g., ["water", "miss"]) into a string of emojis ("🟦⭕️")
        emoji_row = "".join([STATE_TO_EMOJI.get(cell, "❓") for cell in row_data])
        
        # Combine the label, a space, and the emoji string
        output_lines.append(f"{row_label} {emoji_row}")

    # 4. Add the blank line and legend
    output_lines.append("") # Blank line
    output_lines.append("Legend: 🟦 = water   ⭕️ = miss   💥 = hit/sunk   🚤 = dinghy")
    
    # 5. Add the code block end
    output_lines.append("```")

    # Join all the lines together into a single string with newlines
    return "\n".join(output_lines)

# --- Example Usage ---
if __name__ == "__main__":
    # Create a sample 10x10 game state to test the generator.
    # In a real game, this data would come from your database.
    sample_game_state = [["water"] * 10 for _ in range(10)]

    # Add some sample hits and misses
    sample_game_state[0][1] = "miss"   # B1
    sample_game_state[2][4] = "hit"    # E3
    sample_game_state[2][5] = "hit"    # F3
    sample_game_state[2][6] = "sunk"   # G3 (renders as hit)
    sample_game_state[5][9] = "miss"   # J6
    sample_game_state[9][0] = "hit"    # A10

    # Generate the board string
    game_board_text = generate_text_board(sample_game_state)

    # Print the result. This is exactly what you would post.
    print(game_board_text)
