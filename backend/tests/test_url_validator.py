"""
Unit tests for the URL safety validator (utils/url_validator.py).
Verifies correct detection of malformed syntax, unsupported schemes,
and loopback/private IP ranges (SSRF protection).
"""
import pytest
from unittest.mock import patch, MagicMock
import socket

from utils.url_validator import (
    validate_url_safety,
    InvalidURLException,
    UnsafeURLException,
    is_safe_ip
)


def test_valid_public_urls():
    """Verify that normal public URLs pass validation."""
    # We will patch getaddrinfo to return a safe public IP so we don't depend on actual DNS resolution in tests
    with patch("socket.getaddrinfo") as mock_resolve:
        # Resolve to a safe public IP: 8.8.8.8
        mock_resolve.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))
        ]
        
        assert validate_url_safety("https://github.com/dataset.csv") == "https://github.com/dataset.csv"
        assert validate_url_safety("http://example.com/api/v1/data") == "http://example.com/api/v1/data"
        
        mock_resolve.assert_called()


def test_invalid_and_unsupported_schemes():
    """Verify that unsupported schemes are rejected with InvalidURLException."""
    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("file:///etc/passwd")
    assert "Unsupported scheme" in str(exc.value)

    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("ftp://anonymous@ftp.example.com/data.xlsx")
    assert "Unsupported scheme" in str(exc.value)

    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("data:text/csv;base64,col1,col2")
    assert "Unsupported scheme" in str(exc.value)

    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("gopher://localhost/1")
    assert "Unsupported scheme" in str(exc.value)


def test_empty_and_malformed_urls():
    """Verify that empty or syntactically malformed URLs are rejected."""
    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("")
    assert "cannot be empty" in str(exc.value)

    with pytest.raises(InvalidURLException) as exc:
        validate_url_safety("http://")
    assert "must contain a valid hostname" in str(exc.value)


def test_unsafe_ip_checking():
    """Test individual IP categories in is_safe_ip function."""
    # Loopback
    assert not is_safe_ip("127.0.0.1")
    assert not is_safe_ip("127.0.0.2")
    assert not is_safe_ip("::1")
    
    # Private IPv4 (RFC 1918)
    assert not is_safe_ip("10.0.0.1")
    assert not is_safe_ip("172.16.50.4")
    assert not is_safe_ip("192.168.1.100")
    
    # Private IPv6
    assert not is_safe_ip("fd00::1")
    
    # Link-Local (SSRF Cloud Metadata)
    assert not is_safe_ip("169.254.169.254")
    assert not is_safe_ip("fe80::1")
    
    # Unspecified/Wildcard
    assert not is_safe_ip("0.0.0.0")
    assert not is_safe_ip("::")
    
    # Valid Public IPs
    assert is_safe_ip("8.8.8.8")
    assert is_safe_ip("140.82.121.4") # GitHub IP
    assert is_safe_ip("2001:4860:4860::8888") # Google Public DNS IPv6


def test_ssrf_resolutions_rejected():
    """Verify hostnames resolving to unsafe addresses are rejected."""
    # Scenario A: Host resolves to loopback
    with patch("socket.getaddrinfo") as mock_resolve:
        mock_resolve.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ]
        with pytest.raises(UnsafeURLException) as exc:
            validate_url_safety("https://localhost/dataset.csv")
        assert "forbidden" in str(exc.value)

    # Scenario B: Host resolves to cloud metadata endpoint
    with patch("socket.getaddrinfo") as mock_resolve:
        mock_resolve.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))
        ]
        with pytest.raises(UnsafeURLException) as exc:
            validate_url_safety("http://metadata.internal/info")
        assert "forbidden" in str(exc.value)

    # Scenario C: Host resolves to private network
    with patch("socket.getaddrinfo") as mock_resolve:
        mock_resolve.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.250.0.1", 0))
        ]
        with pytest.raises(UnsafeURLException) as exc:
            validate_url_safety("http://internal-service.local/data.json")
        assert "forbidden" in str(exc.value)


def test_failed_dns_resolution():
    """Verify hostnames failing DNS resolution are rejected gracefully."""
    with patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")):
        with pytest.raises(InvalidURLException) as exc:
            validate_url_safety("https://thisdomaindoesnotexist.invalid/data.csv")
        assert "Failed to resolve host" in str(exc.value)
