# bot.py - DEPRECATED

**DO NOT USE THIS FILE**

## Why Deprecated?

`bot.py` has been deprecated in favor of `main.py` for the following reasons:

1. **Duplicate Code**: bot.py reimplements all database functions that already exist in `db.py`
2. **Maintenance Burden**: Changes to DB schema require updates in TWO places
3. **Inconsistency Risk**: bot.py and main.py can diverge, causing different behavior
4. **Complexity**: OOP class-based approach is unnecessarily complex for this use case

## Use main.py Instead

```bash
python main.py
```

`main.py` uses the modular architecture:
- `game_logic.py` - Core game rules
- `db.py` - Database operations
- `image_generator.py` - Board visualization
- `main.py` - Bot orchestration

This is easier to maintain, test, and extend.

## Migration Notes

If you were using bot.py:
- All functionality exists in main.py
- Database schema is identical
- Game logic is identical (and now FIXED for ship sinking)
- Error handling is equivalent

## What Was Fixed

The ship sinking bug has been fixed in `game_logic.py` by using values 12-14 for hit ships instead of overwriting with 1, which preserves ship identity for sinking detection.

Both bot.py and main.py would have had the same bug before the fix.
