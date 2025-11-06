"""
Utility functions for Battle Dinghy bot.

This module consolidates various utility scripts for environment checking,
database diagnostics, and connection testing.
"""

import os
from dotenv import load_dotenv
from supabase import create_client
import tweepy
import httpx


def check_environment_variables():
    """
    Check if all required environment variables are set.

    Returns:
        tuple: (success: bool, missing: list, message: str)
    """
    load_dotenv()

    required_vars = [
        'X_API_KEY',
        'X_API_SECRET',
        'X_ACCESS_TOKEN',
        'X_ACCESS_TOKEN_SECRET',
        'BEARER_TOKEN',
        'SUPABASE_URL',
        'SUPABASE_KEY'
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        message = f"[X] Missing environment variables: {', '.join(missing)}"
        return False, missing, message
    else:
        message = "[OK] All environment variables are set!"
        return True, [], message


def test_supabase_connection():
    """
    Test connection to Supabase database.

    Returns:
        tuple: (success: bool, message: str, error: Exception or None)
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        return False, "Missing Supabase credentials", None

    try:
        supabase = create_client(supabase_url, supabase_key)

        # Try to query games table
        response = supabase.table('games').select('*').limit(1).execute()

        message = f"[OK] Supabase connection successful! Found {len(response.data)} game(s)"
        return True, message, None

    except httpx.ConnectError as e:
        message = f"[X] Connection error: Could not reach Supabase server"
        return False, message, e

    except Exception as e:
        message = f"[X] Error connecting to Supabase: {str(e)}"
        return False, message, e


def test_twitter_api_connection():
    """
    Test connection to Twitter API.

    Returns:
        tuple: (success: bool, message: str, username: str or None, error: Exception or None)
    """
    load_dotenv()

    # Get credentials
    api_key = os.getenv('X_API_KEY')
    api_secret = os.getenv('X_API_SECRET')
    access_token = os.getenv('X_ACCESS_TOKEN')
    access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')
    bearer_token = os.getenv('BEARER_TOKEN')

    if not all([api_key, api_secret, access_token, access_token_secret, bearer_token]):
        return False, "Missing Twitter API credentials", None, None

    try:
        # Initialize client
        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

        # Test by getting authenticated user
        me = client.get_me()

        if me.data:
            username = me.data.username
            message = f"[OK] Twitter API connection successful! Authenticated as @{username}"
            return True, message, username, None
        else:
            message = "[X] Could not get user information"
            return False, message, None, None

    except tweepy.Unauthorized as e:
        message = "[X] Unauthorized: Check your API credentials and access level"
        return False, message, None, e

    except tweepy.Forbidden as e:
        message = "[X] Forbidden: Check API access permissions"
        return False, message, None, e

    except Exception as e:
        message = f"[X] Error connecting to Twitter API: {str(e)}"
        return False, message, None, e


def check_database_schema():
    """
    Check if the database schema is correct.

    Returns:
        tuple: (success: bool, message: str, missing_columns: list, error: Exception or None)
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        return False, "Missing Supabase credentials", [], None

    try:
        supabase = create_client(supabase_url, supabase_key)

        # Try to fetch one record to see column structure
        response = supabase.table('games').select('*').limit(1).execute()

        required_columns = [
            'id', 'game_number', 'player1_id', 'player2_id',
            'player1_board', 'player2_board', 'turn', 'thread_id'
        ]

        optional_columns = ['game_state', 'bot_post_count', 'created_at']

        if response.data and len(response.data) > 0:
            actual_columns = list(response.data[0].keys())
            missing_required = [col for col in required_columns if col not in actual_columns]
            missing_optional = [col for col in optional_columns if col not in actual_columns]

            if missing_required:
                message = f"[X] Missing required columns: {', '.join(missing_required)}"
                return False, message, missing_required, None
            elif missing_optional:
                message = f"[!] Schema OK but missing optional columns: {', '.join(missing_optional)}"
                return True, message, missing_optional, None
            else:
                message = "[OK] Database schema is correct!"
                return True, message, [], None
        else:
            message = "[!] Games table exists but is empty - cannot verify full schema"
            return True, message, [], None

    except Exception as e:
        message = f"[X] Error checking schema: {str(e)}"
        return False, message, [], e


def diagnose_setup():
    """
    Run all diagnostic checks and print a comprehensive report.

    Returns:
        bool: True if all checks pass, False otherwise
    """
    print("=" * 60)
    print("Battle Dinghy Setup Diagnostics")
    print("=" * 60)
    print()

    all_passed = True

    # Check 1: Environment Variables
    print("1. Checking environment variables...")
    success, missing, message = check_environment_variables()
    print(f"   {message}")
    if not success:
        print(f"   Missing: {missing}")
        all_passed = False
    print()

    # Check 2: Twitter API
    print("2. Testing Twitter API connection...")
    success, message, username, error = test_twitter_api_connection()
    print(f"   {message}")
    if error:
        print(f"   Error details: {error}")
        all_passed = False
    print()

    # Check 3: Supabase
    print("3. Testing Supabase connection...")
    success, message, error = test_supabase_connection()
    print(f"   {message}")
    if error:
        print(f"   Error details: {error}")
        all_passed = False
    print()

    # Check 4: Database Schema
    print("4. Checking database schema...")
    success, message, missing, error = check_database_schema()
    print(f"   {message}")
    if error:
        print(f"   Error details: {error}")
        all_passed = False
    print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("[OK] All checks passed! Bot is ready to run.")
    else:
        print("[X] Some checks failed. Please fix the issues above.")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    # Run diagnostics when executed directly
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "env":
            success, missing, message = check_environment_variables()
            print(message)
            sys.exit(0 if success else 1)

        elif command == "twitter":
            success, message, username, error = test_twitter_api_connection()
            print(message)
            if error:
                print(f"Error: {error}")
            sys.exit(0 if success else 1)

        elif command == "supabase":
            success, message, error = test_supabase_connection()
            print(message)
            if error:
                print(f"Error: {error}")
            sys.exit(0 if success else 1)

        elif command == "schema":
            success, message, missing, error = check_database_schema()
            print(message)
            if error:
                print(f"Error: {error}")
            sys.exit(0 if success else 1)

        elif command == "all":
            success = diagnose_setup()
            sys.exit(0 if success else 1)

        else:
            print(f"Unknown command: {command}")
            print("Usage: python utils.py [env|twitter|supabase|schema|all]")
            sys.exit(1)
    else:
        # No arguments - run all diagnostics
        success = diagnose_setup()
        sys.exit(0 if success else 1)
