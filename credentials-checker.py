#!/usr/bin/env python
"""
Simple script to check if Google OAuth credentials are properly loaded
"""
import json
import os

def check_credentials():
    # Try environment variables first
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    
    if client_id and client_secret:
        print("✅ Found Google OAuth credentials in environment variables")
        print(f"Client ID: {client_id[:5]}...{client_id[-5:]}")
        print(f"Client Secret: {'*' * 10}")
        return True
    
    # Try credentials file as fallback
    try:
        with open('google_credentials.json', 'r') as f:
            creds = json.load(f)
            file_id = creds.get('client_id')
            file_secret = creds.get('client_secret')
            
            if file_id and file_secret:
                print("✅ Found Google OAuth credentials in google_credentials.json")
                print(f"Client ID: {file_id[:5]}...{file_id[-5:]}")
                print(f"Client Secret: {'*' * 10}")
                return True
            else:
                print("❌ google_credentials.json exists but is missing required fields")
                print("Make sure it contains 'client_id' and 'client_secret' fields")
                return False
    except FileNotFoundError:
        print("❌ google_credentials.json file not found")
        return False
    except json.JSONDecodeError:
        print("❌ google_credentials.json contains invalid JSON")
        return False

if __name__ == "__main__":
    print("Google OAuth Credentials Check")
    print("------------------------------")
    if not check_credentials():
        print("\nYou need to either:")
        print("1. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables")
        print("2. Create a google_credentials.json file with this format:")
        print("""{
  "client_id": "YOUR_GOOGLE_CLIENT_ID",
  "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
}""")
    else:
        print("\nCredentials look good! If you're still having issues:")
        print("1. Make sure the Client ID and Secret are correct")
        print("2. Verify that you've set up the correct redirect URIs in Google Developer Console")
        print("   - For local testing: http://localhost:5001/auth/callback")
