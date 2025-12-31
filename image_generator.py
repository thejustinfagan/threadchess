"""
Battle Dinghy Twitter Bot - Game State Image Generator
Generates mobile-optimized PNG images for public Battleship games on Twitter
"""

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import math
import tempfile
import os


def generate_board_image(board, defender_name, theme_color='#2C2C2C', ships_status=None):
    """
    Generate a single-board game image for Twitter.

    Args:
        board: 6x6 grid with cell values (0=water, 2-4=ships, 9=miss, 1/12-14=hit)
        defender_name: Display name of whose FLEET this is (e.g., "@thejustinfagan")
        theme_color: Hex color for board theme
            - '#1A1A1A' (near-black) for Player 1's board
            - '#4A4A4A' (slate gray) for Player 2's board
        ships_status: Optional dict with ship status
            {'big': {'hits': 0-3, 'sunk': bool}, 'medium': {...}, 'small': {...}}

    Returns:
        str: Path to the generated PNG image file
    """
    # Constants
    WIDTH = 400
    HEIGHT = 520
    CELL_SIZE = 50
    GRID_SIZE = 6
    BOARD_WIDTH = CELL_SIZE * GRID_SIZE

    # Parse theme color to determine board style
    if theme_color.startswith('#'):
        theme_rgb = tuple(int(theme_color[i:i+2], 16) for i in (1, 3, 5))
    else:
        theme_rgb = (44, 44, 44)

    # Determine if this is Player 1 (dark/black) or Player 2 (gray) board
    is_dark_theme = sum(theme_rgb) < 150

    if is_dark_theme:
        # Player 1's board (BLACK theme)
        BG_COLOR = (12, 12, 18)
        WATER_COLOR1 = (20, 45, 90)
        WATER_COLOR2 = (30, 60, 110)
        GRID_LINE_COLOR = (60, 70, 90)
        ACCENT_COLOR = (70, 130, 200)  # Blue accent
    else:
        # Player 2's board (GRAY theme)
        BG_COLOR = (25, 28, 35)
        WATER_COLOR1 = (45, 75, 120)
        WATER_COLOR2 = (55, 90, 140)
        GRID_LINE_COLOR = (80, 90, 110)
        ACCENT_COLOR = (200, 160, 80)  # Gold accent

    # Common colors
    SHIP_COLOR = (100, 105, 115)
    SHIP_HIT_COLOR = (200, 80, 60)
    SHIP_SUNK_COLOR = (120, 40, 40)
    MISS_COLOR = (50, 180, 80)
    TEXT_COLOR = (255, 255, 255)
    LABEL_COLOR = (255, 255, 255)

    img = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Font setup
    try:
        font_title = ImageFont.truetype("arial.ttf", 18)
        font_label = ImageFont.truetype("arial.ttf", 20)  # Big axis labels
        font_ship = ImageFont.truetype("arial.ttf", 11)
        font_small = ImageFont.truetype("arial.ttf", 10)
    except:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_ship = ImageFont.load_default()
        font_small = ImageFont.load_default()

    def draw_gradient_square(x, y, size, color1, color2):
        for i in range(size):
            ratio = i / size
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            draw.line([(x, y + i), (x + size - 1, y + i)], fill=(r, g, b))

    def draw_explosion(x, y, size):
        center_x = x + size // 2
        center_y = y + size // 2
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x1 = center_x + int(math.cos(rad) * size * 0.4)
            y1 = center_y + int(math.sin(rad) * size * 0.4)
            draw.line([(center_x, center_y), (x1, y1)], fill=(255, 200, 0), width=2)
        draw.ellipse([x + size//4, y + size//4, x + 3*size//4, y + 3*size//4], fill=(255, 140, 0))
        draw.ellipse([x + size//3, y + size//3, x + 2*size//3, y + 2*size//3], fill=(255, 50, 30))

    def draw_ship_indicator(x, y, size, hits, is_sunk):
        """Draw a ship segment indicator showing damage status."""
        segment_width = 18
        segment_height = 14
        gap = 3

        for i in range(size):
            seg_x = x + i * (segment_width + gap)
            if is_sunk:
                color = SHIP_SUNK_COLOR
            elif i < hits:
                color = SHIP_HIT_COLOR
            else:
                color = SHIP_COLOR

            # Draw rounded segment
            draw.rounded_rectangle(
                [seg_x, y, seg_x + segment_width, y + segment_height],
                radius=3,
                fill=color,
                outline=(40, 45, 55) if not is_sunk else (80, 30, 30)
            )

            # Draw hit marker (X) on damaged segments
            if i < hits and not is_sunk:
                draw.line([(seg_x + 4, y + 3), (seg_x + segment_width - 4, y + segment_height - 3)],
                         fill=(255, 255, 255), width=2)
                draw.line([(seg_x + segment_width - 4, y + 3), (seg_x + 4, y + segment_height - 3)],
                         fill=(255, 255, 255), width=2)

    # Accent bar at top
    draw.rectangle([0, 0, WIDTH, 5], fill=ACCENT_COLOR)

    # Header: "{defender}'s Fleet"
    y_pos = 12
    header_text = f"{defender_name}'s Fleet"
    draw.text((15, y_pos), header_text, font=font_title, fill=TEXT_COLOR)

    y_pos += 28

    # Ship status display (if provided)
    if ships_status:
        # Draw ship indicators in a row
        ship_y = y_pos
        x_pos = 15

        # Big Dinghy (3 segments)
        draw.text((x_pos, ship_y), "Big:", font=font_ship, fill=(150, 150, 170))
        big_info = ships_status.get('big', {'hits': 0, 'sunk': False})
        draw_ship_indicator(x_pos + 30, ship_y, 3, big_info.get('hits', 0), big_info.get('sunk', False))

        # Dinghy (2 segments)
        x_pos = 145
        draw.text((x_pos, ship_y), "Med:", font=font_ship, fill=(150, 150, 170))
        med_info = ships_status.get('medium', {'hits': 0, 'sunk': False})
        draw_ship_indicator(x_pos + 32, ship_y, 2, med_info.get('hits', 0), med_info.get('sunk', False))

        # Small Dinghy (1 segment)
        x_pos = 255
        draw.text((x_pos, ship_y), "Sm:", font=font_ship, fill=(150, 150, 170))
        small_info = ships_status.get('small', {'hits': 0, 'sunk': False})
        draw_ship_indicator(x_pos + 25, ship_y, 1, small_info.get('hits', 0), small_info.get('sunk', False))

        y_pos += 25

    # Board position
    board_x = 55
    board_y = y_pos + 35

    # Column labels (1-6)
    for j in range(GRID_SIZE):
        label_x = board_x + j * CELL_SIZE + (CELL_SIZE // 2) - 5
        draw.text((label_x, board_y - 25), str(j + 1), font=font_label, fill=LABEL_COLOR)

    # Row labels (A-F)
    for i in range(GRID_SIZE):
        label = chr(65 + i)
        label_y = board_y + i * CELL_SIZE + (CELL_SIZE // 2) - 10
        draw.text((board_x - 30, label_y), label, font=font_label, fill=LABEL_COLOR)

    # Draw grid cells
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            x = board_x + j * CELL_SIZE
            y = board_y + i * CELL_SIZE
            cell = board[i][j]

            # Cell values: 0=water, 2-4=ships, 9=miss, 1=hit, 12-14=hit ships
            if cell == 0:
                draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4, WATER_COLOR1, WATER_COLOR2)
            elif cell == 9:
                draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4, WATER_COLOR1, WATER_COLOR2)
                draw.ellipse([x + 12, y + 12, x + CELL_SIZE - 12, y + CELL_SIZE - 12],
                           fill=MISS_COLOR, outline=(30, 140, 60), width=2)
            elif cell == 1 or cell >= 12:
                draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4, (70, 75, 85), (50, 55, 65))
                draw_explosion(x + 5, y + 5, CELL_SIZE - 10)
            elif cell in [2, 3, 4]:
                draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4, (70, 75, 85), (50, 55, 65))

            draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], outline=GRID_LINE_COLOR, width=1)

    # Bottom accent bar
    draw.rectangle([0, HEIGHT - 5, WIDTH, HEIGHT], fill=ACCENT_COLOR)

    # Watermark
    draw.text((WIDTH - 100, HEIGHT - 22), "@battle_dinghy", font=font_small, fill=(80, 90, 110))

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file.name, format='PNG', optimize=True)

    return temp_file.name

