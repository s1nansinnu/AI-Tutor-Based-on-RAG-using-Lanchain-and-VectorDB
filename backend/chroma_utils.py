from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredHTMLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from typing import List, Optional
from langchain_core.documents import Document
from config import get_settings
import logging
import threading

settings = get_settings()
logger = logging.getLogger(__name__)
_vectorstore_lock = threading.Lock()

# Initialize text splitter with configurable settings
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    length_function=len,
    separators=["\n\n", "\n", " ", ""]
)

# Initialize embedding function
try:
    embedding_function = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-001",
        google_api_key=settings.google_api_key
    )
    logger.info("Embedding function initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize embedding function: {e}")
    raise

# Initialize vector store
try:
    vectorstore = Chroma(
        persist_directory=settings.chroma_persist_dir,
        embedding_function=embedding_function
    )
    logger.info(f"Vector store initialized at {settings.chroma_persist_dir}")
except Exception as e:
    logger.error(f"Failed to initialize vector store: {e}")
    raise

def load_and_split_document(file_path: str) -> List[Document]:
    """
    Load a document and split it into chunks.
    
    Args:
        file_path: Path to the document file
    
    Returns:
        List of document chunks
    
    Raises:
        ValueError: If file type is unsupported
        Exception: If loading or splitting fails
    """
    try:
        # Determine file type and select appropriate loader
        if file_path.lower().endswith('.pdf'):
            loader = PyPDFLoader(file_path)
            logger.info(f"Loading PDF: {file_path}")
        elif file_path.lower().endswith('.docx'):
            loader = Docx2txtLoader(file_path)
            logger.info(f"Loading DOCX: {file_path}")
        elif file_path.lower().endswith('.html'):
            loader = UnstructuredHTMLLoader(file_path)
            logger.info(f"Loading HTML: {file_path}")
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        # Load the document
        documents = loader.load()
        
        if not documents:
            raise ValueError(f"No content extracted from {file_path}")
        
        logger.info(f"Loaded {len(documents)} pages/sections from {file_path}")
        
        # Split into chunks
        splits = text_splitter.split_documents(documents)
        
        if not splits:
            raise ValueError(f"Document splitting produced no chunks for {file_path}")
        
        logger.info(f"Split into {len(splits)} chunks")
        
        return splits
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error loading/splitting document {file_path}: {e}", exc_info=True)
        raise Exception(f"Failed to process document: {str(e)}")

def index_document_to_chroma(file_path: str, file_id: int) -> bool:
    """
    Index a document to the Chroma vector store.
    
    Args:
        file_path: Path to the document
        file_id: Database ID for tracking
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting indexing for file_id {file_id}: {file_path}")
        
        # Load and split document
        splits = load_and_split_document(file_path)
        
        if not splits:
            logger.error(f"No document chunks created for file_id {file_id}")
            return False
        
        # Add metadata to each split
        for i, split in enumerate(splits):
            split.metadata.update({
                'file_id': file_id,
                'chunk_index': i,
                'total_chunks': len(splits),
                'source_file': file_path
            })
        
        # Add to vector store
        with _vectorstore_lock:
            vectorstore.add_documents(splits)
            try:
                vectorstore.persist()
            except AttributeError:
                pass
        logger.info(
            f"Successfully indexed {len(splits)} chunks for file_id {file_id}"
        )
        return True
        
    except Exception as e:
        logger.error(
            f"Error indexing document (file_id {file_id}): {str(e)}",
            exc_info=True
        )
        return False

def delete_doc_from_chroma(file_id: int) -> bool:
    """
    Delete all chunks associated with a file_id from Chroma.
    
    Args:
        file_id: The file ID to delete
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Attempting to delete chunks for file_id {file_id}")
        
        # First, check how many documents exist with this file_id
        try:
            docs = vectorstore.get(where={"file_id": file_id})
            chunk_count = len(docs['ids']) if docs and 'ids' in docs else 0
            
            if chunk_count == 0:
                logger.warning(f"No chunks found for file_id {file_id}")
                return True  # Nothing to delete, consider it successful
            
            logger.info(f"Found {chunk_count} chunks for file_id {file_id}")
            
        except Exception as e:
            logger.warning(f"Could not count chunks for file_id {file_id}: {e}")
        
        # Delete all documents with this file_id
        vectorstore._collection.delete(where={"file_id": file_id})
        
        logger.info(f"Successfully deleted all chunks for file_id {file_id}")
        return True
        
    except Exception as e:
        logger.error(
            f"Error deleting document chunks (file_id {file_id}): {str(e)}",
            exc_info=True
        )
        return False

def get_document_chunks(file_id: int) -> Optional[dict]:
    """
    Get information about chunks for a specific document.
    
    Args:
        file_id: The file ID to query
    
    Returns:
        Dictionary with chunk information or None
    """
    try:
        with _vectorstore_lock:
            docs = vectorstore.get(where={"file_id": file_id})
        
        if not docs or 'ids' not in docs:
            return None
        
        return {
            "file_id": file_id,
            "chunk_count": len(docs['ids']),
            "chunk_ids": docs['ids']
        }
        
    except Exception as e:
        logger.error(f"Error getting chunks for file_id {file_id}: {e}")
        return None

def get_vectorstore_stats() -> dict:
    """
    Get statistics about the vector store.
    
    Returns:
        Dictionary with vector store statistics
    """
    try:
        with _vectorstore_lock:
            collection = vectorstore._collection
            count = collection.count()
        
        return {
            "total_chunks": count,
            "collection_name": collection.name,
            "persist_directory": settings.chroma_persist_dir
        }
        
    except Exception as e:
        logger.error(f"Error getting vector store stats: {e}")
        return {
            "error": str(e)
        }

def search_documents(query: str, k: int = 5, file_id: Optional[int] = None) -> List[Document]:
    """
    Search for relevant documents.
    
    Args:
        query: Search query
        k: Number of results to return
        file_id: Optional file ID to filter results
    
    Returns:
        List of relevant documents
    """
    try:
        search_kwargs = {"k": k}

        if file_id is not None:
            search_kwargs["where"] = {"file_id": file_id}

        with _vectorstore_lock:
            retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
            results = retriever.get_relevant_documents(query)
        logger.info(f"Search returned {len(results)} documents for query: {query[:50]}..." + (f"filtered by file_id {file_id}" if file_id else ""))
        return results
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []

def clear_all_documents() -> bool:
    """
    Clear all documents from the vector store.
    USE WITH CAUTION - This deletes everything!
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.warning("Clearing ALL documents from vector store")
        
        # Get all document IDs
        all_docs = vectorstore.get()
        
        if not all_docs or 'ids' not in all_docs:
            logger.info("No documents to clear")
            return True
        
        # Delete all
        vectorstore._collection.delete(ids=all_docs['ids'])
        
        logger.info(f"Cleared {len(all_docs['ids'])} documents from vector store")
        return True
        
    except Exception as e:
        logger.error(f"Error clearing vector store: {e}")
        return False
def check_vectorstore_health() -> bool:
    """Check if vector store is accessible and functional"""
    try:
        with _vectorstore_lock:
            vectorstore._collection.count()
        return True
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        return False