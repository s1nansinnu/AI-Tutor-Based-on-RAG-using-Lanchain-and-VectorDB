import sqlite3
from typing import List, Dict, Optional
from contextlib import contextmanager
from config import get_settings
import logging
import threading

settings = get_settings()
logger = logging.getLogger(__name__)

# Thread-local storage for connection pooling
_local = threading.local()

def get_pooled_connection():
    """Get thread-local database connection for connection pooling"""
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(
            settings.database_name,
            check_same_thread=False,
            timeout=10.0
        )
        _local.conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        _local.conn.execute("PRAGMA journal_mode=WAL")
        logger.debug("Created new database connection")
    return _local.conn

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper cleanup"""
    conn = get_pooled_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    # Note: We don't close the connection as it's pooled

def create_application_logs():
    """Create application logs table with indexes"""
    try:
        with get_db_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS application_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    gpt_response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    emotion TEXT DEFAULT 'neutral',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Create index for faster session queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON application_logs(session_id)
            ''')
            # Create index for date-based queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON application_logs(created_at)
            ''')
            logger.info("Application logs table initialized")
    except Exception as e:
        logger.error(f"Error creating application_logs table: {e}")
        raise

def insert_application_logs(
    session_id: str, 
    user_query: str, 
    gpt_response: str, 
    model: str,
    emotion: str = "neutral"
) -> bool:
    """Insert a chat log entry with error handling"""
    try:
        with get_db_connection() as conn:
            conn.execute(
                '''INSERT INTO application_logs 
                   (session_id, user_query, gpt_response, model, emotion) 
                   VALUES (?, ?, ?, ?, ?)''',
                (session_id, user_query, gpt_response, model, emotion)
            )
        return True
    except Exception as e:
        logger.error(f"Error inserting application log: {e}")
        return False

def get_chat_history(
    session_id: str, 
    limit: Optional[int] = None
) -> List[Dict[str, str]]:
    """
    Get chat history for a session.
    
    Args:
        session_id: The session identifier
        limit: Optional limit on number of messages to return (most recent)
    
    Returns:
        List of message dictionaries with 'role' and 'content'
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT user_query, gpt_response 
                FROM application_logs 
                WHERE session_id = ? 
                ORDER BY created_at DESC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
                cursor.execute(query, (session_id,))
                # Reverse to get chronological order
                rows = list(reversed(cursor.fetchall()))
            else:
                cursor.execute(query.replace('DESC', 'ASC'), (session_id,))
                rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                messages.extend([
                    {"role": "human", "content": row['user_query']},
                    {"role": "ai", "content": row['gpt_response']}
                ])
            
            return messages
            
    except Exception as e:
        logger.error(f"Error retrieving chat history for session {session_id}: {e}")
        return []

def get_session_stats(session_id: str) -> Dict:
    """Get statistics for a session"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as message_count,
                    MIN(created_at) as first_message,
                    MAX(created_at) as last_message
                FROM application_logs 
                WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            return {
                "message_count": row['message_count'],
                "first_message": row['first_message'],
                "last_message": row['last_message']
            }
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        return {}

def create_document_store():
    """Create document store table with indexes"""
    try:
        with get_db_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS document_store (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    file_hash TEXT UNIQUE,
                    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Create index for filename searches
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_filename 
                ON document_store(filename)
            ''')
            # Create index for hash-based deduplication
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_file_hash 
                ON document_store(file_hash)
            ''')
            logger.info("Document store table initialized")
    except Exception as e:
        logger.error(f"Error creating document_store table: {e}")
        raise

def insert_document_record(
    filename: str, 
    file_size: Optional[int] = None,
    file_type: Optional[str] = None,
    file_hash: Optional[str] = None
) -> int:
    """
    Insert a document record and return its ID
    
    Args:
        filename: Name of the file
        file_size: Size in bytes (optional)
        file_type: File extension/type (optional)
        file_hash: SHA256 hash for deduplication (optional)
    
    Returns:
        The auto-generated file_id
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO document_store (filename, file_size, file_type, file_hash) 
                   VALUES (?, ?, ?, ?)''',
                (filename, file_size, file_type, file_hash)
            )
            file_id = cursor.lastrowid
            logger.info(f"Inserted document record: {filename} (ID: {file_id})")
            return file_id
    except sqlite3.IntegrityError as e:
        if "file_hash" in str(e):
            logger.warning(f"Duplicate file detected: {filename}")
            raise ValueError("This file has already been uploaded")
        raise
    except Exception as e:
        logger.error(f"Error inserting document record: {e}")
        raise

def delete_document_record(file_id: int) -> bool:
    """Delete a document record by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM document_store WHERE id = ?', (file_id,))
            deleted = cursor.rowcount > 0
            
            if deleted:
                logger.info(f"Deleted document record ID: {file_id}")
            else:
                logger.warning(f"No document found with ID: {file_id}")
            
            return deleted
    except Exception as e:
        logger.error(f"Error deleting document record {file_id}: {e}")
        return False

def get_all_documents() -> List[Dict]:
    """Get all documents with their metadata"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, filename, file_size, file_type, upload_timestamp 
                FROM document_store 
                ORDER BY upload_timestamp DESC
            ''')
            documents = cursor.fetchall()
            return [dict(doc) for doc in documents]
    except Exception as e:
        logger.error(f"Error retrieving documents: {e}")
        return []

