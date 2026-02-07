import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { documentAPI } from '../utils/api';
import { DocumentGridSkeleton } from './LoadingSkeleton';
import './DocumentManager.css';

function DocumentManager() {
  const [documents, setDocuments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const response = await documentAPI.list();
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const validExtensions = ['.pdf', '.docx', '.html'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    
    if (!validExtensions.includes(fileExtension)) {
      toast.error(`Invalid file type. Supported: ${validExtensions.join(', ')}`);
      e.target.value = '';
      return;
    }

    // Validate file size (10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File too large. Maximum size is 10MB');
      e.target.value = '';
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsUploading(true);
    const uploadToast = toast.loading(`Uploading ${file.name}...`);

    try {
      await documentAPI.upload(formData);
      toast.success('Upload successful!', { id: uploadToast });
      fetchDocuments();
    } catch (error) {
      console.error('Error uploading file:', error);
      toast.error('Upload failed. Please try again.', { id: uploadToast });
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteDocument = async (fileId, filename) => {
    if (!window.confirm(`Delete ${filename}?`)) return;

    const deleteToast = toast.loading('Deleting document...');

    try {
      await documentAPI.delete(fileId);
      toast.success('Document deleted!', { id: deleteToast });
      fetchDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      toast.error('Failed to delete document', { id: deleteToast });
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'Unknown size';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="document-manager">
      <div className="upload-section">
        <h2>📤 Upload Documents</h2>
        <p className="supported-formats">
          Supported formats: PDF, DOCX, HTML (Max 10MB)
        </p>
        <label className="file-upload-btn">
          <input
            type="file"
            accept=".pdf,.docx,.html"
            onChange={handleFileUpload}
            disabled={isUploading}
          />
          {isUploading ? '⏳ Uploading...' : '📁 Choose File'}
        </label>
      </div>

      <div className="documents-list">
        <h2>📚 Your Documents ({documents.length})</h2>
        
        {/* ✅ ADDED: Loading skeleton */}
        {isLoading ? (
          <DocumentGridSkeleton count={3} />
        ) : documents.length === 0 ? (
          <div className="no-documents">
            <div className="empty-state-icon">📭</div>
            <p>No documents uploaded yet.</p>
            <p className="empty-state-hint">Upload a document to get started!</p>
          </div>
        ) : (
          <div className="documents-grid">
            {documents.map((doc) => (
              <div key={doc.id} className="document-card">
                <div className="doc-icon">
                  {doc.filename.endsWith('.pdf') ? '📄' : 
                   doc.filename.endsWith('.docx') ? '📝' : '🌐'}
                </div>
                <div className="doc-info">
                  <h3 title={doc.filename}>{doc.filename}</h3>
                  <p className="doc-date">{formatDate(doc.upload_timestamp)}</p>
                  {doc.file_size && (
                    <p className="doc-size">{formatFileSize(doc.file_size)}</p>
                  )}
                </div>
                <button
                  onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                  className="delete-btn"
                  title="Delete document"
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DocumentManager;