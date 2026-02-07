// src/config.js
export const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const APP_CONFIG = {
  name: 'AI Tutor',
  version: '2.1',
  maxFileSize: 10 * 1024 * 1024, // 10MB
  supportedFormats: ['.pdf', '.docx', '.html'],
};

export const MODELS = {
  GEMINI_FLASH: 'gemini-2.5-flash',
  GEMINI_PRO: 'gemini-pro',
};

export const EMOTIONS = {
  HAPPY: 'happy',
  EXPLAINING: 'explaining',
  THINKING: 'thinking',
  ENCOURAGING: 'encouraging',
  NEUTRAL: 'neutral',
};