# Battle Dinghy - Twitter Battleship Bot

A Twitter bot that allows users to play Battleship (Battle Dinghy) against each other through tweets.

## Overview

Battle Dinghy is an automated Twitter bot that manages multiplayer Battleship games. Players can challenge each other by mentioning the bot, and take turns firing at coordinates on a 6x6 grid. The bot handles game state, validates moves, tracks hits/misses, and declares winners.

## Features

- **Multiplayer Gameplay**: Challenge any Twitter user to a game
- **Automated Game Management**: Bot handles all game state and turn order
- **Visual Board Display**: Generates and posts board images after each turn
- **Statistics Tracking**: Tracks hits, misses, accuracy, and game numbers
- **Persistent Storage**: Uses Supabase for game state persistence
- **Error Handling**: Robust error handling for API rate limits and network issues

## Fleet Configuration

Each player has 3 ships:
- **Big Dinghy**: 4 squares
- **Dinghy**: 3 squares
- **Small Dinghy**: 2 squares

## Game Rules

1. Players take turns firing at coordinates (A-F, 1-6)
2. Hit all squares of a ship to sink it
3. First player to sink all opponent ships wins
4. Grid is 6x6 (rows A-F, columns 1-6)

## Installation

### Prerequisites

- Python 3.9 or higher
- Twitter Developer Account with API credentials
- Supabase account and project

### Setup Steps

1. **Clone the repository**
```bash
git clone <repository-url>
cd battle_dinghy
```

2. **Create virtual environment**
```bash
python -m venv .venv
```

3. **Activate virtual environment**
- Windows:
```bash
.venv\Scripts\activate
```
- macOS/Linux:
```bash
source .venv/bin/activate
```

4. **Install dependencies**
```bash
pip install -r requirements.txt
```

5. **Configure environment variables**

Create a `.env` file in the project root:

```env
# Twitter API Credentials
X_API_KEY=your_api_key_here
X_API_SECRET=your_api_secret_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
BEARER_TOKEN=your_bearer_token_here

# Supabase Credentials
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

See `env_example.txt` for reference.

### Getting Twitter API Credentials

1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app
3. Set app permissions to "Read and Write"
4. Generate API keys and tokens
5. Copy all 5 credentials to your `.env` file

### Setting Up Supabase

1. Create account at [Supabase](https://supabase.com)
2. Create a new project
3. Go to Project Settings > API
4. Copy the Project URL and anon/public key
5. Create the games table (see Database Schema section)

## Database Schema

Create the following table in Supabase:

```sql
CREATE TABLE games (
  id BIGSERIAL PRIMARY KEY,
  game_number INTEGER NOT NULL,
  player1_id TEXT NOT NULL,
  player2_id TEXT NOT NULL,
  player1_board JSONB NOT NULL,
  player2_board JSONB NOT NULL,
  turn TEXT NOT NULL CHECK (turn IN ('player1', 'player2')),
  game_state TEXT DEFAULT 'active' CHECK (game_state IN ('active', 'completed')),
  thread_id TEXT UNIQUE NOT NULL,
  bot_post_count INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc', NOW())
);

CREATE INDEX idx_games_thread_id ON games(thread_id);
CREATE INDEX idx_games_game_state ON games(game_state);
CREATE INDEX idx_games_created_at ON games(created_at);
```

### Database Fields

- `id`: Unique identifier (auto-generated)
- `game_number`: Sequential game number for display
- `player1_id`: Twitter user ID of player 1
- `player2_id`: Twitter user ID of player 2
- `player1_board`: Player 1's ship positions (6x6 grid as JSON)
- `player2_board`: Player 2's ship positions (6x6 grid as JSON)
- `turn`: Current turn ('player1' or 'player2')
- `game_state`: Game status ('active' or 'completed')
- `thread_id`: Twitter conversation/thread ID
- `bot_post_count`: Number of bot posts in this thread
- `created_at`: Game creation timestamp

## Usage

### Starting the Bot

**Option 1: Using bot.py (Recommended)**
```bash
python bot.py
```

**Option 2: Using main.py**
```bash
python main.py
```

The bot will:
- Poll Twitter every 60 seconds for mentions
- Process challenge requests
- Handle fire commands
- Update game states
- Post responses with board images

### Playing a Game

**1. Challenge another player:**
```
@battle_dinghy play @opponent
```

Alternative challenge keywords: `challenge`, `game`, `battle`, `fight`

**2. Bot starts the game and posts the initial board**

**3. Take turns firing:**
```
@battle_dinghy fire A1
```

Valid coordinates: A-F (rows), 1-6 (columns)

**4. Bot responds with:**
- Hit/Miss result
- Updated board image
- Ship status
- Statistics
- Next player's turn

**5. Game ends when all ships are sunk**

## Project Structure

```
battle_dinghy/
├── bot.py                    # Main bot implementation (recommended)
├── main.py                   # Alternative bot implementation
├── db.py                     # Database operations
├── image_generator.py        # Board image generation
├── spec.md/
│   ├── game_logic.py        # Core game logic
│   └── README.md            # Game specification
├── test_game_logic.py       # Unit tests
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (not in git)
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

