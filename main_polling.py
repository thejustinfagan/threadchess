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
from game_logic import create_new_board, process_shot, copy_board, get_ships_remaining, count_hits_and_misses
from image_generator import generate_board_image
from db import (
    create_game, get_game_by_thread_id, get_game_robust, update_game_after_shot,
    increment_bot_post_count, get_active_games, update_last_checked_tweet_id
)

# Load environment variables
load_dotenv()

# Set up Tweepy Client (using same env vars as bot.py)
client = tweepy.Client(
    bearer_token=os.getenv("BEARER_TOKEN"),
    consumer_key=os.getenv("X_API_KEY"),
    consumer_secret=os.getenv("X_API_SECRET"),
    access_token=os.getenv("X_ACCESS_TOKEN"),
    access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
    wait_on_rate_limit=True
)

# Bot username
BOT_USERNAME = "battle_dinghy"

# Get bot's numeric user ID (needed to filter out bot's own tweets)
try:
    bot_user = client.get_user(username=BOT_USERNAME)
    BOT_USER_ID = str(bot_user.data.id) if bot_user.data else None
    print(f"Bot user ID: {BOT_USER_ID}")
except Exception as e:
    print(f"Warning: Could not get bot user ID: {e}")
    BOT_USER_ID = None


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


def parse_coordinate_from_text(tweet_text):
    """
    Parse a coordinate (A1-F6) from tweet text.

    Args:
        tweet_text: The text of the tweet

    Returns:
        str: The coordinate if found, None otherwise
    """
    import re

    text_lower = tweet_text.lower()
    words = text_lower.split()

    coordinate = None

    # Look for coordinate after "fire", "at", "shoot", or just find any A-F + 1-6 pattern
    for i, word in enumerate(words):
        if word in ["fire", "shoot", "at"]:
            # Check next word
            if i + 1 < len(words):
                potential_coord = words[i + 1].strip(',:;!?.')
                # Validate it's a real coordinate
                pattern = r'^([a-f][1-6]|[1-6][a-f])$'
                if re.fullmatch(pattern, potential_coord):
                    coordinate = potential_coord
                    break

    # If no coordinate found after keywords, search for A-F + 1-6 pattern
    if not coordinate:
        # Match EXACT patterns: a1, A1, 1a, 1A (must be whole word)
        pattern = r'^([a-f][1-6]|[1-6][a-f])$'
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

    This is the core fire processing logic, extracted so it can be used by both
    the @mention handler and the thread monitor.

    Args:
        tweet: The tweet object containing the fire command
        game_data: The game data from the database
        author_username: The username of the tweet author
        opponent_username: The username of the opponent

    Returns:
        bool: True if the fire was processed successfully, False otherwise
    """
    author_id = str(tweet.author_id)
    thread_id = game_data['thread_id']

    # Parse the coordinate from the tweet text
    coordinate = parse_coordinate_from_text(tweet.text)

    if not coordinate:
        reply_text = "🎯 Please specify a coordinate! Example: 'fire A1' (A-F, 1-6)"
        client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        return False

    # Determine which player is shooting
    player1_id = game_data['player1_id']
    player2_id = game_data['player2_id']

    # Player theme colors - Player 1 gets black, Player 2 gets gray
    p1_theme = '#2C2C2C'  # Black for Player 1
    p2_theme = '#808080'  # Gray for Player 2

    if author_id == player1_id:
        # Player 1 is shooting at Player 2's board
        target_board = game_data['player2_board']
        board_to_update = "player2_board"
        opponent_id = player2_id
        next_turn = 'player2'
        shooter_board_theme = p2_theme  # Show P2's board (gray) with P1's shots
    else:
        # Player 2 is shooting at Player 1's board
        target_board = game_data['player1_board']
        board_to_update = "player1_board"
        opponent_id = player1_id
        next_turn = 'player1'
        shooter_board_theme = p1_theme  # Show P1's board (black) with P2's shots

    # Make a copy of the target board to avoid mutations
    target_board_copy = copy_board(target_board)

    # Process the shot - this updates the target board to mark hit/miss
    result_text, updated_board = process_shot(
        coordinate,
        target_board_copy,
        target_board_copy  # We're marking hits/misses on the target board itself
    )

    print(f"Shot result: {result_text}")
    logger.info(f"Shot processed in {thread_id}: {coordinate} -> {result_text}")

    # Check ships remaining and game end condition
    ships_remaining = get_ships_remaining(updated_board)
    game_over = ships_remaining['total'] == 0

    # Update the game state in database with turn validation
    # Pass current_turn to prevent race conditions
    current_turn = game_data['turn']  # The turn it should be NOW
    if game_over:
        db_result = update_game_after_shot(
            thread_id,
            board_to_update,
            updated_board,
            'completed',  # Mark game as completed
            current_turn  # Validate it's still this player's turn
        )
    else:
        db_result = update_game_after_shot(
            thread_id,
            board_to_update,
            updated_board,
            next_turn,
            current_turn  # Validate it's still this player's turn
        )

    # Check if database update failed (race condition detected)
    if not db_result:
        print(f"Database update failed - race condition detected or game no longer active")
        reply_text = "⚠️ Oops! Something went wrong. The game state changed. Please try again!"
        client.create_tweet(
            text=reply_text,
            in_reply_to_tweet_id=tweet.id
        )
        return False

    # Get scoreboard stats
    hits, misses = count_hits_and_misses(updated_board)

    # Generate the result image showing the updated board with ship count
    result_image = generate_board_image(
        updated_board,
        f"@{author_username}",
        shooter_board_theme,
        ships_remaining
    )

    print(f"Generated result image: {result_image}")

    # Get post number for result tweet
    result_post_number = increment_bot_post_count(thread_id)

    # Get game number from the database
    game_number = game_data.get('game_number', 1)

    # Build result tweet with scoreboard
    if game_over:
        result_tweet_text = (
            f"{result_post_number}/ {result_text}\n\n"
            f"🎉 GAME OVER! @{author_username} WINS! 🏆\n\n"
            f"📊 Final Stats:\n"
            f"• Shots: {hits + misses}\n"
            f"• Hits: {hits} 💥\n"
            f"• Misses: {misses} ⭕\n"
            f"• Accuracy: {round(hits/(hits+misses)*100) if hits+misses > 0 else 0}%\n\n"
            f"Game #{game_number}"
        )
    else:
        result_tweet_text = (
            f"{result_post_number}/ {result_text}\n\n"
            f"📊 Stats: {hits} hits, {misses} misses\n"
            f"🚢 Ships left: {ships_remaining['total']}/3\n\n"
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
    result_tweet = client.create_tweet(
        text=result_tweet_text,
        in_reply_to_tweet_id=thread_id,
        media_ids=[media.media_id]
    )

    print(f"Posted result tweet {result_tweet.data['id']}")

    # If game is not over, prompt the opponent for their turn
    if not game_over:
        # Show the opponent the board they'll be SHOOTING AT (not their defense board)
        # This is the shooting board - shows where they can fire next
        if author_id == player1_id:
            # Player 1 just shot at Player 2's board
            # Now show Player 2 where THEY will shoot (Player 1's position board)
            opponent_board = game_data['player1_board']
            opponent_board_theme = p1_theme  # Black
        else:
            # Player 2 just shot at Player 1's board
            # Now show Player 1 where THEY will shoot (Player 2's position board)
            opponent_board = game_data['player2_board']
            opponent_board_theme = p2_theme  # Gray

        # Get opponent's ship status
        opponent_ships = get_ships_remaining(opponent_board)

        # Generate opponent's board image with ship count
        opponent_image = generate_board_image(
            opponent_board,
            f"@{opponent_username}",
            opponent_board_theme,
            opponent_ships
        )

        print(f"Generated opponent image: {opponent_image}")

        # Get post number for prompt tweet
        prompt_post_number = increment_bot_post_count(thread_id)

        # Upload opponent's board image
        media_opponent = api.media_upload(opponent_image)

        # Post the prompt tweet for the opponent - reply to THREAD not previous tweet
        prompt_text = f"{prompt_post_number}/ Your turn, @{opponent_username}! Fire away! 🎯"
        prompt_tweet = client.create_tweet(
            text=prompt_text,
            in_reply_to_tweet_id=thread_id,
            media_ids=[media_opponent.media_id]
        )

        print(f"Posted prompt tweet {prompt_tweet.data['id']}")
    else:
        print(f"Game over! {author_id} wins!")

    print("Turn completed successfully!")
    return True


def handle_fire_command(last_fire_tweet_id=None):
    """
    Handle fire commands from players via @mentions.

    This function searches for tweets mentioning @battle_dinghy with "fire" commands.
    NOTE: This is now a backup mechanism - most fire commands come via monitor_active_games().

    Returns:
        str: The last fire tweet ID processed (or None if no tweets were processed)
    """
    print("\nChecking for @mention fire commands...")

    # Search for recent tweets mentioning the bot with "fire"
    query = f"@{BOT_USERNAME} fire"

    search_params = {
        'query': query,
        'max_results': 10,
        'tweet_fields': ['author_id', 'created_at', 'conversation_id'],
        'expansions': ['author_id'],
        'user_fields': ['username']
    }

    if last_fire_tweet_id:
        search_params['since_id'] = last_fire_tweet_id

    try:
        response = client.search_recent_tweets(**search_params)

        if response.data:
            print(f"Found {len(response.data)} @mention fire command(s)")

            for tweet in response.data:
                # Update last_fire_tweet_id
                last_fire_tweet_id = tweet.id

                # Skip if this is from the bot itself
                if BOT_USER_ID and str(tweet.author_id) == BOT_USER_ID:
                    print(f"Skipping bot's own tweet {tweet.id}")
                    continue

                print(f"Processing @mention fire command from tweet {tweet.id}")

                # Get thread_id with fallback
                tweet_id = str(tweet.id)
                conversation_id = str(tweet.conversation_id) if hasattr(tweet, 'conversation_id') else None
                author_id = str(tweet.author_id)

                # THREAD ID LOOKUP FIX: Use robust lookup with multiple fallback strategies
                game_data = get_game_robust(tweet_id, conversation_id, author_id)

                if not game_data:
                    print(f"No game found for tweet_id={tweet_id}, conversation_id={conversation_id}")
                    reply_text = "❌ No active game found. Make sure you're replying in the game thread!"
                    try:
                        client.create_tweet(
                            text=reply_text,
                            in_reply_to_tweet_id=tweet.id
                        )
                    except:
                        pass
                    continue

                thread_id = game_data['thread_id']

                # Check game is still active
                if game_data.get('game_state') != 'active':
                    print(f"Game {thread_id} is not active (state: {game_data.get('game_state')})")
                    continue

                # Get the author's username from expansions
                author_username = get_username_from_response(tweet.author_id, response)

                # TURN VALIDATION
                current_turn_player_id = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']

                if author_id != current_turn_player_id:
                    whose_turn = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']
                    reply_text = f"⏳ Hold up! It's @{whose_turn}'s turn. You'll go next!"
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id
                    )
                    print(f"Rejected turn for {author_id} - not their turn")
                    continue

                # Get opponent's username from expansions
                opponent_id = game_data['player2_id'] if author_id == game_data['player1_id'] else game_data['player1_id']
                opponent_username = get_username_from_response(opponent_id, response)

                # Process the fire command
                process_fire_tweet(tweet, game_data, author_username, opponent_username)

        else:
            print("No @mention fire commands found")

    except Exception as e:
        print(f"Error in handle_fire_command: {e}")
        logger.error(f"Error in handle_fire_command: {e}")

    return last_fire_tweet_id


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

            response = client.search_recent_tweets(**search_params)

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

                # TURN VALIDATION
                current_turn_player_id = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']

                if author_id != current_turn_player_id:
                    whose_turn = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']
                    reply_text = f"⏳ Hold up! It's @{whose_turn}'s turn. You'll go next!"
                    try:
                        client.create_tweet(
                            text=reply_text,
                            in_reply_to_tweet_id=tweet.id
                        )
                    except Exception as e:
                        logger.error(f"Failed to send turn rejection: {e}")
                    print(f"  Rejected - not {author_id}'s turn")
                    continue

                # Get usernames from expansions
                author_username = get_username_from_response(tweet.author_id, response)
                opponent_id = game_data['player2_id'] if author_id == game_data['player1_id'] else game_data['player1_id']
                opponent_username = get_username_from_response(opponent_id, response)

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

    # Track the last tweet IDs we've seen
    last_challenge_tweet_id = None
    last_fire_tweet_id = None

    while True:
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

            response = client.search_recent_tweets(**search_params)
            
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
                                        'you and me', 'with me']
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
                        if word.startswith('@') and word.lower() != f'@{BOT_USERNAME}'.lower():
                            # Strip @ from start AND punctuation from end
                            clean_username = word.lstrip('@').rstrip(',:;!?.')
                            if clean_username:  # Make sure something remains
                                mentions.append(clean_username)

                    if not mentions:
                        print(f"No opponent mentioned in tweet {tweet.id} - skipping")
                        # Reply to let user know they need to mention an opponent
                        try:
                            client.create_tweet(
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
                        opponent_user_response = client.get_user(username=opponent_username)
                        if not opponent_user_response.data:
                            print(f"Opponent @{opponent_username} not found")
                            # Reply with error - DON'T create game
                            try:
                                client.create_tweet(
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
                            client.create_tweet(
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
                            client.create_tweet(
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
                            client.create_tweet(
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

                    game_id = create_game(challenger_id, opponent_id, board1, board2, thread_id)

                    print(f"Created game with thread_id {game_id}")

                    blank_board = [[0 for _ in range(6)] for _ in range(6)]
                    p1_theme_color = '#2C2C2C'  # Black for Player 1
                    image_filename = generate_board_image(
                        blank_board,
                        f"@{challenger_username}",
                        p1_theme_color
                    )

                    # Get the post number for this bot tweet
                    post_number = increment_bot_post_count(thread_id)

                    # Get the game data to determine who goes first (random selection)
                    game_data = get_game_by_thread_id(thread_id)
                    game_number = game_data.get('game_number', 1) if game_data else 1

                    # Determine who goes first based on random selection in database
                    first_turn = game_data.get('turn', 'player1') if game_data else 'player1'
                    if first_turn == 'player1':
                        first_player_username = challenger_username
                    else:
                        first_player_username = opponent_username

                    # Log game creation with first player info
                    logger.info(f"Game created: {thread_id}, {challenger_username} vs {opponent_username}, first player: {first_player_username}")

                    reply_text = (
                        f"{post_number}/ ⚔️ Game #{game_number} has begun! ⚔️\n\n"
                        f"@{challenger_username} vs. @{opponent_username}\n\n"
                        f"📍 How to play:\n"
                        f"• Reply with: fire [coordinate]\n"
                        f"• Example: fire A1\n"
                        f"• Grid: A-F (rows) × 1-6 (columns)\n\n"
                        f"@{first_player_username}, you're up first! 🎯"
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

                    reply = client.create_tweet(
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
            # This is the PRIMARY way to detect fire commands (no @mention needed)
            # Players can just reply "fire A1" in the game thread
            monitor_active_games()

            # =================================================================
            # PART 3: Check for @mention fire commands (BACKUP)
            # =================================================================
            # This catches fire commands that include @battle_dinghy mention
            # Kept as a backup in case thread monitoring misses something
            last_fire_tweet_id = handle_fire_command(last_fire_tweet_id)

        except Exception as e:
            print(f"Error in main loop: {e}")
            logger.error(f"Error in main loop: {e}")
            print("Continuing to next poll cycle...")

        # Wait 60 seconds before polling again
        print("\nWaiting 60 seconds before next poll...")
        time.sleep(60)


if __name__ == "__main__":
    main_loop()
