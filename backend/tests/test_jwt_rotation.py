"""
Tests for JWT key rotation functionality.
"""

import pytest
from datetime import timedelta
from app.utils.jwt_rotation import MultiKeyJWT, KeyRotationSchedule


def test_encode_decode_with_current_key():
    """Test basic encode/decode with current key."""
    jwt_manager = MultiKeyJWT(current_key="secret-123")

    payload = {"user_id": "test-user", "email": "test@example.com"}
    token = jwt_manager.encode(payload)

    decoded = jwt_manager.decode(token)

    assert decoded["user_id"] == "test-user"
    assert decoded["email"] == "test@example.com"


def test_decode_with_old_key():
    """Test decoding tokens signed with old keys."""
    old_key = "old-secret"
    new_key = "new-secret"

    # Create token with old key
    jwt_old = MultiKeyJWT(current_key=old_key)
    token = jwt_old.encode({"user_id": "test-user"})

    # Verify with new manager that has old key in list
    jwt_new = MultiKeyJWT(current_key=new_key, old_keys=[old_key])
    decoded = jwt_new.decode(token)

    assert decoded["user_id"] == "test-user"


def test_rotation():
    """Test key rotation process."""
    jwt_manager = MultiKeyJWT(current_key="key-1")

    # Rotate to new key
    jwt_manager.rotate_key("key-2")

    assert jwt_manager.current_key == "key-2"
    assert "key-1" in jwt_manager.old_keys

    # Tokens signed with key-1 still valid
    old_token = jwt.encode({"user": "test"}, "key-1", algorithm="HS256")
    decoded = jwt_manager.decode(old_token)
    assert decoded["user"] == "test"

    # New tokens signed with key-2
    new_token = jwt_manager.encode({"user": "test2"})
    decoded = jwt_manager.decode(new_token)
    assert decoded["user"] == "test2"


def test_expired_token_rejected():
    """Test that expired tokens are rejected."""
    jwt_manager = MultiKeyJWT(current_key="secret")

    # Create token that expires immediately
    token = jwt_manager.encode(
        {"user_id": "test"},
        expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(Exception):  # JWTError or ExpiredSignatureError
        jwt_manager.decode(token)


def test_invalid_signature_rejected():
    """Test that tampered tokens are rejected."""
    jwt_manager = MultiKeyJWT(current_key="secret")

    token = jwt_manager.encode({"user_id": "test"})

    # Tamper with token
    tampered = token[:-5] + "XXXXX"

    with pytest.raises(Exception):
        jwt_manager.decode(tampered)


def test_rotation_schedule():
    """Test automatic key rotation scheduling."""
    jwt_manager = MultiKeyJWT(current_key="key-1")
    schedule = KeyRotationSchedule(
        jwt_manager=jwt_manager,
        rotation_days=90,
        transition_days=7,
    )

    # Should not rotate immediately
    assert not schedule.should_rotate()

    # Simulate 91 days passing
    schedule.last_rotation = schedule.last_rotation - timedelta(days=91)
    assert schedule.should_rotate()

    # Rotate
    schedule.rotate_key("key-2")
    assert jwt_manager.current_key == "key-2"
    assert "key-1" in jwt_manager.old_keys

    # Old key should be scheduled for expiry
    assert "key-1" in schedule.old_key_expiry


def test_expired_key_cleanup():
    """Test cleanup of expired old keys."""
    jwt_manager = MultiKeyJWT(current_key="key-2", old_keys=["key-1"])
    schedule = KeyRotationSchedule(jwt_manager)

    # Add an expired key
    expired_time = datetime.now(timezone.utc) - timedelta(days=1)
    schedule.old_key_expiry["key-1"] = expired_time

    # Cleanup
    removed = schedule.cleanup_expired_keys()

    assert removed == 1
    assert "key-1" not in jwt_manager.old_keys
