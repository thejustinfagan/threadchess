from PIL import Image, ImageDraw, ImageFont


def generate_board_image(board_data, player_name, theme_color, ships_remaining=None):
    """
    Generate a Battle Dinghy board image.

    Args:
        board_data: 6x6 grid with values: 0 (water), 9 (miss), 1 (hit), or ship IDs
        player_name: string, e.g., "@Player1"
        theme_color: hex color code, e.g., '#1DA1F2'
        ships_remaining: dict with ship status (optional), e.g., {'total': 3, 'Big Dinghy': True, ...}

    Returns:
        str: filename of the saved image ("temp_board.png")
    """

    # Color dictionary
    colors = {
        'water': theme_color,
        'miss': '#FFFFFF',
        'hit': '#E0245E',
        'text': '#FFFFFF',
        'background': '#15202B'
    }

    # Convert hex colors to RGB tuples
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # Settings - Increased for better Twitter quality
    SQUARE_SIZE = 100  # Increased from 60 for better readability
    MARGIN = 80  # Increased from 50 for better spacing

    # Calculate image dimensions with extra space for legend and ship count
    title_space = 80  # Space for title and player name
    legend_space = 60  # Space for legend at bottom
    width = MARGIN * 2 + (6 * SQUARE_SIZE) + MARGIN  # Extra margin for right labels
    height = MARGIN + title_space + (6 * SQUARE_SIZE) + MARGIN + legend_space

    # Create image
    bg_color = hex_to_rgb(colors['background'])
    image = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    # Load font with platform-specific paths
    import platform
    system = platform.system()

    try:
        if system == "Windows":
            font_base = "C:/Windows/Fonts/arial.ttf"
        elif system == "Darwin":  # Mac
            font_base = "/System/Library/Fonts/Helvetica.ttc"
        else:  # Linux
            font_base = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        title_font = ImageFont.truetype(font_base, 28)  # Increased from 24
        player_font = ImageFont.truetype(font_base, 24)  # Increased from 20
        label_font = ImageFont.truetype(font_base, 18)  # Increased from 16
        print(f"✅ Loaded font from: {font_base}")
    except Exception as e:
        print(f"⚠️ Font loading failed: {e}, using default font")
        title_font = ImageFont.load_default()
        player_font = ImageFont.load_default()
        label_font = ImageFont.load_default()

    text_color = hex_to_rgb(colors['text'])

    # Draw title "Battle Dinghy's"
    title_text = "Battle Dinghy's"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, MARGIN), title_text, fill=text_color, font=title_font)

    # Draw player name
    player_bbox = draw.textbbox((0, 0), player_name, font=player_font)
    player_width = player_bbox[2] - player_bbox[0]
    player_x = (width - player_width) // 2
    draw.text((player_x, MARGIN + 35), player_name, fill=text_color, font=player_font)

    # Starting position for grid
    grid_start_x = MARGIN
    grid_start_y = MARGIN + title_space

    # Draw column headers (1-6)
    for col in range(6):
        header = str(col + 1)
        header_bbox = draw.textbbox((0, 0), header, font=label_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = grid_start_x + (col * SQUARE_SIZE) + (SQUARE_SIZE - header_width) // 2
        header_y = grid_start_y - 25
        draw.text((header_x, header_y), header, fill=text_color, font=label_font)

    # Draw row headers (A-F)
    for row in range(6):
        header = chr(65 + row)  # A, B, C, D, E, F
        header_bbox = draw.textbbox((0, 0), header, font=label_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_height = header_bbox[3] - header_bbox[1]
        header_x = grid_start_x - 25
        header_y = grid_start_y + (row * SQUARE_SIZE) + (SQUARE_SIZE - header_height) // 2
        draw.text((header_x, header_y), header, fill=text_color, font=label_font)

    # Draw column headers at bottom too for easier reference
    for col in range(6):
        header = str(col + 1)
        header_bbox = draw.textbbox((0, 0), header, font=label_font)
        header_width = header_bbox[2] - header_bbox[0]
        header_x = grid_start_x + (col * SQUARE_SIZE) + (SQUARE_SIZE - header_width) // 2
        header_y = grid_start_y + (6 * SQUARE_SIZE) + 10
        draw.text((header_x, header_y), header, fill=text_color, font=label_font)

    # Draw row headers on right side too for easier reference
    for row in range(6):
        header = chr(65 + row)  # A, B, C, D, E, F
        header_bbox = draw.textbbox((0, 0), header, font=label_font)
        header_height = header_bbox[3] - header_bbox[1]
        header_x = grid_start_x + (6 * SQUARE_SIZE) + 10
        header_y = grid_start_y + (row * SQUARE_SIZE) + (SQUARE_SIZE - header_height) // 2
        draw.text((header_x, header_y), header, fill=text_color, font=label_font)

    # Draw the grid
    water_color = hex_to_rgb(colors['water'])
    miss_color = hex_to_rgb(colors['miss'])
    hit_color = hex_to_rgb(colors['hit'])

    for row in range(6):
        for col in range(6):
            x0 = grid_start_x + (col * SQUARE_SIZE)
            y0 = grid_start_y + (row * SQUARE_SIZE)
            x1 = x0 + SQUARE_SIZE
            y1 = y0 + SQUARE_SIZE

            cell_value = board_data[row][col]

            if cell_value == 0:
                # Water - draw square with theme color
                draw.rectangle([x0, y0, x1, y1], fill=water_color, outline=text_color, width=2)
            elif cell_value == 9:
                # Miss - draw water square with larger white circle
                draw.rectangle([x0, y0, x1, y1], fill=water_color, outline=text_color, width=2)
                # Draw larger white circle in the middle
                circle_margin = 12  # Reduced from 15 to make circles bigger
                draw.ellipse([x0 + circle_margin, y0 + circle_margin,
                             x1 - circle_margin, y1 - circle_margin],
                            fill=miss_color, outline=text_color, width=2)
            elif cell_value >= 12:  # Hit ships (12, 13, 14)
                # Hit - draw water square with larger red circle
                draw.rectangle([x0, y0, x1, y1], fill=water_color, outline=text_color, width=2)
                # Draw larger red circle in the middle
                circle_margin = 12  # Reduced from 15 to make circles bigger
                draw.ellipse([x0 + circle_margin, y0 + circle_margin,
                             x1 - circle_margin, y1 - circle_margin],
                            fill=hit_color, outline=text_color, width=2)
            else:
                # Ship (2, 3, 4) or any other value - draw as water (ships are hidden from opponent)
                draw.rectangle([x0, y0, x1, y1], fill=water_color, outline=text_color, width=2)

    # Draw legend at bottom
    legend_y = grid_start_y + (6 * SQUARE_SIZE) + 40

    try:
        legend_font = ImageFont.truetype(font_base, 16)  # Increased from 14 to match larger image
    except:
        legend_font = ImageFont.load_default()

    legend_text = "○ = Miss  |  ● = Hit"  # Using Unicode circles instead of emojis for better compatibility
    legend_bbox = draw.textbbox((0, 0), legend_text, font=legend_font)
    legend_width = legend_bbox[2] - legend_bbox[0]
    legend_x = (width - legend_width) // 2
    draw.text((legend_x, legend_y), legend_text, fill=text_color, font=legend_font)

    # Draw ship count if provided
    if ships_remaining and 'total' in ships_remaining:
        ships_y = legend_y + 20
        ships_text = f"Ships Remaining: {ships_remaining['total']}/3"  # Text-based instead of emojis for better compatibility
        ships_bbox = draw.textbbox((0, 0), ships_text, font=legend_font)
        ships_width = ships_bbox[2] - ships_bbox[0]
        ships_x = (width - ships_width) // 2
        draw.text((ships_x, ships_y), ships_text, fill=text_color, font=legend_font)

    # Save the image
    filename = "temp_board.png"
    image.save(filename)

    return filename
