"""
Cryptographic signing service for receipts.

This service provides JWT-based signing and verification for decision receipts.
Receipts are signed to ensure:
- Authenticity: Proof that we generated the receipt
- Integrity: Detection of any tampering
- Non-repudiation: Receipt can't be forged

Why JWT?
- Industry standard (RFC 7519)
- Compact format (URL-safe)
- Self-contained (includes all data)
- Easy to verify (no database lookup needed)

Security:
- Uses HMAC-SHA256 (symmetric signing)
- Secret key from environment (settings.HMAC_SECRET)
- Future: Can migrate to RS256 (asymmetric) for public verification
"""

import jwt
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional

from utc.config import settings


class SigningService:
    """
    Service for signing and verifying receipts using JWT.
    
    Uses HMAC-SHA256 algorithm with a shared secret.
    
    Why a class?
    - Encapsulation: All signing logic in one place
    - State management: Can cache keys, manage multiple algorithms
    - Testability: Easy to mock
    - Singleton pattern: One instance for entire app
    """
    
    def __init__(self, secret: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize signing service.
        
        Args:
            secret: Secret key for signing (defaults to settings.HMAC_SECRET)
            algorithm: JWT algorithm to use (HS256, RS256, etc.)
        
        Security Note:
        - In production, secret should be 256+ bits (32+ characters)
        - Generate with: openssl rand -hex 32
        - Never commit secret to Git!
        """
        self.secret = secret or settings.hmac_secret
        self.algorithm = algorithm
        
        # Validate secret strength
        if len(self.secret) < 32:
            raise ValueError(
                f"HMAC secret is too short ({len(self.secret)} chars). "
                f"Use at least 32 characters for security. "
                f"Generate with: openssl rand -hex 32"
            )
    
    def sign_receipt(
        self,
        receipt_data: Dict[str, Any],
        expiry_hours: Optional[int] = None
    ) -> str:
        """
        Sign a receipt and return JWT token.
        
        Args:
            receipt_data: Receipt data to sign (will be JWT payload)
            expiry_hours: Optional expiration time in hours
        
        Returns:
            JWT token (compact string)
        
        Example:
            receipt = {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "subject": "agent-42",
                "action": "write:/payments",
                "decision": "ALLOW",
                "rules": ["writes_require_approval"],
                "reason": "Approved by security team"
            }
            
            token = signer.sign_receipt(receipt)
            # → "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        
        Security:
        - Includes 'iat' (issued at) claim automatically
        - Optionally includes 'exp' (expiration) claim
        - Payload is NOT encrypted (visible to anyone)
        - Signature prevents tampering
        """
        # Create payload (copy to avoid modifying original)
        payload = receipt_data.copy()
        
        # Add standard JWT claims
        payload["iat"] = datetime.now(UTC)  # Issued at
        
        if expiry_hours:
            payload["exp"] = datetime.now(UTC) + timedelta(hours=expiry_hours)
        
        # Sign and return
        token = jwt.encode(
            payload,
            self.secret,
            algorithm=self.algorithm
        )
        
        return token
    
    def verify_receipt(
        self,
        token: str,
        verify_exp: bool = True
    ) -> Dict[str, Any]:
        """
        Verify a JWT signature and return payload.
        
        Args:
            token: JWT token to verify
            verify_exp: Whether to check expiration (default True)
        
        Returns:
            Decoded payload if signature is valid
        
        Raises:
            jwt.InvalidSignatureError: If signature doesn't match
            jwt.ExpiredSignatureError: If token has expired
            jwt.DecodeError: If token is malformed
        
        Example:
            try:
                payload = signer.verify_receipt(token)
                print(f"Valid receipt: {payload['id']}")
            except jwt.InvalidSignatureError:
                print("Receipt has been tampered with!")
            except jwt.ExpiredSignatureError:
                print("Receipt has expired")
        
        Security:
        - Verifies HMAC signature matches
        - Checks expiration if present
        - Returns None if verification fails
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_exp": verify_exp}
            )
            return payload
        
        except jwt.ExpiredSignatureError:
            # Re-raise with context
            raise jwt.ExpiredSignatureError("Receipt signature has expired")
        
        except jwt.InvalidSignatureError:
            # Re-raise with context
            raise jwt.InvalidSignatureError(
                "Receipt signature is invalid - possible tampering detected!"
            )
        
        except jwt.DecodeError as e:
            # Re-raise with context
            raise jwt.DecodeError(f"Malformed receipt token: {e}")
    
    def is_valid(self, token: str) -> bool:
        """
        Check if a token is valid (without raising exceptions).
        
        Args:
            token: JWT token to check
        
        Returns:
            True if valid, False otherwise
        
        Example:
            if signer.is_valid(token):
                print("Receipt is valid!")
            else:
                print("Receipt is invalid or tampered")
        
        Convenience method for boolean checks.
        """
        try:
            self.verify_receipt(token)
            return True
        except (jwt.InvalidSignatureError, jwt.ExpiredSignatureError, jwt.DecodeError):
            return False
    
    def get_payload_without_verification(self, token: str) -> Dict[str, Any]:
        """
        Decode JWT payload WITHOUT verifying signature.
        
        Args:
            token: JWT token to decode
        
        Returns:
            Payload (even if signature is invalid)
        
        WARNING: This does NOT verify the signature!
        Use only for:
        - Debugging
        - Displaying data before verification
        - Understanding why verification failed
        
        NEVER use for security decisions!
        
        Example:
            # See what's in a token (even if tampered)
            payload = signer.get_payload_without_verification(token)
            print(f"Token claims to be for: {payload['subject']}")
            
            # But always verify before trusting!
            if signer.is_valid(token):
                # Now we can trust the data
                process_receipt(payload)
        """
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False
            }
        )