def generate_battle_dinghy_image(
    player1_board: list[list[str]],  # 6x6, values: 'water'|'miss'|'hit'|'ship'
    player2_board: list[list[str]],
    player1_name: str,  # "@Player1"
    player2_name: str,  # "@Player2" 
    player1_ships: dict,  # {"big": "alive"|"sunk", "medium": "alive"|"sunk", "small": "alive"|"sunk"}
    player2_ships: dict,
    current_turn: str,  # "@Player2"
    message: str = "",  # Optional game message
    show_player1_ships: bool = True,  # Whether to show player 1's ships
    show_player2_ships: bool = True  # Whether to show player 2's ships
) -> BytesIO:
    """Generate a battle state image for Twitter (400x850px)"""
    
    # Constants
    WIDTH = 400
    HEIGHT = 850
    CELL_SIZE = 50
    GRID_SIZE = 6
    BOARD_WIDTH = CELL_SIZE * GRID_SIZE
    
    # Colors
    BG_COLOR = (15, 20, 30)  # Dark navy background
    WATER_COLOR1 = (30, 60, 120)  # Gradient start
    WATER_COLOR2 = (40, 80, 140)  # Gradient end
    SHIP_COLOR1 = (80, 85, 90)  # Gray gradient start
    SHIP_COLOR2 = (60, 65, 70)  # Gray gradient end
    MISS_COLOR = (50, 180, 80)  # Green for misses
    HIT_COLOR = (255, 100, 50)  # Orange-red for hits
    TEXT_COLOR = (255, 255, 255)
    DIVIDER_COLOR = (60, 70, 80)

    # Create image
    img = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Font setup with fallback
    try:
        font_large = ImageFont.truetype("arial.ttf", 18)
        font_medium = ImageFont.truetype("arial.ttf", 14)  # Consistent header size
        font_small = ImageFont.truetype("arial.ttf", 11)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    def draw_rounded_rect(x, y, w, h, radius, fill):
        """Draw rounded rectangle"""
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
    
    def draw_gradient_square(x, y, size, color1, color2):
        """Draw a square with vertical gradient"""
        for i in range(size):
            ratio = i / size
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            draw.line([(x, y + i), (x + size - 1, y + i)], fill=(r, g, b))
    
    def draw_explosion(x, y, size):
        """Draw an explosion burst effect"""
        center_x = x + size // 2
        center_y = y + size // 2
        
        # Outer explosion rays (yellow)
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x1 = center_x + int(math.cos(rad) * size * 0.4)
            y1 = center_y + int(math.sin(rad) * size * 0.4)
            draw.line([(center_x, center_y), (x1, y1)], 
                     fill=(255, 200, 0), width=2)
        
        # Middle burst (orange)
        draw.ellipse([x + size//4, y + size//4, 
                     x + 3*size//4, y + 3*size//4], 
                    fill=(255, 140, 0))
        
        # Inner core (bright red)
        draw.ellipse([x + size//3, y + size//3,
                     x + 2*size//3, y + 2*size//3],
                    fill=(255, 50, 30))
    
    def draw_ship_status(x, y, ships_dict):
        """Draw ship status indicators with visual ship shapes"""
        ship_sizes = {"big": 3, "medium": 2, "small": 1}
        ship_width = 12  # Width of each ship segment
        spacing = 25  # Space between ships
        
        current_x = x
        for ship_type, size in ship_sizes.items():
            status = ships_dict.get(ship_type, "alive")
            color = (200, 60, 60) if status == "sunk" else (100, 110, 120)
            
            # Draw ship as connected rectangles
            ship_length = size * ship_width - 2
            draw_rounded_rect(current_x, y, ship_length, 8, 2, color)
            
            # Add small highlight if alive
            if status == "alive":
                draw.line([(current_x + 2, y + 2), 
                          (current_x + ship_length - 4, y + 2)], 
                         fill=(140, 150, 160), width=1)
            
            current_x += ship_length + spacing
        
        return current_x  # Return end position
    
    def draw_board(board_x, board_y, board_data, show_ships, 
                   opponent_name, fleet_name, ships_dict):
        """Draw a single game board"""
        # Board headers - CONSISTENT SIZING (14px for both lines)
        draw.text((board_x, board_y), f"{fleet_name}'s Fleet", 
                 font=font_medium, fill=TEXT_COLOR)
        
        # Ship status indicators next to fleet name
        fleet_text_width = draw.textlength(f"{fleet_name}'s Fleet", font=font_medium)
        draw_ship_status(board_x + fleet_text_width + 10, board_y + 3, ships_dict)
        
        draw.text((board_x, board_y + 20), f"{opponent_name}'s Shots",
                 font=font_medium, fill=(180, 180, 200))
        
        # Grid starts lower to accommodate headers
        grid_y = board_y + 45
        
        # Draw row labels (A-F)
        for i in range(GRID_SIZE):
            label = chr(65 + i)  # A, B, C, D, E, F
            draw.text((board_x - 20, grid_y + i * CELL_SIZE + 15),
                     label, font=font_small, fill=(120, 120, 140))
        
        # Draw column labels (1-6)
        for j in range(GRID_SIZE):
            draw.text((board_x + j * CELL_SIZE + 20, grid_y - 20),
                     str(j + 1), font=font_small, fill=(120, 120, 140))
        
        # Draw grid cells
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                x = board_x + j * CELL_SIZE
                y = grid_y + i * CELL_SIZE
                cell = board_data[i][j]
                
                # Draw base cell
                if cell == 'water':
                    draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4,
                                       WATER_COLOR1, WATER_COLOR2)
                elif cell == 'ship' and show_ships:
                    draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4,
                                       SHIP_COLOR1, SHIP_COLOR2)
                elif cell == 'miss':
                    # Water background first
                    draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4,
                                       WATER_COLOR1, WATER_COLOR2)
                    # Green circle for miss
                    draw.ellipse([x + 12, y + 12, x + CELL_SIZE - 12, y + CELL_SIZE - 12],
                                fill=MISS_COLOR, outline=(30, 140, 60), width=2)
                elif cell == 'hit':
                    # Ship background if showing ships
                    if show_ships:
                        draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4,
                                           SHIP_COLOR1, SHIP_COLOR2)
                    else:
                        draw_gradient_square(x + 2, y + 2, CELL_SIZE - 4,
                                           WATER_COLOR1, WATER_COLOR2)
                    # Explosion effect
                    draw_explosion(x + 5, y + 5, CELL_SIZE - 10)
                
                # Grid lines
                draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE],
                              outline=(40, 50, 60), width=1)
    
    # Current Y position tracker
    y_pos = 20
    
    # Turn banner
    turn_player = current_turn if current_turn else player2_name
    draw_rounded_rect(30, y_pos, WIDTH - 60, 35, 8, (40, 120, 200))
    turn_text = f"🎯 {turn_player}'s turn to fire!"
    text_bbox = draw.textbbox((0, 0), turn_text, font=font_large)
    text_width = text_bbox[2] - text_bbox[0]
    draw.text(((WIDTH - text_width) // 2, y_pos + 8), 
             turn_text, font=font_large, fill=TEXT_COLOR)
    
    y_pos += 55
    
    # Calculate board positions (centered)
    board_x = (WIDTH - BOARD_WIDTH) // 2
    
    # Player 1's board
    draw_board(board_x, y_pos, player1_board, show_player1_ships, 
              player2_name, player1_name, player1_ships)
    
    y_pos += 380  # Space for board + labels
    
    # Divider line
    draw.line([(40, y_pos), (WIDTH - 40, y_pos)], 
             fill=DIVIDER_COLOR, width=2)
    
    y_pos += 15
    
    # Player 2's board
    draw_board(board_x, y_pos, player2_board, show_player2_ships,
              player1_name, player2_name, player2_ships)
    
    # Message (if any)
    if message:
        y_pos = HEIGHT - 60
        draw_rounded_rect(30, y_pos, WIDTH - 60, 35, 8, (180, 60, 60))
        text_bbox = draw.textbbox((0, 0), message, font=font_medium)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(((WIDTH - text_width) // 2, y_pos + 10),
                 message, font=font_medium, fill=TEXT_COLOR)
    
    # Watermark
    watermark = "@battle_dinghy"
    draw.text((WIDTH - 100, HEIGHT - 20), watermark, 
             font=font_small, fill=(80, 90, 100))
    
    # Save to BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return buffer


# Test case - mid-game scenario
if __name__ == "__main__":
    # Create test boards
    test_board1 = [
        ['ship', 'ship', 'ship', 'water', 'miss', 'water'],
        ['water', 'water', 'water', 'water', 'water', 'water'],
        ['hit', 'hit', 'water', 'water', 'water', 'miss'],
        ['water', 'water', 'water', 'miss', 'water', 'water'],
        ['water', 'ship', 'water', 'water', 'water', 'water'],
        ['water', 'water', 'water', 'water', 'miss', 'water']
    ]
    
    test_board2 = [
        ['water', 'water', 'miss', 'water', 'water', 'water'],
        ['hit', 'hit', 'hit', 'water', 'water', 'water'],
        ['water', 'water', 'water', 'water', 'miss', 'water'],
        ['water', 'ship', 'ship', 'water', 'water', 'water'],
        ['miss', 'water', 'water', 'water', 'water', 'water'],
        ['water', 'water', 'water', 'ship', 'water', 'miss']
    ]
    
    # Ship status
    p1_ships = {"big": "alive", "medium": "sunk", "small": "alive"}
    p2_ships = {"big": "sunk", "medium": "alive", "small": "alive"}
    
    # Generate image
    image_buffer = generate_battle_dinghy_image(
        player1_board=test_board1,
        player2_board=test_board2,
        player1_name="@captain_ahab",
        player2_name="@naval_ninja",
        player1_ships=p1_ships,
        player2_ships=p2_ships,
        current_turn="@naval_ninja",
        message="@captain_ahab sunk @naval_ninja's Big Dinghy! 💥"
    )
    
    # Save test image
    with open("battle_dinghy_test.png", "wb") as f:
        f.write(image_buffer.getvalue())
    
    print("Test image generated: battle_dinghy_test.png")
    print(f"Image size: {image_buffer.getbuffer().nbytes / 1024:.1f} KB")

