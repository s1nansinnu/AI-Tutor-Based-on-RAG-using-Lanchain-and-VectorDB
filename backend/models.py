from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime
from typing import Optional

class ModelName(str, Enum):
    """Available AI models"""
    GEMINI_FLASH = "gemini-2.5-flash"
    GEMINI_PRO = "gemini-pro"
    
    @classmethod
    def get_default(cls):
        return cls.GEMINI_FLASH

class EmotionType(str, Enum):
    """Possible emotion types for responses"""
    HAPPY = "happy"
    EXPLAINING = "explaining"
    THINKING = "thinking"
    ENCOURAGING = "encouraging"
    NEUTRAL = "neutral"

class QueryInput(BaseModel):
    """Input model for chat queries"""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question or query"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Session identifier for maintaining conversation context"
    )
    model: ModelName = Field(
        default=ModelName.GEMINI_FLASH,
        description="AI model to use for generating response"
    )
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Validate and clean the question"""
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty or whitespace only")
        return v
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate session ID format"""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Basic validation - alphanumeric and hyphens only
            if not all(c.isalnum() or c == '-' for c in v):
                raise ValueError("Session ID can only contain alphanumeric characters and hyphens")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is machine learning?",
                "session_id": "abc-123-def",
                "model": "gemini-2.5-flash"
            }
        }

class QueryResponse(BaseModel):
    """Response model for chat queries"""
    answer: str = Field(
        ...,
        description="The AI-generated answer"
    )
    session_id: str = Field(
        ...,
        description="Session identifier for this conversation"
    )
    model: ModelName = Field(
        ...,
        description="Model used to generate the response"
    )
    emotion: str = Field(
        default="neutral",
        description="Detected emotion of the response"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Machine learning is a subset of AI...",
                "session_id": "abc-123-def",
                "model": "gemini-2.5-flash",
                "emotion": "explaining"
            }
        }

class DocumentInfo(BaseModel):
    """Information about an uploaded document"""
    id: int = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    file_type: Optional[str] = Field(None, description="File extension")
    upload_timestamp: datetime = Field(..., description="When the document was uploaded")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "filename": "machine_learning_notes.pdf",
                "file_size": 1024000,
                "file_type": ".pdf",
                "upload_timestamp": "2024-01-15T10:30:00"
            }
        }

class DocumentUploadResponse(BaseModel):
    """Response after successful document upload"""
    message: str = Field(..., description="Success message")
    file_id: int = Field(..., description="Assigned file ID")
    filename: str = Field(..., description="Sanitized filename")
    size_bytes: int = Field(..., description="File size in bytes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "File uploaded successfully",
                "file_id": 1,
                "filename": "notes.pdf",
                "size_bytes": 1024000
            }
        }

class DeleteFileRequest(BaseModel):
    """Request to delete a document"""
    file_id: int = Field(
        ...,
        gt=0,
        description="ID of the file to delete"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": 1
            }
        }

class DeleteFileResponse(BaseModel):
    """Response after file deletion"""
    message: str = Field(..., description="Deletion confirmation message")
    file_id: int = Field(..., description="ID of the deleted file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Document deleted successfully",
                "file_id": 1
            }
        }

class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    path: Optional[str] = Field(None, description="Request path that caused the error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "File too large",
                "error_code": "FILE_TOO_LARGE",
                "path": "/upload-doc"
            }
        }

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    services: dict = Field(..., description="Status of individual services")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00",
                "services": {
                    "database": "operational",
                    "vector_store": "operational",
                    "llm": "operational"
                }
            }
        }