def get_document_by_id(file_id: int) -> Optional[Dict]:
    """Get a specific document by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, filename, file_size, file_type, upload_timestamp 
                   FROM document_store WHERE id = ?''',
                (file_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving document {file_id}: {e}")
        return None

def cleanup_old_logs(days: int = 30) -> int:
    """
    Clean up chat logs older than specified days
    
    Args:
        days: Number of days to keep
    
    Returns:
        Number of records deleted
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM application_logs 
                WHERE created_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old log records")
            return deleted
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {e}")
        return 0

def cleanup_expired_sessions(hours: int = None) -> int:
    """
    Remove sessions older than specified hours
    
    Args:
        hours: Number of hours to keep (uses settings.session_timeout_hours if not specified)
    
    Returns:
        Number of messages deleted
    """
    if hours is None:
        hours = settings.session_timeout_hours
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Find sessions to delete
            cursor.execute('''
                SELECT DISTINCT session_id 
                FROM application_logs 
                WHERE created_at < datetime('now', '-' || ? || ' hours')
            ''', (hours,))
            
            expired_sessions = [row['session_id'] for row in cursor.fetchall()]
            
            if not expired_sessions:
                logger.info("No expired sessions to clean up")
                return 0
            
            # Delete logs for expired sessions
            placeholders = ','.join('?' * len(expired_sessions))
            cursor.execute(
                f'DELETE FROM application_logs WHERE session_id IN ({placeholders})',
                expired_sessions
            )
            
            deleted = cursor.rowcount
            logger.info(
                f"Cleaned up {deleted} messages from {len(expired_sessions)} expired sessions"
            )
            return deleted
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        return 0

def get_database_stats() -> Dict:
    """Get overall database statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get logs count
            cursor.execute('SELECT COUNT(*) as count FROM application_logs')
            logs_count = cursor.fetchone()['count']
            
            # Get documents count
            cursor.execute('SELECT COUNT(*) as count FROM document_store')
            docs_count = cursor.fetchone()['count']
            
            # Get unique sessions
            cursor.execute('SELECT COUNT(DISTINCT session_id) as count FROM application_logs')
            sessions_count = cursor.fetchone()['count']
            
            # Get active sessions (last 24 hours)
            cursor.execute('''
                SELECT COUNT(DISTINCT session_id) as count 
                FROM application_logs 
                WHERE created_at > datetime('now', '-24 hours')
            ''')
            active_sessions = cursor.fetchone()['count']
            
            return {
                "total_messages": logs_count,
                "total_documents": docs_count,
                "unique_sessions": sessions_count,
                "active_sessions_24h": active_sessions
            }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}

def check_database_health() -> bool:
    """Check if database is accessible and functional"""
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

# Initialize database tables on module import
try:
    create_application_logs()
    create_document_store()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise