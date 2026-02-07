// src/components/LoadingSkeleton.js
import React from 'react';
import './LoadingSkeleton.css';

export const MessageSkeleton = () => (
  <div className="message-skeleton">
    <div className="skeleton-avatar"></div>
    <div className="skeleton-content">
      <div className="skeleton-line long"></div>
      <div className="skeleton-line medium"></div>
      <div className="skeleton-line short"></div>
    </div>
  </div>
);

export const DocumentSkeleton = () => (
  <div className="document-skeleton">
    <div className="skeleton-icon"></div>
    <div className="skeleton-info">
      <div className="skeleton-line medium"></div>
      <div className="skeleton-line short"></div>
    </div>
  </div>
);

export const DocumentGridSkeleton = ({ count = 3 }) => (
  <div className="documents-grid">
    {Array.from({ length: count }).map((_, index) => (
      <DocumentSkeleton key={index} />
    ))}
  </div>
);

export const ChatHeaderSkeleton = () => (
  <div className="chat-header-skeleton">
    <div className="skeleton-line long"></div>
    <div className="skeleton-controls">
      <div className="skeleton-button"></div>
      <div className="skeleton-button"></div>
    </div>
  </div>
);

export default MessageSkeleton;