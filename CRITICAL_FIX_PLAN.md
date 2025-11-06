# Critical Fix: Ship Sinking Bug

## Problem
The `process_shot()` function expects TWO boards:
- `secret_board`: Original ship positions (never modified)
- `hits_board`: Tracking board (gets hits=1, misses=9)

But BOTH bot.py and main.py pass **the same board twice**:
```python
process_shot(coordinate, target_board_copy, target_board_copy)
```

This causes the ship positions to be overwritten with `1` (hit) or `9` (miss), making ship sinking detection fail.

## Why Ship Sinking Fails
1. Ship placed at A1-A4 with ID=4 (Big Dinghy)
2. Player fires at A1 → `process_shot()` marks `board[0][0] = 1` (hit)
3. Ship sinking check looks for `board[r][c] == 4` but finds `1` instead
4. Ship never gets marked as sunk

## Solution Options

### Option A: Store TWO boards in DB (BEST but requires schema change)
```sql
ALTER TABLE games ADD COLUMN player1_secret_board JSONB;
ALTER TABLE games ADD COLUMN player2_secret_board JSONB;
-- Rename existing to player1_current_board, player2_current_board
```

### Option B: Never modify boards, track hits separately (requires refactor)
```sql
ALTER TABLE games ADD COLUMN player1_hits JSONB;  -- Array of coordinates
ALTER TABLE games ADD COLUMN player2_hits JSONB;
```

### Option C: Change board values to preserve ship info (EASIEST)
Instead of overwriting ship IDs with `1` for hit, use different values:
- 2,3,4 = unhit ships
- 12, 13, 14 = hit ships (10 + ship_id)
- 9 = miss
- 0 = water

Then sinking check looks for `board[r][c] == ship_id OR board[r][c] == (10 + ship_id)`

## Implementation: Option C (Quick Fix)

Modify `process_shot()` to use value 10+ship_id for hits:
- Hit Big Dinghy (4) → mark as 14
- Hit Dinghy (3) → mark as 13
- Hit Small Dinghy (2) → mark as 12

This preserves which ship was hit while marking it as damaged.
