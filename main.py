import tweepy
import os
import time
import sys
from dotenv import load_dotenv

# Add the spec.md directory to the path to import game_logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))

# Import our game modules
from game_logic import create_new_board, process_shot, copy_board, get_ships_remaining, count_hits_and_misses
from image_generator import generate_board_image
from db import create_game, get_game_by_thread_id, update_game_after_shot, increment_bot_post_count

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


def handle_fire_command(last_fire_tweet_id=None):
    """
    Handle fire commands from players.

    This function searches for tweets containing "fire" commands and processes them.

    Returns:
        str: The last fire tweet ID processed (or None if no tweets were processed)
    """
    print("\nChecking for fire commands...")

    # Search for recent tweets mentioning the bot with "fire"
    query = f"{BOT_USERNAME} fire"

    search_params = {
        'query': query,
        'max_results': 10,
        'tweet_fields': ['author_id', 'created_at', 'conversation_id']
    }

    if last_fire_tweet_id:
        search_params['since_id'] = last_fire_tweet_id

    try:
        response = client.search_recent_tweets(**search_params)

        if response.data:
            print(f"Found {len(response.data)} fire command(s)")

            for tweet in response.data:
                # Update last_fire_tweet_id
                last_fire_tweet_id = tweet.id

                # Skip if this is from the bot itself
                if tweet.author_id == BOT_USERNAME:
                    continue

                print(f"Processing fire command from tweet {tweet.id}")

                # Get thread_id
                thread_id = str(tweet.conversation_id) if hasattr(tweet, 'conversation_id') else str(tweet.id)

                # Get the game by thread_id
                game_data = get_game_by_thread_id(thread_id)

                if not game_data:
                    print(f"No game found for thread {thread_id}")
                    continue

                author_id = str(tweet.author_id)

                # Get the author's username for display purposes
                try:
                    user_response = client.get_user(id=tweet.author_id)
                    author_username = user_response.data.username if user_response.data else author_id
                except:
                    author_username = author_id  # Fallback to ID if lookup fails

                # Check if it's the author's turn (compare against player IDs based on turn)
                current_turn_player_id = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']

                if author_id != current_turn_player_id:
                    # Not their turn - get opponent name for helpful message
                    whose_turn = game_data['player1_id'] if game_data['turn'] == 'player1' else game_data['player2_id']
                    reply_text = f"⏳ Hold up! It's @{whose_turn}'s turn. You'll go next!"
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id
                    )
                    print(f"Rejected turn for {author_id} - not their turn")
                    continue

                # Parse the coordinate from the tweet text
                tweet_text = tweet.text.lower()
                words = tweet_text.split()

                coordinate = None

                # Look for coordinate after "fire", "at", "shoot", or just find any A-F + 1-6 pattern
                for i, word in enumerate(words):
                    if word in ["fire", "shoot", "at"]:
                        # Check next word
                        if i + 1 < len(words):
                            potential_coord = words[i + 1].strip(',:;!?.')
                            coordinate = potential_coord
                            break

                # If no coordinate found after keywords, search for A-F + 1-6 pattern anywhere
                if not coordinate:
                    import re
                    # Match patterns like: a1, A1, 1a, 1A, a-1, a 1
                    pattern = r'[a-f][1-6]|[1-6][a-f]'
                    for word in words:
                        clean_word = word.strip(',:;!?.')
                        match = re.search(pattern, clean_word)
                        if match:
                            coord_str = match.group()
                            # Normalize to A1 format (letter first)
                            if coord_str[0].isdigit():
                                coordinate = coord_str[1] + coord_str[0]  # Swap to letter-first
                            else:
                                coordinate = coord_str
                            break

                if not coordinate:
                    reply_text = "🎯 Please specify a coordinate! Example: 'fire A1' (A-F, 1-6)"
                    client.create_tweet(
                        text=reply_text,
                        in_reply_to_tweet_id=tweet.id
                    )
                    continue

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
                    shooter_board_theme = p2_theme  # Show P2's board (gray) with hits
                    opponent_board_theme = p1_theme  # Show P1's board (black) to P2
                else:
                    # Player 2 is shooting at Player 1's board
                    target_board = game_data['player1_board']
                    board_to_update = "player1_board"
                    opponent_id = player1_id
                    next_turn = 'player1'
                    shooter_board_theme = p1_theme  # Show P1's board (black) with hits
                    opponent_board_theme = p2_theme  # Show P2's board (gray) to P1

                # Get opponent's username
                try:
                    opponent_user_response = client.get_user(id=opponent_id)
                    opponent_username = opponent_user_response.data.username if opponent_user_response.data else opponent_id
                except:
                    opponent_username = opponent_id  # Fallback to ID if lookup fails

                # Make a copy of the target board to avoid mutations
                target_board_copy = copy_board(target_board)

                # Process the shot - this updates the target board to mark hit/miss
                result_text, updated_board = process_shot(
                    coordinate,
                    target_board_copy,
                    target_board_copy  # We're marking hits/misses on the target board itself
                )

                print(f"Shot result: {result_text}")

                # Check ships remaining and game end condition
                ships_remaining = get_ships_remaining(updated_board)
                game_over = ships_remaining['total'] == 0

                # Update the game state in database
                if game_over:
                    update_game_after_shot(
                        thread_id,
                        board_to_update,
                        updated_board,
                        'completed'  # Mark game as completed
                    )
                else:
                    update_game_after_shot(
                        thread_id,
                        board_to_update,
                        updated_board,
                        next_turn
                    )

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
                import tweepy
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
                    # Get the opponent's board for the prompt tweet
                    if author_id == player1_id:
                        opponent_board = game_data['player1_board']  # Opponent sees their own board
                    else:
                        opponent_board = game_data['player2_board']

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

        else:
            print("No fire commands found")

    except Exception as e:
        print(f"Error in handle_fire_command: {e}")

    return last_fire_tweet_id


