#!/usr/bin/env python3
"""
Test JWT Token Verification
"""

import jwt
from datetime import datetime, timedelta, timezone

# Configuration
JWT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

# Test token from previous generation
test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJ0ZW5hbnRfaWQiOiJ0ZW5hbnQtMSIsImlhdCI6MTc2MDgyODk0NCwiZXhwIjoxNzYwOTE1MzQ0LCJpc3MiOiJhZ2VudC1mcmFtZXdvcmstdGVzdCIsImF1ZCI6ImFnZW50LWZyYW1ld29yay1hcGkifQ.n3sjQWN40Errys-zH7fGggr5D3Fj2Gxe0OSlTyF7rns"

def test_token_verification():
    """Test if the token can be verified."""
    try:
        # Decode the token
        payload = jwt.decode(test_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        print("✅ Token verification successful!")
        print(f"Payload: {payload}")
        
        # Check required fields
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if not user_id or not tenant_id:
            print("❌ Token missing required fields")
            return False
            
        print(f"✅ User ID: {user_id}")
        print(f"✅ Tenant ID: {tenant_id}")
        return True
        
    except jwt.ExpiredSignatureError:
        print("❌ Token has expired")
        return False
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid token: {e}")
        return False

def generate_new_token():
    """Generate a fresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "test-user",
        "tenant_id": "tenant-1", 
        "iat": now,
        "exp": now + timedelta(hours=24),
        "iss": "agent-framework-test",
        "aud": "agent-framework-api"
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    print(f"🆕 New token: {token}")
    return token

if __name__ == "__main__":
    print("Testing JWT Token Verification...")
    print()
    
    # Test existing token
    print("Testing existing token:")
    if not test_token_verification():
        print()
        print("Generating new token:")
        new_token = generate_new_token()
        print()
        print("Testing new token:")
        # Test the new token
        try:
            payload = jwt.decode(new_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            print("✅ New token verification successful!")
            print(f"Payload: {payload}")
        except Exception as e:
            print(f"❌ New token verification failed: {e}")
