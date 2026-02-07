from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest
from langchain_utils import get_rag_chain, parse_llm_response
from db_utils import (
    insert_application_logs, get_chat_history, get_all_documents, 
    insert_document_record, delete_document_record, get_database_stats,
    cleanup_expired_sessions, check_database_health
)
from chroma_utils import (
    index_document_to_chroma, delete_doc_from_chroma, 
    get_vectorstore_stats, check_vectorstore_health
)
from file_utils import (
    sanitize_filename, validate_file_extension, validate_file_content,
    validate_file_size, calculate_file_hash
)
from config import get_settings
from datetime import datetime, timedelta
from google.api_core.exceptions import ResourceExhausted
from pathlib import Path
import pytz
import uuid
import logging
import tempfile
import os
from typing import List
import threading

# Initialize settings
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="AI Tutor API",
    description="Document-based AI Tutor with integrated emotion detection",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.rate_limit_storage_url
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add to logging context
    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Create upload directory if it doesn't exist
Path(settings.upload_dir).mkdir(exist_ok=True)

# Metrics (simple counters)
class Metrics:
    def __init__(self):
        self.chat_requests = 0
        self.chat_errors = 0
        self.upload_requests = 0
        self.upload_errors = 0
        self._lock = threading.Lock()
    
    def increment(self, metric: str):
        with self._lock:
            setattr(self, metric, getattr(self, metric) + 1)
    
    def get_all(self):
        with self._lock:
            return {
                "chat_requests": self.chat_requests,
                "chat_errors": self.chat_errors,
                "upload_requests": self.upload_requests,
                "upload_errors": self.upload_errors
            }

metrics = Metrics()

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "message": "AI Tutor API is running",
        "version": "2.0.0",
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    """Detailed health check with dependency validation"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database
    try:
        if check_database_health():
            health_status["services"]["database"] = "operational"
        else:
            health_status["services"]["database"] = "degraded"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check vector store
    try:
        if check_vectorstore_health():
            health_status["services"]["vector_store"] = "operational"
        else:
            health_status["services"]["vector_store"] = "degraded"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["vector_store"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check LLM connectivity (lightweight check)
    try:
        # Note: Full LLM check is expensive, so we just verify credentials exist
        if settings.google_api_key:
            health_status["services"]["llm"] = "operational"
        else:
            health_status["services"]["llm"] = "missing_api_key"
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["services"]["llm"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status

@app.get("/metrics")
def get_metrics():
    """Get application metrics"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics.get_all(),
        "database": get_database_stats(),
        "vector_store": get_vectorstore_stats()
    }

def get_seconds_until_reset():
    """Calculate seconds until midnight Pacific Time (when Gemini quota resets)"""
    pacific = pytz.timezone('US/Pacific')
    now = datetime.now(pacific)
    tomorrow_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    remaining = tomorrow_midnight - now
    return int(remaining.total_seconds())