def main_loop():
    """
    Main game loop that polls for both challenges and fire commands.
    """
    print(f"Starting Battle Dinghy bot polling for {BOT_USERNAME}...")

    # Track the last tweet IDs we've seen
    last_challenge_tweet_id = None
    last_fire_tweet_id = None

    while True:
        try:
            # Check for new challenges
            print("\nChecking for new challenges...")
            query = f"{BOT_USERNAME} play"

            search_params = {
                'query': query,
                'max_results': 10,
                'tweet_fields': ['author_id', 'created_at', 'conversation_id']
            }

            if last_challenge_tweet_id:
                search_params['since_id'] = last_challenge_tweet_id

            response = client.search_recent_tweets(**search_params)

            if response.data:
                print(f"Found {len(response.data)} new challenge(s)")

                for tweet in response.data:
                    last_challenge_tweet_id = tweet.id

                    if tweet.author_id == BOT_USERNAME:
                        continue

                    print(f"Processing challenge tweet {tweet.id}")

                    challenger_id = str(tweet.author_id)

                    # Get challenger's username
                    try:
                        challenger_user_response = client.get_user(id=tweet.author_id)
                        challenger_username = challenger_user_response.data.username if challenger_user_response.data else challenger_id
                    except:
                        challenger_username = challenger_id

                    tweet_text = tweet.text
                    mentions = []
                    words = tweet_text.split()
                    for word in words:
                        if word.startswith('@') and word.lower() != f'@{BOT_USERNAME}'.lower():
                            mentions.append(word.lstrip('@'))

                    if not mentions:
                        continue

                    opponent_username = mentions[0]

                    # Get opponent's user ID from username
                    try:
                        opponent_user_response = client.get_user(username=opponent_username)
                        opponent_id = str(opponent_user_response.data.id) if opponent_user_response.data else opponent_username
                    except:
                        opponent_id = opponent_username  # Fallback

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

                    # Get the game number from the database
                    game_data = get_game_by_thread_id(thread_id)
                    game_number = game_data.get('game_number', 1) if game_data else 1

                    reply_text = (
                        f"{post_number}/ ⚔️ Game #{game_number} has begun! ⚔️\n\n"
                        f"@{challenger_username} vs. @{opponent_username}\n\n"
                        f"📍 How to play:\n"
                        f"• Reply with: fire [coordinate]\n"
                        f"• Example: fire A1\n"
                        f"• Grid: A-F (rows) × 1-6 (columns)\n\n"
                        f"@{challenger_username}, you're up first! 🎯"
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

            # Check for fire commands and update last_fire_tweet_id
            last_fire_tweet_id = handle_fire_command(last_fire_tweet_id)

        except Exception as e:
            print(f"Error in main loop: {e}")
            print("Continuing to next poll cycle...")

        # Wait 60 seconds before polling again
        print("\nWaiting 60 seconds before next poll...")
        time.sleep(60)


if __name__ == "__main__":
    main_loop()
