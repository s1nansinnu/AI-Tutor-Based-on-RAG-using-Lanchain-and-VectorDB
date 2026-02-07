"""File validation and security utilities"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of a file for deduplication.
    
    Args:
        file_path: Path to the file
    
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        raise

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystem
    """
    # Get just the filename, no path components
    filename = Path(filename).name
    
    # Allowed characters: alphanumeric, dash, underscore, period
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    
    # Replace unsafe characters with underscore
    sanitized = ''.join(c if c in safe_chars else '_' for c in filename)
    
    # Ensure filename isn't empty after sanitization
    if not sanitized or sanitized == '.':
        sanitized = 'unnamed_file'
    
    # Prevent hidden files
    if sanitized.startswith('.'):
        sanitized = 'file_' + sanitized[1:]
    
    return sanitized

def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
    """
    Validate file has an allowed extension.
    
    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.docx'])
    
    Returns:
        True if extension is allowed, False otherwise
    """
    file_extension = Path(filename).suffix.lower()
    return file_extension in allowed_extensions

def validate_file_content(file_path: str, expected_extension: str) -> bool:
    """
    Validate file content matches declared type using magic numbers.
    Note: Requires python-magic library. If not available, returns True.
    
    Args:
        file_path: Path to the file
        expected_extension: Expected file extension
    
    Returns:
        True if content matches extension, False otherwise
    """
    try:
        import magic
        
        mime = magic.from_file(file_path, mime=True)
        
        # Map extensions to expected MIME types
        valid_mimes = {
            '.pdf': ['application/pdf'],
            '.docx': [
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/zip'  # DOCX files are ZIP archives
            ],
            '.html': ['text/html', 'application/xhtml+xml']
        }
        
        expected_mimes = valid_mimes.get(expected_extension.lower(), [])
        
        if not expected_mimes:
            logger.warning(f"No MIME validation available for extension: {expected_extension}")
            return True
        
        is_valid = mime in expected_mimes
        
        if not is_valid:
            logger.warning(
                f"File content mismatch: expected {expected_mimes}, got {mime}"
            )
        
        return is_valid
        
    except ImportError:
        logger.info("python-magic not available, skipping content validation")
        return True
    except Exception as e:
        logger.error(f"Error validating file content: {e}")
        # On error, allow the file (fail open)
        return True

def validate_file_size(file_size: int, max_size_mb: int) -> bool:
    """
    Validate file size is within limits.
    
    Args:
        file_size: Size in bytes
        max_size_mb: Maximum allowed size in megabytes
    
    Returns:
        True if within limits, False otherwise
    """
    max_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_bytes