@app.post("/chat", response_model=QueryResponse)
@limiter.limit(f"{settings.requests_per_minute}/minute")
def chat(request: Request, query_input: QueryInput):
    """
    Process a chat query with context from uploaded documents.
    Returns answer and emotion in a single API call.
    """
    metrics.increment("chat_requests")
    session_id = query_input.session_id or str(uuid.uuid4())
    
    logger.info(
        f"Session: {session_id} | Query: {query_input.question[:100]}... | "
        f"Model: {query_input.model.value} | Request ID: {request.state.request_id}"
    )
    
    try:
        # Validate query length
        if len(query_input.question) > settings.max_query_length:
            raise HTTPException(
                status_code=400,
                detail=f"Query too long. Max {settings.max_query_length} characters."
            )
        
        # Get chat history (limited to recent messages)
        chat_history = get_chat_history(session_id, limit=settings.max_chat_history)
        
        # Get RAG chain (returns both answer and emotion)
        rag_chain = get_rag_chain(query_input.model.value)
        
        # Single API call that returns both answer and emotion!
        result = rag_chain.invoke({
            "input": query_input.question,
            "chat_history": chat_history
        })
        
        answer_text = result['answer']
        parsed = parse_llm_response(answer_text)
        answer = parsed['answer']
        emotion = parsed['emotion']
        
        logger.info(
            f"Session: {session_id} | Response length: {len(answer)} | "
            f"Emotion: {emotion} | Request ID: {request.state.request_id}"
        )
        
        # Save to database (including emotion)
        insert_application_logs(
            session_id, 
            query_input.question, 
            answer, 
            query_input.model.value,
            emotion
        )
        
        return QueryResponse(
            answer=answer,
            session_id=session_id,
            model=query_input.model,
            emotion=emotion
        )
        
    except ResourceExhausted as e:
        # Caught the Google API ResourceExhausted exception
        retry_seconds = get_seconds_until_reset()  # ✅ Seconds until midnight Pacific Time
        logger.error(f"Quota exceeded (ResourceExhausted). Quota resets in {retry_seconds} seconds")
        logger.error(f"Error details: {str(e)}")
        metrics.increment("chat_errors")
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Daily API limit reached. Quota resets at midnight Pacific Time.",
                "retry_after_seconds": retry_seconds
            }
        )
    except Exception as e:
        # ✅ CHECK FOR QUOTA ERRORS IN STRING
        error_str = str(e)
        
        # Check for quota-related errors from LangChain/Gemini
        if ('RESOURCE_EXHAUSTED' in error_str or 
            'quota' in error_str.lower() or 
            '429' in error_str):
            
            # ✅ USE get_seconds_until_reset() - Returns seconds until midnight Pacific Time
            # This is when Gemini's daily quota resets, NOT the short retry delay
            retry_seconds = get_seconds_until_reset()
            
            logger.error(f"Quota error detected ({type(e).__name__})")
            logger.info(f"Gemini quota resets at midnight PT. Seconds remaining: {retry_seconds}")
            metrics.increment("chat_errors")
            
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Daily API limit reached. Quota resets at midnight Pacific Time.",
                    "retry_after_seconds": retry_seconds
                }
            )
        
        # Check if it's already an HTTPException (don't wrap it)
        if isinstance(e, HTTPException):
            metrics.increment("chat_errors")
            raise
        
        # Generic error - all other exceptions
        logger.error(
            f"Error in chat endpoint: {str(e)} | Request ID: {request.state.request_id}", 
            exc_info=True
        )
        metrics.increment("chat_errors")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request. Please try again."
        )

