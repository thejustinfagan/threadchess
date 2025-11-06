# Battle Dinghy Database Schema

This document describes the database schema for the Battle Dinghy Twitter bot.

## Overview

The database uses Supabase (PostgreSQL) to store game state, player information, and game history. All game data is stored in a single `games` table with JSONB columns for board states.

## Tables

### `games` Table

Primary table storing all game information.

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
```

#### Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key, unique game identifier |
| `game_number` | INTEGER | NO | - | Sequential display number for games |
| `player1_id` | TEXT | NO | - | Twitter user ID of player 1 (challenger) |
| `player2_id` | TEXT | NO | - | Twitter user ID of player 2 (opponent) |
| `player1_board` | JSONB | NO | - | Player 1's ship positions and hit/miss state |
| `player2_board` | JSONB | NO | - | Player 2's ship positions and hit/miss state |
| `turn` | TEXT | NO | - | Current turn: 'player1' or 'player2' |
| `game_state` | TEXT | NO | 'active' | Game status: 'active' or 'completed' |
| `thread_id` | TEXT | NO | - | Twitter conversation/thread ID (unique) |
| `bot_post_count` | INTEGER | NO | 0 | Count of bot posts in this thread |
| `created_at` | TIMESTAMP WITH TIME ZONE | NO | now() | Game creation timestamp (UTC) |

#### Constraints

- **Primary Key**: `id`
- **Unique**: `thread_id` (ensures one game per Twitter thread)
- **Check Constraints**:
  - `turn` must be either 'player1' or 'player2'
  - `game_state` must be either 'active' or 'completed'

#### Indexes

```sql
-- Primary key index (automatic)
CREATE INDEX games_pkey ON games(id);

-- Thread ID index for fast lookups
CREATE INDEX idx_games_thread_id ON games(thread_id);

-- Game state index for filtering active games
CREATE INDEX idx_games_game_state ON games(game_state);

-- Created at index for sorting/filtering by date
CREATE INDEX idx_games_created_at ON games(created_at);
```

## Board Data Structure

The `player1_board` and `player2_board` columns store JSONB data representing the 6x6 game board.

### Board Format

Boards are stored as a 2D array (6x6 grid):

```json
[
  [0, 0, 4, 4, 4, 4],
  [0, 0, 0, 0, 0, 0],
  [2, 2, 0, 3, 3, 3],
  [0, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 0, 0]
]
```

### Cell Values

| Value | Meaning |
|-------|---------|
| `0` | Water (empty cell) |
| `1` | Hit ship cell |
| `2` | Small Dinghy (2 cells) |
| `3` | Dinghy (3 cells) |
| `4` | Big Dinghy (4 cells) |
| `9` | Miss (water that was fired upon) |

### Board State Transitions

1. **Game Start**: Ships placed with IDs (2, 3, 4), rest is water (0)
2. **Miss**: Water (0) → Miss (9)
3. **Hit**: Ship (2, 3, 4) → Hit (1)
4. **Ship Sunk**: All cells of a ship are marked as Hit (1)

### Example Board States

**Initial Board (Player 1)**:
```json
[
  [4, 4, 4, 4, 0, 0],  // Big Dinghy horizontal
  [0, 0, 0, 0, 0, 0],
  [0, 3, 3, 3, 0, 0],  // Dinghy horizontal
  [0, 0, 0, 0, 0, 0],
  [2, 0, 0, 0, 0, 0],  // Small Dinghy vertical
  [2, 0, 0, 0, 0, 0]
]
```

**After Several Turns**:
```json
[
  [1, 1, 4, 4, 9, 0],  // 2 hits on Big Dinghy, 1 miss
  [0, 9, 0, 0, 0, 0],  // 1 miss
  [9, 3, 1, 3, 0, 0],  // 1 hit on Dinghy, 1 miss
  [0, 0, 0, 0, 0, 9],  // 1 miss
  [2, 0, 0, 0, 0, 0],  // Small Dinghy untouched
  [2, 0, 0, 0, 0, 0]
]
```

**Small Dinghy Sunk**:
```json
[
  [1, 1, 4, 4, 9, 0],
  [0, 9, 0, 0, 0, 0],
  [9, 3, 1, 3, 0, 0],
  [0, 0, 0, 0, 0, 9],
  [1, 0, 0, 0, 0, 0],  // Small Dinghy fully hit
  [1, 0, 0, 0, 0, 0]   // = sunk
]
```

## Queries

### Common Queries

**Get active games:**
```sql
SELECT * FROM games
WHERE game_state = 'active'
ORDER BY created_at DESC;
```

**Get game by thread ID:**
```sql
SELECT * FROM games
WHERE thread_id = '1234567890';
```

**Get games for a player:**
```sql
SELECT * FROM games
WHERE player1_id = '987654321' OR player2_id = '987654321'
ORDER BY created_at DESC;
```

**Get completed games:**
```sql
SELECT * FROM games
WHERE game_state = 'completed'
ORDER BY created_at DESC;
```

**Count total games:**
```sql
SELECT COUNT(*) FROM games;
```

**Get latest game number:**
```sql
SELECT MAX(game_number) FROM games;
```

## Row Level Security (RLS)

For production, consider implementing RLS policies:

```sql
-- Enable RLS
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Policy: Allow bot to insert games
CREATE POLICY "Bot can insert games"
ON games FOR INSERT
TO authenticated
WITH CHECK (true);

