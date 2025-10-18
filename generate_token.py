#!/usr/bin/env python3
"""
JWT Token Generator for Enterprise AI Agent Framework Testing
"""

import jwt
import json
from datetime import datetime, timedelta, timezone
import sys

# Configuration (should match your API configuration)
JWT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"

def generate_test_token(user_id: str = "test-user", tenant_id: str = "tenant-1", expires_hours: int = 24):
    """Generate a test JWT token."""
    
    # Create payload
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,  # Subject (user ID)
        "tenant_id": tenant_id,  # Tenant ID for multi-tenancy
        "iat": now,  # Issued at
        "exp": now + timedelta(hours=expires_hours),  # Expiration
        "iss": "agent-framework-test"  # Issuer (removed aud to avoid validation issues)
    }
    
    # Generate token
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def test_token_verification(token):
    """Test if the token can be verified."""
    try:
        # Decode the token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        print("Token verification successful!")
        print(f"Payload: {payload}")
        
        # Check required fields
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if not user_id or not tenant_id:
            print("Token missing required fields")
            return False
            
        print(f"User ID: {user_id}")
        print(f"Tenant ID: {tenant_id}")
        return True
        
    except jwt.ExpiredSignatureError:
        print("Token has expired")
        return False
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {e}")
        return False

def main():
    """Main function to generate tokens."""
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "generate":
            user_id = sys.argv[2] if len(sys.argv) > 2 else "test-user"
            tenant_id = sys.argv[3] if len(sys.argv) > 3 else "tenant-1"
            
            token = generate_test_token(user_id, tenant_id)
            
            print("Generated JWT Token:")
            print(f"Token: {token}")
            print()
            print("Token Details:")
            print(f"User ID: {user_id}")
            print(f"Tenant ID: {tenant_id}")
            print(f"Expires: 24 hours from now")
            print()
            print("Testing token verification:")
            test_token_verification(token)
            print()
            print("Test Commands:")
            print(f'curl -X POST http://localhost:8000/v1/runs \\')
            print(f'  -H "Authorization: Bearer {token}" \\')
            print(f'  -H "Content-Type: application/json" \\')
            print(f'  -d \'{{"flow_id": "sample-flow-1", "input": {{"message": "Hello World"}}, "tenant_id": "{tenant_id}"}}\'')
            
        elif command == "decode":
            if len(sys.argv) < 3:
                print("Please provide a token to decode")
                return
                
            token = sys.argv[2]
            test_token_verification(token)
                
        elif command == "help":
            print("JWT Token Generator Help:")
            print()
            print("Commands:")
            print("  generate [user_id] [tenant_id]  - Generate a new token")
            print("  decode <token>                  - Decode and verify a token")
            print("  help                           - Show this help")
            print()
            print("Examples:")
            print("  python generate_token.py generate")
            print("  python generate_token.py generate user123 tenant456")
            print("  python generate_token.py decode eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")
            
        else:
            print(f"Unknown command: {command}")
            print("Use 'help' to see available commands")
    else:
        # Default: generate a token
        token = generate_test_token()
        print("Generated JWT Token:")
        print(f"Token: {token}")
        print()
        print("Testing token verification:")
        test_token_verification(token)
        print()
        print("Copy this token and use it in your API requests!")
        print("Test in Swagger UI:")
        print("1. Click 'Authorize' button")
        print("2. Enter: Bearer " + token)
        print("3. Click 'Authorize'")
        print("4. Now you can test the /v1/runs endpoint")

if __name__ == "__main__":
    main()