@app.post("/upload-doc")
@limiter.limit(f"{settings.requests_per_minute}/minute")
def upload_and_index_document(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Upload and index a document for RAG.
    Supports PDF, DOCX, and HTML formats with security validation.
    """
    metrics.increment("upload_requests")
    
    # Validate file extension
    if not validate_file_extension(file.filename, settings.allowed_extensions):
        file_extension = Path(file.filename).suffix.lower()
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_extension}'. "
                   f"Allowed: {', '.join(settings.allowed_extensions)}"
        )
    
    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Read file content and check size
    contents = file.file.read()
    
    if not validate_file_size(len(contents), settings.max_file_size_mb):
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_file_size_mb}MB"
        )
    
    # Create a secure temporary file
    temp_file = None
    try:
        file_extension = Path(file.filename).suffix.lower()
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension,
            dir=settings.upload_dir
        )
        temp_file.write(contents)
        temp_file.close()
        
        temp_file_path = temp_file.name
        
        # Validate file content matches extension (if enabled)
        if settings.enable_file_content_validation:
            if not validate_file_content(temp_file_path, file_extension):
                raise HTTPException(
                    status_code=400,
                    detail=f"File content does not match extension {file_extension}"
                )
        
        # Calculate file hash for deduplication
        file_hash = calculate_file_hash(temp_file_path)
        
        logger.info(
            f"Processing file: {safe_filename} ({len(contents)} bytes) | "
            f"Hash: {file_hash[:16]}... | Request ID: {request.state.request_id}"
        )
        
        # Insert document record (will fail if hash already exists)
        try:
            file_id = insert_document_record(
                safe_filename, 
                len(contents), 
                file_extension,
                file_hash
            )
        except ValueError as e:
            # Duplicate file detected
            raise HTTPException(
                status_code=409,
                detail=str(e)
            )
        
        # Index document
        success = index_document_to_chroma(temp_file_path, file_id)
        
        if success:
            logger.info(
                f"Successfully indexed document: {safe_filename} (ID: {file_id}) | "
                f"Request ID: {request.state.request_id}"
            )
            return {
                "message": f"File '{safe_filename}' uploaded and indexed successfully",
                "file_id": file_id,
                "filename": safe_filename,
                "size_bytes": len(contents)
            }
        else:
            # Rollback database entry if indexing fails
            delete_document_record(file_id)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to index '{safe_filename}'. Please try again."
            )
            
    except HTTPException:
        metrics.increment("upload_errors")
        raise
    except Exception as e:
        logger.error(
            f"Error uploading document: {str(e)} | Request ID: {request.state.request_id}", 
            exc_info=True
        )
        metrics.increment("upload_errors")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while uploading the document"
        )
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
                logger.debug(f"Cleaned up temp file: {temp_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")

@app.get("/list-docs", response_model=List[DocumentInfo])
def list_documents():
    """List all uploaded documents"""
    try:
        documents = get_all_documents()
        logger.info(f"Retrieved {len(documents)} documents")
        return documents
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve documents"
        )

@app.post("/delete-doc")
def delete_document(request: Request, delete_request: DeleteFileRequest):
    """Delete a document from both vector store and database"""
    try:
        logger.info(
            f"Deleting document with ID: {delete_request.file_id} | "
            f"Request ID: {request.state.request_id}"
        )
        
        # Delete from Chroma
        chroma_success = delete_doc_from_chroma(delete_request.file_id)
        
        if not chroma_success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete document (ID: {delete_request.file_id}) from vector store"
            )
        
        # Delete from database
        db_success = delete_document_record(delete_request.file_id)
        
        if not db_success:
            logger.warning(
                f"Deleted from Chroma but failed to delete from DB: {delete_request.file_id}"
            )
            raise HTTPException(
                status_code=500,
                detail="Document removed from vector store but database cleanup failed"
            )
        
        logger.info(f"Successfully deleted document ID: {delete_request.file_id}")
        return {
            "message": f"Document (ID: {delete_request.file_id}) deleted successfully",
            "file_id": delete_request.file_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while deleting the document"
        )

@app.get("/api-stats")
def get_api_stats():
    """
    Get API usage statistics showing optimization savings.
    """
    try:
        stats = get_database_stats()
        total_messages = stats.get("total_messages", 0)
        
        # Calculate savings
        old_calls = total_messages * 4  # Old: embedding + reformulation + answer + emotion
        new_calls = total_messages * 3  # New: embedding + reformulation + answer_with_emotion
        calls_saved = old_calls - new_calls
        
        return {
            "total_chat_messages": total_messages,
            "api_calls_with_old_method": old_calls,
            "api_calls_with_optimization": new_calls,
            "calls_saved": calls_saved,
            "cost_reduction_percentage": 25,
            "documents_indexed": stats.get("total_documents", 0),
            "unique_sessions": stats.get("unique_sessions", 0),
            "active_sessions_24h": stats.get("active_sessions_24h", 0)
        }
    except Exception as e:
        logger.error(f"Error getting API stats: {e}")
        return {"error": str(e)}

@app.post("/admin/cleanup-sessions")
def cleanup_sessions(hours: int = None):
    """
    Admin endpoint to clean up expired sessions.
    Requires authentication in production.
    """
    try:
        deleted = cleanup_expired_sessions(hours)
        return {
            "message": f"Cleaned up {deleted} messages from expired sessions",
            "deleted_count": deleted
        }
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cleanup sessions"
        )

# Global exception handler
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc  
    logger.error(
        f"Unhandled exception: {str(exc)} | Path: {request.url.path} | "
        f"Request ID: {getattr(request.state, 'request_id', 'unknown')}", 
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "path": str(request.url.path),
            "request_id": getattr(request.state, 'request_id', None)
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("AI Tutor API Starting Up")
    logger.info(f"Version: 2.0.0")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Rate Limiting: {'Enabled' if settings.enable_rate_limiting else 'Disabled'}")
    logger.info(f"Allowed Origins: {settings.allowed_origins}")
    logger.info("=" * 60)

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AI Tutor API Shutting Down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_config=None  # Use our custom logging config
    )