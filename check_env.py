"""Check if environment variables are set correctly"""
from dotenv import load_dotenv
import os

load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_KEY')

print("Checking environment variables...")
print(f"SUPABASE_URL: {url if url else 'NOT SET'}")
print(f"SUPABASE_KEY: {'SET' if key else 'NOT SET'} ({len(key) if key else 0} characters)")

if not url or not key:
    print("\n❌ Missing Supabase credentials!")
    print("\nPlease create a .env file with your Supabase credentials.")
    print("You can copy env_example.txt to .env and fill in the values.")
else:
    print("\n✓ Credentials are set")


