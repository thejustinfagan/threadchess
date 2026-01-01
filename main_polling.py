import tweepy
import os
import time
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('battle_dinghy.log'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

# Add the spec.md directory to the path to import game_logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))

# Import our game modules
from game_logic import create_new_board, process_shot, copy_board, get_ships_remaining, count_hits_and_misses, get_detailed_ship_status
from image_generator import generate_board_image
from db import (
    create_game, get_game_by_thread_id, update_game_after_shot,
    increment_bot_post_count, get_active_games, update_last_checked_tweet_id,
    is_tweet_processed, mark_tweet_processed, cleanup_old_processed_tweets
)

# Load environment variables
load_dotenv()

# Bot username
BOT_USERNAME = "battle_dinghy"

# Defer client initialization - will be created on first use
client = None
BOT_USER_ID = None

def get_twitter_client():
    """Get or create the Twitter get_twitter_client(). Deferred to allow env vars to load."""
    global client, BOT_USER_ID

    if client is not None:
        return client

    # Log which env vars are present (without revealing values)
    env_vars = {
        'BEARER_TOKEN': os.getenv("BEARER_TOKEN") is not None,
        'X_API_KEY': os.getenv("X_API_KEY") is not None,
        'X_API_SECRET': os.getenv("X_API_SECRET") is not None,
        'X_ACCESS_TOKEN': os.getenv("X_ACCESS_TOKEN") is not None,
        'X_ACCESS_TOKEN_SECRET': os.getenv("X_ACCESS_TOKEN_SECRET") is not None,
    }
    logger.info(f"Environment variables present: {env_vars}")

    # Check for missing credentials
    missing = [k for k, v in env_vars.items() if not v]
    if missing:
        logger.error(f"Missing Twitter credentials: {missing}")
        raise ValueError(f"Missing Twitter credentials: {missing}")

    client = tweepy.Client(
        bearer_token=os.getenv("BEARER_TOKEN"),
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True
    )

    # Get bot's numeric user ID
    try:
        bot_user = client.get_user(username=BOT_USERNAME)
        BOT_USER_ID = str(bot_user.data.id) if bot_user.data else None
        logger.info(f"Bot user ID: {BOT_USER_ID}")
    except Exception as e:
        logger.warning(f"Could not get bot user ID: {e}")
        BOT_USER_ID = None

    return client


def get_username_from_response(user_id, response):
    """
    Extract username from Twitter API response.includes data.
    This avoids making separate get_user() API calls.

    Args:
        user_id: Twitter user ID to lookup
        response: Twitter API response object with includes data

    Returns:
        str: Username if found, otherwise the user_id as fallback
    """
    if response.includes and 'users' in response.includes:
        for user in response.includes['users']:
            if str(user.id) == str(user_id):
                return user.username
    return str(user_id)  # Fallback to ID if not found


def get_username_by_id(user_id):
    """
    Get a username from a user ID by making an API call.
    Used when username isn't available in response.includes.

    Args:
        user_id: Twitter user ID to lookup

    Returns:
        str: Username if found, otherwise the user_id as fallback
    """
    try:
        user_response = get_twitter_client().get_user(id=user_id)
        if user_response.data:
            return user_response.data.username
    except Exception as e:
        logger.warning(f"Could not get username for ID {user_id}: {e}")
    return str(user_id)  # Fallback to ID


# Cache for processed tweet IDs to prevent double-processing
# Limited to MAX_CACHE_SIZE entries to prevent memory growth
# Also persisted to database to survive restarts
MAX_CACHE_SIZE = 500
processed_tweet_ids = set()


def add_processed_tweet(tweet_id):
    """
    Add a tweet ID to the processed cache AND database.
    Memory cache provides fast lookups, DB provides persistence across restarts.
    """
    global processed_tweet_ids
    tweet_id_str = str(tweet_id)

    # If cache is getting too large, clear it (DB is the source of truth)
    if len(processed_tweet_ids) >= MAX_CACHE_SIZE:
        logger.info(f"Processed tweet cache reached {len(processed_tweet_ids)} entries, clearing memory cache...")
        processed_tweet_ids.clear()
        logger.info("Memory cache cleared (DB still has records)")

    # Add to memory cache
    processed_tweet_ids.add(tweet_id_str)

    # Persist to database (survives restarts)
    mark_tweet_processed(tweet_id_str)


def is_already_processed(tweet_id):
    """
    Check if a tweet has already been processed.
    First checks memory cache (fast), then falls back to database (persistent).
    """
    tweet_id_str = str(tweet_id)

    # Fast path: check memory cache first
    if tweet_id_str in processed_tweet_ids:
        return True

    # Slow path: check database (handles restart case)
    if is_tweet_processed(tweet_id_str):
        # Add to memory cache for future fast lookups
        processed_tweet_ids.add(tweet_id_str)
        return True

    return False


def parse_coordinate_from_text(tweet_text):
    """
    Parse a coordinate (A1-E5) from tweet text.

    Args:
        tweet_text: The text of the tweet

    Returns:
        str: The coordinate if found, None otherwise
    """
    import re

    text_lower = tweet_text.lower()
    words = text_lower.split()

    coordinate = None

    # Look for coordinate after "fire", "at", "shoot", or just find any A-E + 1-5 pattern
    for i, word in enumerate(words):
        if word in ["fire", "shoot", "at"]:
            # Check next word
            if i + 1 < len(words):
                potential_coord = words[i + 1].strip(',:;!?.')
                # Validate it's a real coordinate (A-E, 1-5)
                pattern = r'^([a-e][1-5]|[1-5][a-e])$'
                if re.fullmatch(pattern, potential_coord):
                    coordinate = potential_coord
                    break

    # If no coordinate found after keywords, search for A-E + 1-5 pattern
    if not coordinate:
        # Match EXACT patterns: a1, A1, 1a, 1A (must be whole word)
        pattern = r'^([a-e][1-5]|[1-5][a-e])$'
        for word in words:
            clean_word = word.strip(',:;!?.').lower()
            match = re.fullmatch(pattern, clean_word)
            if match:
                coord_str = match.group()
                # Normalize to A1 format (letter first)
                if coord_str[0].isdigit():
                    coordinate = coord_str[1] + coord_str[0]  # Swap to letter-first
                else:
                    coordinate = coord_str
                break

    return coordinate


def process_fire_tweet(tweet, game_data, author_username, opponent_username):
    """
    Process a fire command from a tweet.

    Args:
        tweet: The tweet object containing the fire command
        game_data: The game data from the database
        author_username: The username of the tweet author (shooter)
        opponent_username: The username of the opponent (defender)

    Returns:
        bool: True if the fire was processed successfully, False otherwise
    """
    author_id = str(tweet.author_id)
    thread_id = game_data['thread_id']

    # Parse the coordinate from the tweet text
    coordinate = parse_coordinate_from_text(tweet.text)

    if not coordinate:
        reply_text = f"🎯 @{author_username}, please specify a coordinate! Example: 'fire A1' (A-E, 1-5)"
        get_twitter_client().create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        return False

    # Determine which player is shooting
    player1_id = game_data['player1_id']
    player2_id = game_data['player2_id']

    # Player theme colors - distinct visual themes for each player's board
    p1_theme = '#1A1A1A'  # Near-black for Player 1's board
    p2_theme = '#4A4A4A'  # Slate gray for Player 2's board

    if author_id == player1_id:
        # Player 1 is shooting at Player 2's board
        target_board = game_data['player2_board']
        board_to_update = "player2_board"
        next_turn = 'player2'
        shooter_board_theme = p2_theme
    else:
        # Player 2 is shooting at Player 1's board
        target_board = game_data['player1_board']
        board_to_update = "player1_board"
        next_turn = 'player1'
        shooter_board_theme = p1_theme

    # Make a copy of the target board to avoid mutations
    target_board_copy = copy_board(target_board)

    # Process the shot - returns (result_code, updated_board, ship_name)
    result_code, updated_board, ship_name = process_shot(
        coordinate,
        target_board_copy,
        target_board_copy
    )

    print(f"Shot result: {result_code}, ship: {ship_name}")
    logger.info(f"Shot processed in {thread_id}: {coordinate} -> {result_code}")

    # Handle invalid coordinate
    if result_code == "INVALID":
        reply_text = f"🎯 @{author_username}, invalid coordinate! Use A-E and 1-5. Example: A1, C3, E5"
        get_twitter_client().create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        return False

    # Handle already fired at this coordinate
    if result_code == "ALREADY_FIRED":
        reply_text = f"🔄 @{author_username} already fired at {coordinate.upper()}! Pick a different spot."
        get_twitter_client().create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        logger.info(f"Duplicate shot attempt at {coordinate} - no turn change")
        return False

    # Build the result message with @usernames (no pronouns)
    coord_upper = coordinate.upper()
    if result_code == "MISS":
        result_text = f"@{author_username} fired at {coord_upper}. Miss! ⭕"
    elif result_code == "HIT":
        result_text = f"@{author_username} hit @{opponent_username}'s {ship_name}! 💥"
    elif result_code == "SUNK":
        result_text = f"@{author_username} sunk @{opponent_username}'s {ship_name}! 💥🚢"

    # Check ships remaining and game end condition
    ships_remaining = get_ships_remaining(updated_board)
    game_over = ships_remaining['total'] == 0

    # Update the game state in database with turn validation
    current_turn = game_data['turn']
    if game_over:
        db_result = update_game_after_shot(
            thread_id,
            board_to_update,
            updated_board,
            'completed',
            current_turn
        )
    else:
        db_result = update_game_after_shot(
            thread_id,
            board_to_update,
            updated_board,
            next_turn,
            current_turn
        )

    # Check if database update failed (race condition detected)
    if not db_result:
        print(f"Database update failed - race condition detected or game no longer active")
        reply_text = f"⚠️ @{author_username}, something went wrong. The game state changed. Please try again!"
        get_twitter_client().create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        return False

    # Get scoreboard stats
    hits, misses = count_hits_and_misses(updated_board)

    # Get detailed ship status for visual display
    ship_status = get_detailed_ship_status(updated_board)

    # Generate the result image
    result_image = generate_board_image(
        updated_board,
        f"@{author_username}",
        f"@{opponent_username}",
        shooter_board_theme,
        ship_status
    )

    print(f"Generated result image: {result_image}")

    # Get post number for result tweet
    result_post_number = increment_bot_post_count(thread_id)
    game_number = game_data.get('game_number', 1)

    # Build result tweet with scoreboard (no pronouns)
    if game_over:
        result_tweet_text = (
            f"{result_post_number}/ {result_text}\n\n"
            f"🎉 GAME OVER! @{author_username} WINS! 🏆\n\n"
            f"📊 @{author_username}'s Final Stats:\n"
            f"• Shots: {hits + misses}\n"
            f"• Hits: {hits} 💥\n"
            f"• Misses: {misses} ⭕\n"
            f"• Accuracy: {round(hits/(hits+misses)*100) if hits+misses > 0 else 0}%\n\n"
            f"Game #{game_number}"
        )
    else:
        result_tweet_text = (
            f"{result_post_number}/ {result_text}\n\n"
            f"📊 @{author_username}'s Stats: {hits} hits, {misses} misses\n"
            f"🚢 @{opponent_username}'s ships left: {ships_remaining['total']}/3\n\n"
            f"Game #{game_number}"
        )

    # Upload image using v1.1 API
    auth = tweepy.OAuth1UserHandler(
        os.getenv("X_API_KEY"),
        os.getenv("X_API_SECRET"),
        os.getenv("X_ACCESS_TOKEN"),
        os.getenv("X_ACCESS_TOKEN_SECRET")
    )
    api = tweepy.API(auth)
    media = api.media_upload(result_image)

    # Post the result tweet - reply to the THREAD not the fire command
    result_tweet = get_twitter_client().create_tweet(
        text=result_tweet_text,
        in_reply_to_tweet_id=thread_id,
        media_ids=[media.media_id]
    )

    print(f"Posted result tweet {result_tweet.data['id']}")

    # If game is not over, prompt the opponent for their turn
    if not game_over:
        if author_id == player1_id:
            opponent_board = game_data['player1_board']
            opponent_board_theme = p1_theme
        else:
            opponent_board = game_data['player2_board']
            opponent_board_theme = p2_theme

        # Get detailed ship status for visual display
        next_turn_ship_status = get_detailed_ship_status(opponent_board)

        # Generate board image for the NEXT player's turn
        opponent_image = generate_board_image(
            opponent_board,
            f"@{opponent_username}",
            f"@{author_username}",
            opponent_board_theme,
            next_turn_ship_status
        )

        print(f"Generated opponent image: {opponent_image}")

        # Get post number for prompt tweet
        prompt_post_number = increment_bot_post_count(thread_id)

        # Upload opponent's board image
        media_opponent = api.media_upload(opponent_image)

        # Post the prompt tweet (no pronouns - use @username)
        prompt_text = f"{prompt_post_number}/ @{opponent_username}'s turn! Fire at @{author_username}'s fleet! 🎯"
        prompt_tweet = get_twitter_client().create_tweet(
            text=prompt_text,
            in_reply_to_tweet_id=thread_id,
            media_ids=[media_opponent.media_id]
        )

        print(f"Posted prompt tweet {prompt_tweet.data['id']}")
    else:
        print(f"Game over! @{author_username} wins!")

    print("Turn completed successfully!")
    return True


def monitor_active_games():
    """
    Monitor active game threads for fire commands WITHOUT requiring @mentions.

    This function:
    1. Gets all active games from the database
    2. For each game, searches the conversation for new replies
    3. Looks for fire patterns (fire A1, A1, etc.)
    4. Processes valid fire commands

    This allows players to just reply "fire A1" without mentioning @battle_dinghy.
    """
    print("\nMonitoring active game threads for fire commands...")

    # Get all active games
    active_games = get_active_games()

    if not active_games:
        print("No active games to monitor")
        return

    print(f"Monitoring {len(active_games)} active game(s)")

    for game in active_games:
        thread_id = game['thread_id']
        last_checked = game.get('last_checked_tweet_id')

        logger.info(f"Checking thread {thread_id} (last_checked: {last_checked})")

        try:
            # Search for tweets in this conversation
            # Note: Twitter API requires searching by conversation_id
            query = f"conversation_id:{thread_id}"

            search_params = {
                'query': query,
                'max_results': 20,  # Check more tweets per thread
                'tweet_fields': ['author_id', 'created_at', 'conversation_id'],
                'expansions': ['author_id'],
                'user_fields': ['username']
            }

            if last_checked:
                search_params['since_id'] = last_checked

            response = get_twitter_client().search_recent_tweets(**search_params)

            if not response.data:
                print(f"  No new tweets in thread {thread_id}")
                continue

            print(f"  Found {len(response.data)} new tweet(s) in thread {thread_id}")

            # Track the highest tweet ID we process
            newest_tweet_id = last_checked

            for tweet in response.data:
                tweet_id = str(tweet.id)

                # Update newest_tweet_id tracker
                if not newest_tweet_id or int(tweet_id) > int(newest_tweet_id):
                    newest_tweet_id = tweet_id

                # Skip bot's own tweets
                if BOT_USER_ID and str(tweet.author_id) == BOT_USER_ID:
                    continue

                author_id = str(tweet.author_id)

                # Check if this is from one of the players
                if author_id != game['player1_id'] and author_id != game['player2_id']:
                    # Not a player in this game - skip
                    continue

                # Check if tweet contains a fire pattern
                coordinate = parse_coordinate_from_text(tweet.text)
                if not coordinate:
                    # No coordinate found - not a fire command
                    continue

                print(f"  Found fire command in tweet {tweet_id}: {coordinate}")
                logger.info(f"Fire command detected in thread {thread_id}: {tweet.text}")

                # Refresh game data to ensure we have latest state
                game_data = get_game_by_thread_id(thread_id)
                if not game_data or game_data.get('game_state') != 'active':
                    print(f"  Game {thread_id} is no longer active")
                    break  # Stop processing this game

                # Check if this tweet was already processed (prevents double-processing)
                if is_already_processed(tweet_id):
                    print(f"  Tweet {tweet_id} already processed - skipping")
                    continue

                # TURN VALIDATION
                current_turn_player_id = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']

                if author_id != current_turn_player_id:
                    # Get the username of whose turn it actually is
                    whose_turn_username = get_username_from_response(current_turn_player_id, response)
                    # If we only got the ID back, make an API call to get the username
                    if whose_turn_username == current_turn_player_id:
                        whose_turn_username = get_username_by_id(current_turn_player_id)
                    reply_text = f"⏳ Hold up! It's @{whose_turn_username}'s turn. You'll go next!"
                    try:
                        get_twitter_client().create_tweet(
                            text=reply_text,
                            in_reply_to_tweet_id=tweet.id
                        )
                    except Exception as e:
                        logger.error(f"Failed to send turn rejection: {e}")
                    print(f"  Rejected - not {author_id}'s turn (it's {whose_turn_username}'s turn)")
                    # Mark as processed so we don't send duplicate rejection messages
                    add_processed_tweet(tweet_id)
                    continue

                # Get usernames from expansions
                author_username = get_username_from_response(tweet.author_id, response)
                # If we only got the ID back, make an API call to get the username
                if author_username == str(tweet.author_id):
                    author_username = get_username_by_id(tweet.author_id)
                opponent_id = game_data['player2_id'] if author_id == game_data['player1_id'] else game_data['player1_id']
                opponent_username = get_username_from_response(opponent_id, response)
                # If we only got the ID back, make an API call to get the username
                if opponent_username == opponent_id:
                    opponent_username = get_username_by_id(opponent_id)

                # Mark tweet as processed BEFORE processing to prevent race conditions
                add_processed_tweet(tweet_id)

                # Process the fire command
                try:
                    success = process_fire_tweet(tweet, game_data, author_username, opponent_username)
                    if success:
                        print(f"  Successfully processed fire command")
                except Exception as e:
                    print(f"  Error processing fire command: {e}")
                    logger.error(f"Error processing fire command in thread {thread_id}: {e}")

            # Update last_checked_tweet_id for this game
            if newest_tweet_id and newest_tweet_id != last_checked:
                update_last_checked_tweet_id(thread_id, newest_tweet_id)
                logger.info(f"Updated last_checked_tweet_id for {thread_id} to {newest_tweet_id}")

        except Exception as e:
            print(f"  Error monitoring thread {thread_id}: {e}")
            logger.error(f"Error monitoring thread {thread_id}: {e}")


def main_loop():
    """
    Main game loop that polls for both challenges and fire commands.
    """
    print(f"Starting Battle Dinghy bot polling for {BOT_USERNAME}...")
    logger.info(f"Battle Dinghy bot started, polling for {BOT_USERNAME}")

    # Track the last challenge tweet ID we've seen
    last_challenge_tweet_id = None

    # Counter for periodic cleanup (every ~60 polls = ~1 hour)
    poll_count = 0

    while True:
        poll_count += 1

        # Periodic cleanup of old processed tweets from database (every hour)
        if poll_count % 60 == 0:
            logger.info("Running periodic cleanup of old processed tweets...")
            cleanup_old_processed_tweets(hours=24)

        try:
            # Check for new challenges
            print("\nChecking for new challenges...")
            # Search for any mention of the bot (we'll filter by keywords in code)
            query = f"@{BOT_USERNAME}"
            
            # Debug: Show what we're searching for
            print(f"DEBUG: Searching for: '{query}'")
            logger.info(f"Searching Twitter for: '{query}'")

            search_params = {
                'query': query,
                'max_results': 10,
                'tweet_fields': ['author_id', 'created_at', 'conversation_id'],
                'expansions': ['author_id'],
                'user_fields': ['username']
            }

            if last_challenge_tweet_id:
                search_params['since_id'] = last_challenge_tweet_id

            response = get_twitter_client().search_recent_tweets(**search_params)
            
            # Debug: Show what Twitter returned
            if response.data:
                print(f"DEBUG: Found {len(response.data)} tweet(s)")
            else:
                print(f"DEBUG: No tweets found. Response: {response}")
                if response.errors:
                    print(f"DEBUG: Errors: {response.errors}")

            if response.data:
                print(f"Found {len(response.data)} new challenge(s)")

                for tweet in response.data:
                    last_challenge_tweet_id = tweet.id

                    # Skip if this is from the bot itself
                    if BOT_USER_ID and str(tweet.author_id) == BOT_USER_ID:
                        print(f"Skipping bot's own tweet {tweet.id}")
                        continue

                    # Natural language challenge detection with confidence scoring
                    tweet_text_lower = tweet.text.lower()
                    
                    # Remove bot username to avoid false positives from keywords in username
                    # e.g., @battle_dinghy contains "battle" but shouldn't count
                    text_without_bot = tweet_text_lower.replace(f'@{BOT_USERNAME.lower()}', '')
                    
                    confidence_score = 0
                    
                    # Strong challenge indicators (3 points each)
                    strong_keywords = ['play', 'playing', 'played', 'challenge', 'challenging', 'challenged', 
                                      'battle', 'battling', 'fight', 'fighting', 'game', 'gaming', 
                                      'match', 'versus', 'vs', 'against']
                    for keyword in strong_keywords:
                        if keyword in text_without_bot:  # Check text without bot username
                            confidence_score += 3
                            break  # Only count once per category
                    
                    # Invitation indicators (2 points each)
                    invitation_keywords = ['wanna', 'wana', 'want', 'wants', 'lets', "let's", 
                                          'ready', 'down', 'dare', 'bet', 'up for', 'fancy']
                    for keyword in invitation_keywords:
                        if keyword in text_without_bot:
                            confidence_score += 2
                            break
                    
                    # Challenge phrases (3 points)
                    challenge_phrases = ['start game', 'new game', 'begin match', '1v1', 'one on one',
                                        'you and me', 'with me', 'challenge you', 'i challenge',
                                        'game of', 'play a game', 'to a game', 'battleship', 'battle dinghy']
                    for phrase in challenge_phrases:
                        if phrase in text_without_bot:
                            confidence_score += 3
                            break
                    
                    # Structural indicators (1 point each)
                    mention_count = tweet_text_lower.count('@')
                    if mention_count >= 2:  # Has opponent mention
                        confidence_score += 1
                    if '?' in tweet_text_lower:  # Question format (invitation)
                        confidence_score += 1
                    
                    # Question starters (2 points)
                    question_starters = ['who', 'anyone', 'anybody']
                    first_word = tweet_text_lower.strip().split()[0] if tweet_text_lower.strip() else ''
                    if first_word in question_starters:
                        confidence_score += 2
                    
                    # Log confidence for debugging
                    logger.info(f"Tweet {tweet.id} challenge confidence: {confidence_score}")
                    
                    # Threshold: Need at least 3 points to be considered a challenge
                    if confidence_score < 3:
                        print(f"Tweet {tweet.id} mentions bot but doesn't look like a challenge (score: {confidence_score}) - skipping")
                        logger.info(f"Skipped tweet: '{tweet.text}' (confidence: {confidence_score})")
                        continue
                    
                    print(f"Challenge detected! (confidence: {confidence_score})")
                    
                    print(f"Processing challenge tweet {tweet.id}")

                    challenger_id = str(tweet.author_id)

                    # Get challenger's username from expansions (no extra API call needed)
                    challenger_username = get_username_from_response(tweet.author_id, response)

                    tweet_text = tweet.text
                    print(f"Challenge tweet text: {tweet_text}")

                    mentions = []
                    words = tweet_text.split()
                    for word in words:
                        if word.startswith('@'):
                            # Strip @ from start AND punctuation from end
                            clean_username = word.lstrip('@').rstrip(',:;!?.')
                            # Skip the bot's username (case-insensitive)
                            if clean_username and clean_username.lower() != BOT_USERNAME.lower():
                                mentions.append(clean_username)

                    if not mentions:
                        print(f"No opponent mentioned in tweet {tweet.id} - skipping")
                        # Reply to let user know they need to mention an opponent
                        try:
                            get_twitter_client().create_tweet(
                                text=f"⚠️ Please mention an opponent! Example: '@{BOT_USERNAME} play @opponent'",
                                in_reply_to_tweet_id=tweet.id
                            )
                        except:
                            pass  # Don't fail if reply doesn't work
                        continue

                    opponent_username = mentions[0]
                    print(f"Found opponent mention: @{opponent_username}")

                    # OPPONENT VALIDATION FIX: Verify opponent exists before creating game
                    # This prevents broken games with invalid opponent IDs
                    try:
                        opponent_user_response = get_twitter_client().get_user(username=opponent_username)
                        if not opponent_user_response.data:
                            print(f"Opponent @{opponent_username} not found")
                            # Reply with error - DON'T create game
                            try:
                                get_twitter_client().create_tweet(
                                    text=f"❌ User @{opponent_username} not found! Please mention a valid Twitter user.",
                                    in_reply_to_tweet_id=tweet.id
                                )
                            except:
                                pass
                            continue  # Skip game creation

                        opponent_id = str(opponent_user_response.data.id)
                    except Exception as e:
                        print(f"Error looking up opponent @{opponent_username}: {e}")
                        # Reply with error - DON'T create game
                        try:
                            get_twitter_client().create_tweet(
                                text=f"❌ Couldn't find user @{opponent_username}. Please check the username and try again!",
                                in_reply_to_tweet_id=tweet.id
                            )
                        except:
                            pass
                        continue  # Skip game creation

                    # SELF-CHALLENGE VALIDATION: Block users from challenging themselves
                    if opponent_id == challenger_id:
                        print(f"User {challenger_id} tried to challenge themselves")
                        try:
                            get_twitter_client().create_tweet(
                                text="❌ You can't challenge yourself! Pick a friend to play against.",
                                in_reply_to_tweet_id=tweet.id
                            )
                        except:
                            pass
                        continue  # Skip game creation

                    # BOT-CHALLENGE VALIDATION: Block users from challenging the bot
                    if BOT_USER_ID and opponent_id == BOT_USER_ID:
                        print(f"User {challenger_id} tried to challenge the bot")
                        try:
                            get_twitter_client().create_tweet(
                                text="❌ You can't challenge me! I'm the referee, not a player! 🤖",
                                in_reply_to_tweet_id=tweet.id
                            )
                        except:
                            pass
                        continue  # Skip game creation

                    print(f"Challenge: {challenger_username} vs {opponent_username}")

                    board1 = create_new_board()
                    board2 = create_new_board()

                    thread_id = str(tweet.conversation_id) if hasattr(tweet, 'conversation_id') else str(tweet.id)

                    # Create game with error handling
                    try:
                        game_id = create_game(challenger_id, opponent_id, board1, board2, thread_id)
                        print(f"Created game with thread_id {game_id}")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Failed to create game: {error_msg}")
                        logger.error(f"Failed to create game: {error_msg}")
                        
                        # Reply to user with helpful error message
                        if "Could not connect to database" in error_msg or "getaddrinfo" in error_msg:
                            reply_text = (
                                "❌ Database connection error. "
                                "The bot is having trouble connecting to the database. "
                                "Please try again in a moment!"
                            )
                        elif "Could not authenticate" in error_msg or "401" in error_msg:
                            reply_text = (
                                "❌ Database authentication error. "
                                "Please contact the bot administrator."
                            )
                        else:
                            reply_text = (
                                "❌ Error creating game. "
                                "Please try again in a moment!"
                            )
                        
                        try:
                            get_twitter_client().create_tweet(
                                text=reply_text,
                                in_reply_to_tweet_id=tweet.id
                            )
                        except:
                            pass  # Don't fail if reply doesn't work
                        continue  # Skip to next tweet

                    # Get the post number for this bot tweet
                    post_number = increment_bot_post_count(thread_id)

                    # Get the game data to determine who goes first (random selection)
                    game_data = get_game_by_thread_id(thread_id)
                    game_number = game_data.get('game_number', 1) if game_data else 1

                    # Determine who goes first based on random selection in database
                    first_turn = game_data.get('turn', 'player1') if game_data else 'player1'
                    if first_turn == 'player1':
                        first_player_username = challenger_username
                        # P1 fires first at P2's fleet (opponent's fleet)
                        defender_username = opponent_username
                        target_theme = '#4A4A4A'  # Gray theme for P2's board
                    else:
                        first_player_username = opponent_username
                        # P2 fires first at P1's fleet (challenger's fleet)
                        defender_username = challenger_username
                        target_theme = '#1A1A1A'  # Dark theme for P1's board

                    # Generate the starting board image
                    # Show the DEFENDER's fleet (whose ships are being targeted)
                    blank_board = [[0 for _ in range(6)] for _ in range(6)]
                    image_filename = generate_board_image(
                        blank_board,
                        f"@{first_player_username}",  # Who will be shooting (attacker)
                        f"@{defender_username}",      # Whose fleet this is (defender)
                        target_theme
                        # No ship_status for blank starting board
                    )

                    # Log game creation with first player info
                    logger.info(f"Game created: {thread_id}, {challenger_username} vs {opponent_username}, first player: {first_player_username}")

                    reply_text = (
                        f"{post_number}/ ⚔️ Game #{game_number} has begun! ⚔️\n\n"
                        f"@{challenger_username} vs. @{opponent_username}\n\n"
                        f"📍 How to play:\n"
                        f"• Reply with: fire [coordinate]\n"
                        f"• Example: fire A1\n"
                        f"• Grid: A-E (rows) × 1-5 (columns)\n\n"
                        f"@{first_player_username} fires first! 🎯"
                    )

                    # Upload image to Twitter using v1.1 API
                    import tweepy
                    auth = tweepy.OAuth1UserHandler(
                        os.getenv("X_API_KEY"),
                        os.getenv("X_API_SECRET"),
                        os.getenv("X_ACCESS_TOKEN"),
                        os.getenv("X_ACCESS_TOKEN_SECRET")
                    )
                    api = tweepy.API(auth)
                    media = api.media_upload(image_filename)

                    reply = get_twitter_client().create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id,
                        media_ids=[media.media_id]
                    )

                    print(f"Posted reply tweet {reply.data['id']}")
                    print("Game started successfully!")

            else:
                print("No new challenges found")

            # =================================================================
            # PART 2: Monitor active game threads for fire commands
            # =================================================================
            # This is the ONLY way to detect fire commands
            # Players reply "fire A1" (or just "A1") in the game thread
            # No @mention needed - we monitor all active game threads
            monitor_active_games()

        except Exception as e:
            print(f"Error in main loop: {e}")
            logger.error(f"Error in main loop: {e}")
            print("Continuing to next poll cycle...")

        # Wait 60 seconds before polling again
        print("\nWaiting 60 seconds before next poll...")
        time.sleep(60)


if __name__ == "__main__":
    main_loop()
