import tweepy
import time
import os
import re
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
import logging
from supabase import create_client, Client

# Add the spec.md directory to the path to import game_logic
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'spec.md'))

from game_logic import create_new_board, process_shot, copy_board, get_ships_remaining, count_hits_and_misses
from image_generator import generate_board_image

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BattleDinghyBot:
    def __init__(self):
        """Initialize the Battle Dinghy bot with API credentials and client setup."""
        # Load environment variables
        load_dotenv()
        
        # Get X credentials from environment
        self.api_key = os.getenv('X_API_KEY')
        self.api_secret = os.getenv('X_API_SECRET')
        self.access_token = os.getenv('X_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')
        self.bearer_token = os.getenv('BEARER_TOKEN')
        
        # Get Supabase credentials
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        # Validate credentials
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret, self.bearer_token]):
            raise ValueError("Missing X API credentials in .env file. All 5 credentials are required.")
        
        if not all([self.supabase_url, self.supabase_key]):
            raise ValueError("Missing Supabase credentials in .env file.")
        
        logger.info("Successfully loaded API credentials from .env file")
        
        # Initialize tweepy client with proper authentication for production
        # Using OAuth 1.0a User Context for full access
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            wait_on_rate_limit=True
        )
        
        # Initialize API v1.1 for media uploads (v2 doesn't support media uploads)
        self.api_v1 = tweepy.API(
            tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_secret,
                self.access_token,
                self.access_token_secret
            ),
            wait_on_rate_limit=True
        )
        
        # Initialize Supabase client
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info("Successfully connected to Supabase")
        
        # Set bot username to battle_dinghy
        self.bot_username = "battle_dinghy"
        
        # Verify credentials 
        try:
            me = self.client.get_me()
            if me.data:
                logger.info(f"Bot initialized successfully, monitoring mentions of @{self.bot_username}")
                logger.info(f"Authenticated as @{me.data.username}")
                self.bot_user_id = me.data.id
                self.authenticated_username = me.data.username
            else:
                raise Exception("Could not get user information")
        except Exception as e:
            logger.error(f"Failed to verify credentials: {e}")
            raise
        
        self.last_tweet_file = "last_tweet_id.txt"
        
        # Keywords that indicate a challenge/game request
        self.challenge_keywords = ['play', 'challenge', 'game', 'battle', 'fight']
    
    def read_last_tweet_id(self):
        """Read the last processed tweet ID from file."""
        try:
            if os.path.exists(self.last_tweet_file):
                with open(self.last_tweet_file, 'r') as f:
                    tweet_id = f.read().strip()
                    if tweet_id:
                        logger.info(f"Last processed tweet ID: {tweet_id}")
                        return tweet_id
                    else:
                        logger.info("Last tweet ID file is empty")
                        return None
            else:
                logger.info("Last tweet ID file doesn't exist, starting fresh")
                return None
        except Exception as e:
            logger.error(f"Error reading last tweet ID: {e}")
            return None
    
    def write_last_tweet_id(self, tweet_id):
        """Write the last processed tweet ID to file."""
        try:
            with open(self.last_tweet_file, 'w') as f:
                f.write(str(tweet_id))
            logger.info(f"Updated last tweet ID to: {tweet_id}")
        except Exception as e:
            logger.error(f"Error writing last tweet ID: {e}")
    
    def search_mentions(self, since_id=None):
        """Search for recent tweets that mention @battle_dinghy."""
        try:
            query = f"@{self.bot_username} -is:retweet"
            search_params = {
                'query': query,
                'max_results': 10,
                'tweet_fields': ['id', 'text', 'author_id', 'created_at', 'public_metrics', 'referenced_tweets'],
                'user_fields': ['username', 'name'],
                'expansions': ['author_id']
            }
            
            if since_id:
                search_params['since_id'] = since_id
            
            logger.info(f"Searching for mentions with query: '{query}'")
            if since_id:
                logger.info(f"Looking for tweets newer than: {since_id}")
            
            response = self.client.search_recent_tweets(**search_params)
            
            if response.data:
                logger.info(f"Found {len(response.data)} mentions")
                users = {}
                if response.includes and 'users' in response.includes:
                    for user in response.includes['users']:
                        users[user.id] = user.username
                return response.data, users
            else:
                logger.info("No new tweets found")
                return [], {}
                
        except tweepy.Unauthorized as e:
            logger.error(f"Unauthorized error - check API credentials and access level: {e}")
            return [], {}
        except tweepy.Forbidden as e:
            logger.error(f"Forbidden error - check API access permissions: {e}")
            return [], {}
        except tweepy.TooManyRequests as e:
            logger.error(f"Rate limit exceeded: {e}")
            return [], {}
        except Exception as e:
            logger.error(f"Error searching for mentions: {e}")
            return [], {}
    
    def parse_challenge_tweet(self, tweet_text):
        """Parse a challenge tweet to extract challenger and opponent usernames."""
        tweet_lower = tweet_text.lower()
        
        # Check if tweet contains any challenge keywords
        has_keyword = any(keyword in tweet_lower for keyword in self.challenge_keywords)
        if not has_keyword:
            return None
        
        # Look for @mentions of other users
        mentions = re.findall(r'@(\w+)', tweet_text)
        mentions = [mention for mention in mentions if mention.lower() != self.bot_username.lower()]
        if mentions:
            return mentions[0]
        
        return None
    
    def parse_fire_command(self, tweet_text):
        """Parse a fire command to extract the coordinate."""
        # Look for "fire" followed by a coordinate (e.g., "fire B5", "fire A1")
        fire_pattern = r'fire\s+([A-Fa-f][1-6])'
        match = re.search(fire_pattern, tweet_text.lower())
        if match:
            return match.group(1).upper()  # Return coordinate in uppercase
        return None
    
    
    def get_user_id_by_username(self, username):
        """Get user ID by username."""
        try:
            user = self.client.get_user(username=username)
            if user.data:
                return user.data.id
            return None
        except Exception as e:
            logger.error(f"Error getting user ID for @{username}: {e}")
            return None
    
    def save_game_to_database(self, game_number, player1_id, player2_id, player1_board_data, player2_board_data, thread_id):
        """Save game state to Supabase database."""
        try:
            # Convert board data to JSON-serializable format
            game_data = {
                'game_number': game_number,
                'player1_id': player1_id,
                'player2_id': player2_id,
                'player1_board': player1_board_data,
                'player2_board': player2_board_data,
                'turn': 'player1',
                'game_state': 'active',
                'thread_id': thread_id,
                'created_at': datetime.now().isoformat()
            }
            
            # Insert into Supabase
            result = self.supabase.table('games').insert(game_data).execute()
            logger.info(f"Successfully saved game {game_number} to database")
            return result
        except Exception as e:
            logger.error(f"Error saving game to database: {e}")
            return None
    
    def get_next_game_number(self):
        """Get the next game number from the database."""
        try:
            # Get the highest game number from the database
            result = self.supabase.table('games').select('game_number').order('game_number', desc=True).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['game_number'] + 1
            else:
                return 1
        except Exception as e:
            logger.error(f"Error getting next game number: {e}")
            return 1
    
    def get_game_by_thread_id(self, thread_id):
        """Get game data by thread_id from the database."""
        try:
            result = self.supabase.table('games').select('*').eq('thread_id', thread_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting game by thread_id {thread_id}: {e}")
            return None
    
    def get_game_by_number(self, game_number):
        """Get game data by game_number from the database."""
        try:
            result = self.supabase.table('games').select('*').eq('game_number', game_number).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting game by number {game_number}: {e}")
            return None
    
    def get_username_by_id(self, user_id):
        """Get username by user ID."""
        try:
            user = self.client.get_user(id=user_id)
            if user.data:
                return user.data.username
            return None
        except Exception as e:
            logger.error(f"Error getting username for user ID {user_id}: {e}")
            return None
    
    def update_game_turn(self, game_id, new_turn):
        """Update the current turn in the database."""
        try:
            result = self.supabase.table('games').update({'turn': new_turn}).eq('id', game_id).execute()
            logger.info(f"Updated game {game_id} turn to {new_turn}")
            return result
        except Exception as e:
            logger.error(f"Error updating game turn: {e}")
            return None
    
    def handle_challenge(self, tweet_id, challenger_username, opponent_username, challenger_user_id):
        """Handle a challenge command by starting a new game instantly."""
        try:
            logger.info(f"Handling challenge from @{challenger_username} to @{opponent_username}")
            
            # Get opponent's user ID
            try:
                opponent_user_id = self.get_user_id_by_username(opponent_username)
                if not opponent_user_id:
                    logger.error(f"Could not get user ID for @{opponent_username}")
                    # Reply to user with error
                    self.client.create_tweet(
                        text=f"⚠️ Couldn't find user @{opponent_username}. Please check the username and try again!",
                        in_reply_to_tweet_id=tweet_id
                    )
                    return False
            except tweepy.TooManyRequests:
                logger.error("Rate limit hit while looking up user")
                self.client.create_tweet(
                    text=f"⚠️ Rate limit reached. Please try again in a few minutes!",
                    in_reply_to_tweet_id=tweet_id
                )
                return False
            except Exception as e:
                logger.error(f"Error looking up user @{opponent_username}: {e}")
                return False
            
            # Generate game boards for both players using create_new_board
            logger.info("Generating game boards for both players...")
            player1_board_data = create_new_board()
            player2_board_data = create_new_board()
            
            # Get next game number
            game_number = self.get_next_game_number()
            logger.info(f"Starting game #{game_number}")
            
            # Save game state to Supabase database
            logger.info("Saving game state to database...")
            try:
                self.save_game_to_database(
                    game_number=game_number,
                    player1_id=challenger_user_id,
                    player2_id=opponent_user_id,
                    player1_board_data=player1_board_data,
                    player2_board_data=player2_board_data,
                    thread_id=tweet_id
                )
            except Exception as e:
                logger.error(f"Failed to save game to database: {e}")
                self.client.create_tweet(
                    text=f"⚠️ Database error. Please try again later!",
                    in_reply_to_tweet_id=tweet_id
                )
                return False
            
            # Create initial empty boards for display (both players see empty target grids)
            # Players start with empty boards - they don't see opponent's ships
            player1_display_board = [[0 for _ in range(6)] for _ in range(6)]
            player2_display_board = [[0 for _ in range(6)] for _ in range(6)]

            # Ship status (all alive at start)
            player1_ships = {'Big Dinghy': True, 'Dinghy': True, 'Small Dinghy': True, 'total': 3}
            player2_ships = {'Big Dinghy': True, 'Dinghy': True, 'Small Dinghy': True, 'total': 3}

            # Generate starting board image for Player 1
            logger.info("Generating starting board image...")
            image_filename = generate_board_image(
                player1_display_board,
                f"@{challenger_username}",
                '#2C2C2C',  # Black theme for Player 1
                player1_ships
            )

            # Upload image using API v1.1
            logger.info("Uploading image to Twitter...")
            media = self.api_v1.media_upload(image_filename)
            
            # Create reply text
            reply_text = f"⚔️ Game #{game_number} has begun! ⚔️\n\n@{challenger_username} vs @{opponent_username}\n\n🎯 @{challenger_username} starts first!\n\nReply with 'Fire [coordinate]' (e.g., 'Fire C3') to take your shot!"
            
            # Post reply with image
            logger.info("Posting game start reply...")
            response = self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=tweet_id,
                media_ids=[media.media_id]
            )
            
            if response.data:
                logger.info(f"Successfully started game #{game_number} for @{challenger_username} vs @{opponent_username}")
                return True
            else:
                logger.error(f"Failed to start game for @{challenger_username} vs @{opponent_username}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling challenge: {e}")
            return False
    
    def handle_fire_command(self, tweet_id, tweet_author_id, coordinate, username):
        """Handle a fire command by processing the shot and updating the game state."""
        try:
            logger.info(f"Handling fire command from @{username} at coordinate {coordinate}")
            
            # Get the tweet to find the thread_id (reply to which tweet)
            try:
                tweet_data = self.client.get_tweet(tweet_id, tweet_fields=['referenced_tweets'])
                if not tweet_data.data or not tweet_data.data.referenced_tweets:
                    logger.error(f"Could not find referenced tweet for fire command from @{username}")
                    return False
                
                # Get the thread_id (the tweet this is replying to)
                thread_id = tweet_data.data.referenced_tweets[0].id
                logger.info(f"Fire command is in thread {thread_id}")
                
            except Exception as e:
                logger.error(f"Error getting tweet data for fire command: {e}")
                return False
            
            # Get game data from database using thread_id
            game_data = self.get_game_by_thread_id(thread_id)
            if not game_data:
                logger.error(f"No active game found for thread {thread_id}")
                return False
            
            # Enforce turn order - check if it's the correct player's turn
            current_turn = game_data['turn']
            if current_turn == 'player1':
                current_turn_id = game_data['player1_id']
            else:
                current_turn_id = game_data['player2_id']
            
            if tweet_author_id != current_turn_id:
                # Wrong player's turn
                logger.info(f"Not @{username}'s turn - current turn is {current_turn}")
                
                # Get the correct player's username
                correct_player_username = self.get_username_by_id(current_turn_id)
                if correct_player_username:
                    reply_text = f"Hold your fire, @{username}! It's not your turn yet. 🎯 @{correct_player_username}'s turn."
                else:
                    reply_text = f"Hold your fire, @{username}! It's not your turn yet."
                
                # Post reply
                self.client.create_tweet(
                    text=reply_text,
                    in_reply_to_tweet_id=tweet_id
                )
                return False
            
            # Get player usernames
            player1_username = self.get_username_by_id(game_data['player1_id'])
            player2_username = self.get_username_by_id(game_data['player2_id'])
            
            if not player1_username or not player2_username:
                logger.error("Could not get player usernames")
                return False
            
            # Determine which player is firing and which board to target
            if tweet_author_id == game_data['player1_id']:
                firing_player = player1_username
                target_board_data = game_data['player2_board']
                next_turn_player = player2_username
                next_turn = 'player2'
            else:
                firing_player = player2_username
                target_board_data = game_data['player1_board']
                next_turn_player = player1_username
                next_turn = 'player1'
            
            # Make a copy of the target board to avoid mutations
            target_board_copy = copy_board(target_board_data)

            # Process the shot - this updates the board with hit/miss markers
            shot_result_text, updated_board = process_shot(coordinate, target_board_copy, target_board_copy)
            logger.info(f"Shot at {coordinate}: {shot_result_text}")

            # Check ships remaining and game end condition
            ships_remaining = get_ships_remaining(updated_board)
            game_over = ships_remaining['total'] == 0

            # Update the target board in the database
            if tweet_author_id == game_data['player1_id']:
                # Player 1 fired at Player 2's board
                self.supabase.table('games').update({
                    'player2_board': updated_board,
                    'turn': next_turn,
                    'game_state': 'completed' if game_over else 'active'
                }).eq('thread_id', thread_id).execute()
            else:
                # Player 2 fired at Player 1's board
                self.supabase.table('games').update({
                    'player1_board': updated_board,
                    'turn': next_turn,
                    'game_state': 'completed' if game_over else 'active'
                }).eq('thread_id', thread_id).execute()

            # Generate board image with updated state
            logger.info("Generating updated board image...")
            image_filename = generate_board_image(
                updated_board,
                f"@{next_turn_player}",
                '#2C2C2C' if next_turn == 'player1' else '#808080',
                ships_remaining
            )

            # Upload image
            logger.info("Uploading updated image...")
            media = self.api_v1.media_upload(image_filename)
            
            # Get scoreboard stats
            hits, misses = count_hits_and_misses(updated_board)

            # Create reply text based on shot result and game state
            if game_over:
                reply_text = (
                    f"{shot_result_text}\n\n"
                    f"🎉 GAME OVER! @{firing_player} WINS! 🏆\n\n"
                    f"📊 Final Stats:\n"
                    f"• Shots: {hits + misses}\n"
                    f"• Hits: {hits} 💥\n"
                    f"• Misses: {misses} ⭕\n"
                    f"• Accuracy: {round(hits/(hits+misses)*100) if hits+misses > 0 else 0}%\n\n"
                    f"Game #{game_data.get('game_number', 'N/A')}"
                )
            else:
                reply_text = (
                    f"{shot_result_text}\n\n"
                    f"📊 Stats: {hits} hits, {misses} misses\n"
                    f"🚢 Ships left: {ships_remaining['total']}/3\n\n"
                    f"🎯 @{next_turn_player}'s turn!\n\n"
                    f"Game #{game_data.get('game_number', 'N/A')}"
                )
            
            # Post reply
            logger.info("Posting fire command reply...")
            response = self.client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=tweet_id,
                media_ids=[media.media_id]
            )
            
            if response.data:
                logger.info(f"Successfully processed fire command from @{firing_player} at {coordinate}")
                return True
            else:
                logger.error(f"Failed to post fire command reply for @{firing_player}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling fire command: {e}")
            return False
    
    def process_mentions(self, tweets, users):
        """Process new mentions and handle challenge commands."""
        if not tweets:
            return None
        
        latest_tweet_id = None
        
        # Process tweets in chronological order (oldest first)
        for tweet in reversed(tweets):
            latest_tweet_id = tweet.id
            username = users.get(tweet.author_id, "unknown")
            
            logger.info(f"Processing tweet from @{username}: '{tweet.text[:50]}...'")
            
            # Skip our own tweets to avoid infinite loops
            if username.lower() == self.authenticated_username.lower():
                logger.info(f"Skipping own tweet from @{username}")
                continue
            
            # Check if this tweet is a reply to another tweet
            is_reply = tweet.referenced_tweets is not None and len(tweet.referenced_tweets) > 0
            
            if is_reply:
                # This is a reply - check for fire commands only
                logger.info(f"Tweet from @{username} is a reply - checking for fire command")
                
                coordinate = self.parse_fire_command(tweet.text)
                
                if coordinate:
                    logger.info(f"Found fire command from @{username} at coordinate {coordinate}")
                    # Handle the fire command
                    self.handle_fire_command(tweet.id, tweet.author_id, coordinate, username)
                else:
                    logger.info(f"Unknown reply from @{username} - ignoring")
            else:
                # This is a top-level mention - check for challenge commands only
                logger.info(f"Tweet from @{username} is a top-level mention - checking for challenge")
                
                opponent_username = self.parse_challenge_tweet(tweet.text)
                
                if opponent_username:
                    logger.info(f"Found challenge from @{username} to @{opponent_username}")
                    
                    # Get challenger's user ID
                    challenger_user_id = self.get_user_id_by_username(username)
                    if not challenger_user_id:
                        logger.error(f"Could not get user ID for @{username}")
                        continue
                    
                    # Handle the challenge (instant game start)
                    self.handle_challenge(tweet.id, username, opponent_username, challenger_user_id)
                else:
                    logger.info(f"Unknown top-level mention from @{username} - ignoring")
        
        return latest_tweet_id
    
    def run(self):
        """Main bot loop - runs continuously checking for mentions."""
        logger.info("="*60)
        logger.info("Starting Battle Dinghy Bot for @battle_dinghy")
        logger.info("="*60)
        logger.info(f"Authenticated as: @{self.authenticated_username}")
        logger.info(f"Monitoring mentions of: @{self.bot_username}")
        logger.info("Bot will check for mentions every 60 seconds")
        logger.info("Looking for challenge keywords: play, challenge, game, battle, fight + user mentions")
        logger.info("Game flow: Challenge → Instant game start → Players take turns")
        logger.info("Press Ctrl+C to stop the bot")
        logger.info("="*60)
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Get last processed tweet ID
                last_tweet_id = self.read_last_tweet_id()
                
                # Search for new mentions
                tweets, users = self.search_mentions(since_id=last_tweet_id)
                
                # Reset error counter on successful search
                consecutive_errors = 0
                
                # Process mentions
                latest_processed_id = self.process_mentions(tweets, users)
                
                # Update last tweet ID if we processed any tweets
                if latest_processed_id:
                    self.write_last_tweet_id(latest_processed_id)
                
                # Wait 60 seconds before next check
                logger.info("Waiting 60 seconds before next check...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in main loop: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many consecutive errors ({consecutive_errors}). Stopping bot.")
                    break
                
                logger.info(f"Continuing after 60 seconds... (Error {consecutive_errors}/{max_consecutive_errors})")
                time.sleep(60)

def main():
    """Main function to run the bot."""
    try:
        # Create and run the bot
        bot = BattleDinghyBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        logger.error("Check your .env file and X API credentials")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
