// src/utils/api.js
import axios from 'axios';
import { API_URL } from '../config';
import toast from 'react-hot-toast';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  timeout: 60000, // 60 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // You can add auth tokens here if needed
    // config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Global error handling
    if (error.response) {
      const { status, data } = error.response;
      
      switch (status) {
        case 400:
          toast.error(data.detail || 'Invalid request');
          break;
        case 404:
          toast.error('Resource not found');
          break;
        case 413:
          toast.error('File too large. Maximum size is 10MB');
          break;
        case 429:
          // Quota limit - don't show toast here, let component handle it
          break;
        case 500:
          toast.error('Server error. Please try again later');
          break;
        default:
          toast.error('An unexpected error occurred');
      }
    } else if (error.request) {
      toast.error('Network error. Please check your connection');
    }
    
    return Promise.reject(error);
  }
);

// API methods
export const chatAPI = {
  sendMessage: (data) => api.post('/chat', data),
};

export const documentAPI = {
  upload: (formData) => 
    api.post('/upload-doc', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  list: () => api.get('/list-docs'),
  delete: (fileId) => api.post('/delete-doc', { file_id: fileId }),
};

export const statsAPI = {
  get: () => api.get('/api-stats'),
};

export default api;