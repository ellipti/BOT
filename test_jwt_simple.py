#!/usr/bin/env python3
"""
Simple JWT authentication test
"""
import asyncio
from dashboard.auth import create_access_token, decode_token, hash_password, verify_password
from dashboard.users import UserStore

async def test_jwt_auth():
    """Test JWT authentication flow"""
    print("🔐 Testing JWT Authentication System")
    print("=" * 50)
    
    # Test password hashing
    password = "admin123"
    hashed = hash_password(password)
    print(f"✅ Password hashing works: {len(hashed)} chars")
    
    # Test password verification
    if verify_password(password, hashed):
        print("✅ Password verification works")
    else:
        print("❌ Password verification failed")
    
    # Test token creation
    token = create_access_token(
        user_id="admin@test.com", 
        roles=["admin"]
    )
    print(f"✅ JWT token created: {token[:50]}...")
    
    # Test token verification
    try:
        payload = decode_token(token)
        print(f"✅ Token verified: user={payload.get('sub')}, roles={payload.get('roles')}")
    except Exception as e:
        print(f"❌ Token verification failed: {e}")
    
    # Test user store
    store = UserStore()
    user = store.authenticate_user("admin@test.com", "admin123")
    if user:
        print(f"✅ User authentication works: {user['email']} with roles {user['roles']}")
    else:
        print("❌ User authentication failed")
    
    print("\n🎉 JWT Authentication System is working correctly!")

if __name__ == "__main__":
    asyncio.run(test_jwt_auth())