-- Policy: Allow bot to read all games
CREATE POLICY "Bot can read all games"
ON games FOR SELECT
TO authenticated
USING (true);

-- Policy: Allow bot to update games
CREATE POLICY "Bot can update games"
ON games FOR UPDATE
TO authenticated
USING (true);

-- Policy: Public read access (optional)
CREATE POLICY "Public read access"
ON games FOR SELECT
TO anon
USING (true);
```

## Maintenance

### Cleanup Old Games

Delete games older than 30 days:
```sql
DELETE FROM games
WHERE created_at < NOW() - INTERVAL '30 days'
AND game_state = 'completed';
```

### Archive Old Games

Create an archive table:
```sql
CREATE TABLE games_archive AS
SELECT * FROM games WHERE false;

-- Move old completed games to archive
INSERT INTO games_archive
SELECT * FROM games
WHERE created_at < NOW() - INTERVAL '90 days'
AND game_state = 'completed';

DELETE FROM games
WHERE created_at < NOW() - INTERVAL '90 days'
AND game_state = 'completed';
```

### Vacuum and Analyze

Optimize table performance:
```sql
VACUUM ANALYZE games;
```

## Backup Strategy

1. **Automated Backups**: Supabase provides automatic daily backups
2. **Manual Backups**: Use pg_dump for additional safety
3. **Point-in-Time Recovery**: Available in Supabase Pro plan

### Manual Backup
```bash
pg_dump -h db.xxx.supabase.co -U postgres -d postgres -t games > backup.sql
```

### Restore
```bash
psql -h db.xxx.supabase.co -U postgres -d postgres < backup.sql
```

## Migration Guide

### Adding New Columns

```sql
-- Add a new column
ALTER TABLE games
ADD COLUMN winner_id TEXT;

-- Add column with default
ALTER TABLE games
ADD COLUMN total_moves INTEGER DEFAULT 0;
```

### Modifying Existing Columns

```sql
-- Change column type
ALTER TABLE games
ALTER COLUMN game_number TYPE BIGINT;

-- Add constraint
ALTER TABLE games
ADD CONSTRAINT check_positive_post_count
CHECK (bot_post_count >= 0);
```

## Performance Considerations

1. **Indexing**: Ensure indexes exist on frequently queried columns
2. **JSONB Queries**: Use JSONB operators for efficient board queries
3. **Connection Pooling**: Use connection pooling for high traffic
4. **Query Optimization**: Use EXPLAIN ANALYZE to optimize slow queries

### JSONB Queries Example

```sql
-- Find games where a specific ship is intact
SELECT * FROM games
WHERE player1_board @> '[[2]]'::jsonb;

-- Count hits on player 2's board
SELECT
  thread_id,
  jsonb_array_length(
    jsonb_path_query_array(player2_board, '$[*][*] ? (@ == 1)')
  ) as hit_count
FROM games;
```

## Troubleshooting

### Connection Issues
- Check Supabase project status
- Verify credentials in `.env`
- Test connection with `test_connection.py`

### Data Inconsistencies
- Run `check_table_schema.py` to verify schema
- Check for orphaned records
- Validate JSONB structure

### Performance Issues
- Review query performance with EXPLAIN
- Check index usage
- Monitor table size and vacuum status
- Consider partitioning for very large tables

## Future Enhancements

Potential schema additions:

1. **Player Statistics Table**
```sql
CREATE TABLE player_stats (
  player_id TEXT PRIMARY KEY,
  total_games INTEGER DEFAULT 0,
  wins INTEGER DEFAULT 0,
  losses INTEGER DEFAULT 0,
  total_shots INTEGER DEFAULT 0,
  total_hits INTEGER DEFAULT 0,
  accuracy DECIMAL(5,2) DEFAULT 0.0
);
```

2. **Game Moves Table** (for replay/analysis)
```sql
CREATE TABLE game_moves (
  id BIGSERIAL PRIMARY KEY,
  game_id BIGINT REFERENCES games(id),
  move_number INTEGER NOT NULL,
  player_id TEXT NOT NULL,
  coordinate TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

3. **Leaderboard View**
```sql
CREATE VIEW leaderboard AS
SELECT
  player_id,
  total_games,
  wins,
  ROUND((wins::DECIMAL / NULLIF(total_games, 0)) * 100, 2) as win_rate,
  accuracy
FROM player_stats
ORDER BY wins DESC, win_rate DESC
LIMIT 100;
```
