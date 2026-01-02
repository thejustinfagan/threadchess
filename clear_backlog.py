"""
Script to mark backlogged challenge tweets as processed.
This prevents the bot from reprocessing old challenges that caused rate limit issues.
"""

from db import mark_tweet_processed

# Tweet IDs from the logs that caused the rate limit loop
backlogged_tweets = [
    "2006948808564027683",
    "2006940923268313164",
    "2006938430828351697",
    "2006936760199389589",
    "2006936710815559813",
    "2006932268573667540",
    "2006929287564374392",
    "2006778287796924842",
    "2006740815440392567",
    "2006734947541987550",
    "2006951645247340930",
]

if __name__ == "__main__":
    print("Marking backlogged tweets as processed...")

    for tweet_id in backlogged_tweets:
        mark_tweet_processed(tweet_id)
        print(f"  Marked {tweet_id} as processed")

    print(f"\n✓ Marked {len(backlogged_tweets)} tweets as processed")
    print("The bot will now skip these tweets on next poll cycle.")
