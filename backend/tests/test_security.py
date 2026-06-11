"""
Unit tests for the security module — password hashing + JWT.
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_token_subject,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hashed_password_is_different_from_plain(self):
        plain = "SecurePass123"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        plain = "MyPassword42!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        # bcrypt uses a random salt — hashes must never be identical
        p = "SamePassword"
        assert hash_password(p) != hash_password(p)

    def test_empty_password_hashes_without_error(self):
        # Edge case — application layer validates length, not bcrypt
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestJWT:
    def test_token_round_trip(self):
        subject = "user-uuid-1234"
        token = create_access_token(subject=subject)
        assert decode_token_subject(token) == subject

    def test_expired_token_returns_none(self):
        token = create_access_token(subject="user-1", expires_delta=timedelta(seconds=-1))
        assert decode_token_subject(token) is None

    def test_invalid_token_returns_none(self):
        assert decode_token_subject("this.is.not.a.jwt") is None

    def test_empty_token_returns_none(self):
        assert decode_token_subject("") is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(subject="user-1")
        tampered = token[:-5] + "XXXXX"
        assert decode_token_subject(tampered) is None

    def test_custom_expiry_respected(self):
        # Token valid for 1 hour should return subject immediately
        token = create_access_token(subject="user-2", expires_delta=timedelta(hours=1))
        assert decode_token_subject(token) == "user-2"

    def test_different_subjects_produce_different_tokens(self):
        t1 = create_access_token(subject="user-a")
        t2 = create_access_token(subject="user-b")
        assert t1 != t2
        assert decode_token_subject(t1) == "user-a"
        assert decode_token_subject(t2) == "user-b"