### Key Files

- **bot.py**: Class-based bot implementation with logging and error handling
- **main.py**: Function-based bot with simpler architecture
- **db.py**: Supabase database interface functions
- **game_logic.py**: Board creation, shot processing, ship tracking
- **image_generator.py**: PIL-based board visualization
- **test_game_logic.py**: Comprehensive unit tests for game logic

## Testing

Run unit tests:
```bash
python -m unittest test_game_logic.py -v
```

Test coverage includes:
- Board creation and validation
- Shot processing (hits, misses, sinks)
- Coordinate parsing
- Ship tracking
- Utility functions

## Utility Scripts

- `check_env.py` - Verify environment variables
- `verify_setup.py` - Test Twitter API and Supabase connections
- `check_table_schema.py` - Verify database schema
- `diagnose_supabase.py` - Debug Supabase issues
- `clear_games.py` - Delete all games from database
- `test_connection.py` - Test Supabase connectivity

## Troubleshooting

### Bot not responding to mentions
- Check Twitter API credentials in `.env`
- Verify bot account has correct permissions
- Check rate limits in Twitter Developer Portal
- Review logs for error messages

### Database errors
- Verify Supabase credentials
- Check table schema matches specification
- Test connection with `test_connection.py`
- Review Supabase dashboard for errors

### Image generation issues
- Ensure Pillow is installed: `pip install Pillow`
- Check font availability on your system
- Verify write permissions in project directory

### Rate limiting
- Bot implements `wait_on_rate_limit=True`
- Polls every 60 seconds to stay within limits
- Monitor usage in Twitter Developer Portal

## Development

### Adding features
1. Create feature branch
2. Write tests first (TDD)
3. Implement feature
4. Run test suite
5. Test with real Twitter account
6. Submit pull request

### Code style
- Follow PEP 8
- Use type hints where appropriate
- Add docstrings to all functions
- Include error handling
- Log important events

### Testing with Twitter
- Use a test Twitter account
- Test in a private conversation first
- Monitor logs carefully
- Have a way to stop the bot quickly

## Security Considerations

- **Never commit `.env` file** - Contains sensitive credentials
- **Use environment variables** - Never hardcode credentials
- **Validate user input** - Prevent injection attacks
- **Rate limiting** - Respect Twitter API limits
- **Monitor bot behavior** - Watch for abuse or spam
- **Secure Supabase** - Use RLS (Row Level Security) policies

## Deployment

### Cloud Hosting (Recommended)

For production deployment, use a cloud hosting platform. See **[DEPLOYMENT.md](DEPLOYMENT.md)** for detailed instructions.

**Quick Start Options:**
- **Railway** (Easiest): Connect GitHub repo, add env vars, deploy
- **Render** (Free tier): Create Background Worker, configure, deploy
- **DigitalOcean**: App Platform worker service

All deployment files are included:
- `Procfile` - Tells platform how to run the bot
- `runtime.txt` - Specifies Python version
- `DEPLOYMENT.md` - Complete deployment guide

### Running on a Local Server

1. **Use screen or tmux**:
```bash
screen -S battle_dinghy
python main_polling.py
# Press Ctrl+A, then D to detach
```

2. **Use systemd (Linux)**:
Create `/etc/systemd/system/battle-dinghy.service`:
```ini
[Unit]
Description=Battle Dinghy Twitter Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/battle_dinghy
ExecStart=/path/to/.venv/bin/python main_polling.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. **Use PM2** (Node.js required):
```bash
pm2 start main_polling.py --interpreter python
pm2 save
pm2 startup
```

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Add your license here]

## Support

- Report bugs via GitHub Issues
- Check existing issues before creating new ones
- Include logs and error messages
- Describe steps to reproduce

## Credits

Built with:
- [Tweepy](https://www.tweepy.org/) - Twitter API library
- [Supabase](https://supabase.com/) - Database and backend
- [Pillow](https://python-pillow.org/) - Image generation
- [Python-dotenv](https://github.com/theskumar/python-dotenv) - Environment management

## Changelog

### Version 1.0.0 (Current)
- Initial release
- Core gameplay functionality
- Twitter bot integration
- Supabase persistence
- Board visualization
- Error handling
- Unit tests
# Trigger redeploy