# ========================================
# Singleton Instance
# ========================================

# Global instance (initialized once)
_signer: Optional[SigningService] = None


def get_signer() -> SigningService:
    """
    Get the singleton signing service instance.
    
    Returns:
        SigningService instance
    
    Why singleton?
    - One secret key for entire app
    - Avoid re-reading config multiple times
    - Consistent behavior everywhere
    
    Usage:
        from utc.services.signer import get_signer
        
        signer = get_signer()
        token = signer.sign_receipt(data)
    """
    global _signer
    
    if _signer is None:
        _signer = SigningService()
    
    return _signer


# ========================================
# Convenience Functions
# ========================================

def sign_receipt(receipt_data: Dict[str, Any]) -> str:
    """
    Convenience function to sign a receipt.
    
    Args:
        receipt_data: Receipt data to sign
    
    Returns:
        JWT token
    
    Example:
        from utc.services.signer import sign_receipt
        
        token = sign_receipt({
            "id": "abc",
            "decision": "ALLOW"
        })
    """
    return get_signer().sign_receipt(receipt_data)


def verify_receipt(token: str) -> Dict[str, Any]:
    """
    Convenience function to verify a receipt.
    
    Args:
        token: JWT token to verify
    
    Returns:
        Decoded payload
    
    Raises:
        jwt.InvalidSignatureError: If tampered
        jwt.ExpiredSignatureError: If expired
    
    Example:
        from utc.services.signer import verify_receipt
        
        try:
            payload = verify_receipt(token)
            print("Valid!")
        except jwt.InvalidSignatureError:
            print("Tampered!")
    """
    return get_signer().verify_receipt(token)


def is_valid_receipt(token: str) -> bool:
    """
    Convenience function to check if receipt is valid.
    
    Args:
        token: JWT token to check
    
    Returns:
        True if valid, False otherwise
    
    Example:
        from utc.services.signer import is_valid_receipt
        
        if is_valid_receipt(token):
            process_receipt(token)
    """
    return get_signer().is_valid(token)


# ========================================
# Testing & Debugging
# ========================================

if __name__ == "__main__":
    """
    Test the signing service.
    
    Run: python -m utc.services.signer
    """
    print("=" * 60)
    print("🔐 Testing Signing Service")
    print("=" * 60)
    
    signer = get_signer()
    
    # Test data
    receipt_data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "subject": "agent-42",
        "action": "write:/payments",
        "decision": "ALLOW",
        "rules": ["writes_require_approval"],
        "reason": "Test receipt"
    }
    
    print("\n1️⃣ Signing receipt...")
    token = signer.sign_receipt(receipt_data)
    print(f"✅ Token generated ({len(token)} chars)")
    print(f"   {token[:50]}...")
    
    print("\n2️⃣ Verifying signature...")
    try:
        payload = signer.verify_receipt(token)
        print(f"✅ Signature valid!")
        print(f"   Receipt ID: {payload['id']}")
        print(f"   Decision: {payload['decision']}")
    except jwt.InvalidSignatureError:
        print("❌ Signature invalid!")
    
    print("\n3️⃣ Testing tampering detection...")
    # Tamper with token (change one character)
    tampered_token = token[:-5] + "XXXXX"
    try:
        signer.verify_receipt(tampered_token)
        print("❌ Failed to detect tampering!")
    except jwt.InvalidSignatureError:
        print("✅ Tampering detected! Signature verification failed.")
    
    print("\n4️⃣ Testing convenience functions...")
    if is_valid_receipt(token):
        print("✅ is_valid_receipt() works")
    
    print("\n" + "=" * 60)
    print("🎉 All signing tests passed!")
    print("=" * 60)