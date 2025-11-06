import tweepy

# Your app's keys have been added below.
consumer_key = 'ZyZOX1rcscqf2WaugUAwnNjxi'
consumer_secret = 'y94ef817ULe1zDcreuifuYoMbIGCisLZni8r5rvMvyaM2dUdjk'

# --- Do not edit below this line ---

try:
    # Set up OAuth handler for PIN-based flow by adding callback="oob"
    auth = tweepy.OAuth1UserHandler(
        consumer_key, consumer_secret, callback="oob"
    )

    # Get the authorization URL
    authorization_url = auth.get_authorization_url(signin_with_twitter=True)

    # Print the URL and instructions
    print("--- Step 1: Authorize Your Bot ---")
    print("Open this URL in a browser where you are logged in as @battle_dinghy:")
    print(authorization_url)
    print("------------------------------------")

    # After authorizing, the user will get a PIN
    verifier = input("Enter the 7-digit PIN from the browser here: ")

    # Exchange the PIN for the access tokens
    access_token, access_token_secret = auth.get_access_token(verifier)

    # Output the final tokens
    print("\n--- Success! Here are the tokens for @battle_dinghy ---")
    print("Access Token:", access_token)
    print("Access Token Secret:", access_token_secret)
    print("--------------------------------------------------")
    
    # Final test step - verify the tokens work
    print("\n--- Step 2: Testing the Generated Tokens ---")
    try:
        # Create a new tweepy client with all four credentials
        test_client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True
        )
        
        # Make a test API call
        me = test_client.get_me()
        
        if me.data:
            print(f"✅ Final Test Successful! These keys are valid.")
            print(f"✅ Authenticated as: @{me.data.username}")
            print(f"✅ User ID: {me.data.id}")
            print("--------------------------------------------------")
            print("Copy these two values into your .env file for the main bot:")
            print(f"X_ACCESS_TOKEN={access_token}")
            print(f"X_ACCESS_TOKEN_SECRET={access_token_secret}")
        else:
            print("❌ Test failed: Could not retrieve user information")
            
    except Exception as test_error:
        print(f"❌ Final Test Failed: {test_error}")
        print("The tokens were generated but may not have the right permissions.")
        print("Please check your app settings in the Developer Portal.")

except Exception as e:
    print(f"\nAn error occurred: {e}")
    print("Please check that your consumer_key and consumer_secret are correct.")