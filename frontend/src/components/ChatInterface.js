import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import removeMd from 'remove-markdown';
import toast from 'react-hot-toast';
import { chatAPI } from '../utils/api';
import { MODELS } from '../config';
import { MessageSkeleton } from './LoadingSkeleton';
import './ChatInterface.css';

function ChatInterface({ 
  sessionId, setSessionId,
  messages, setMessages,
  onEmotionChange, 
  onSpeakingChange, 
  onResponseChange
}) {
  const safeMessages = Array.isArray(messages) ? messages : [];
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(MODELS.GEMINI_FLASH);
  const messagesEndRef = useRef(null);
  
  const [showQuotaPopup, setShowQuotaPopup] = useState(false);
  const [retrySeconds, setRetrySeconds] = useState(null);
  const [countdown, setCountdown] = useState('');
  
  // Speech recognition states
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  
  // Text-to-speech states
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [voices, setVoices] = useState([]);
  const [speechRate, setSpeechRate] = useState(1.0);
  const currentUtteranceRef = useRef(null);
  
  // ✅ NEW: Auto-speak toggle (enabled by default)
  const [autoSpeak, setAutoSpeak] = useState(() => {
    const saved = localStorage.getItem('ai_tutor_auto_speak');
    return saved !== null ? JSON.parse(saved) : true; // Default: true
  });

  // Save auto-speak preference
  useEffect(() => {
    localStorage.setItem('ai_tutor_auto_speak', JSON.stringify(autoSpeak));
  }, [autoSpeak]);

  // Format time helper function
  const formatTime = (seconds) => {
    if (!seconds || seconds <= 0) return '00h 00m 00s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`;
  };

  // Countdown timer effect
  useEffect(() => {
    let timer;
    if (showQuotaPopup && retrySeconds > 0) {
      timer = setInterval(() => {
        setRetrySeconds(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [showQuotaPopup, retrySeconds]);

  // Update countdown display
  useEffect(() => {
    setCountdown(formatTime(retrySeconds));
  }, [retrySeconds]);

  // Initialize session
  useEffect(() => {
    if (!sessionId) {
      const newSessionId = Date.now().toString(36) + Math.random().toString(36).substring(2);
      setSessionId(newSessionId);
      localStorage.setItem('ai_tutor_session', newSessionId);
    }
  }, [sessionId, setSessionId]);

  // Initialize Speech Recognition with proper cleanup
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('Speech recognition not supported in this browser');
      return;
    }

    const recognitionInstance = new SpeechRecognition();
    recognitionInstance.continuous = true;
    recognitionInstance.interimResults = true;
    recognitionInstance.lang = 'en-IN';

    const handleResult = (event) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        }
      }
      if (finalTranscript) {
        setInputValue((prev) => prev + finalTranscript);
      }
    };

    const handleError = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
      if (event.error === 'no-speech') {
        toast.error('No speech detected. Please try again.');
      }
    };

    const handleEnd = () => {
      setIsListening(false);
    };

    recognitionInstance.onresult = handleResult;
    recognitionInstance.onerror = handleError;
    recognitionInstance.onend = handleEnd;

    recognitionRef.current = recognitionInstance;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current = null;
      }
    };
  }, []);

  // Initialize Text-to-Speech voices
  useEffect(() => {
    const synth = window.speechSynthesis;
    
    const loadVoices = () => {
      const availableVoices = synth.getVoices();
      setVoices(availableVoices);
      
      const defaultVoice = availableVoices.find(voice => 
        voice.lang.startsWith('en-US')
      ) || availableVoices[0];
      setSelectedVoice(defaultVoice);
    };

    loadVoices();
    
    if (synth.onvoiceschanged !== undefined) {
      synth.onvoiceschanged = loadVoices;
    }

    return () => {
      synth.cancel();
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [safeMessages]);

  // Toggle speech recognition
  const toggleListening = useCallback(() => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition is not supported in your browser.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        toast.success('Listening... Speak now');
      } catch (error) {
        console.error('Error starting recognition:', error);
        toast.error('Failed to start speech recognition');
      }
    }
  }, [isListening]);

  // Text-to-speech function
  const speakText = useCallback((text, forceSpeak = false, isToggle = false) => {
    const synth = window.speechSynthesis;
    
    // Handle interruption: If already speaking
    if (currentUtteranceRef.current) {
      synth.cancel();
      setIsSpeaking(false);
      onSpeakingChange && onSpeakingChange(false);
      currentUtteranceRef.current = null;
      
      // ✅ FIX: Different behavior based on context
      // If it's a toggle (user clicked speaker button), stop and return
      // If it's auto-speak (new answer arrived), stop old and play new
      if (isToggle) {
        return; // Toggle behavior: stop and don't start new speech
      }
      // For auto-speak: continue below to start new speech
    }
    
    // Don't speak if auto-speak is off and not forced
    if (!autoSpeak && !forceSpeak) return;
    
    if (!text || !text.trim()) return;

    const cleanText = removeMd(text);
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.voice = selectedVoice;
    utterance.rate = speechRate;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      setIsSpeaking(true);
      onSpeakingChange && onSpeakingChange(true);
    };
    
    utterance.onend = () => {
      setIsSpeaking(false);
      onSpeakingChange && onSpeakingChange(false);
      currentUtteranceRef.current = null;
    };
    
    utterance.onerror = () => {
      setIsSpeaking(false);
      onSpeakingChange && onSpeakingChange(false);
      currentUtteranceRef.current = null;
    };

    currentUtteranceRef.current = utterance;
    synth.speak(utterance);
  }, [selectedVoice, speechRate, autoSpeak, onSpeakingChange]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    // Stop listening when sending message
    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    const userMessage = { role: 'user', content: inputValue };
    const newMessages = [...safeMessages, userMessage];
    setMessages(newMessages);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await chatAPI.sendMessage({
        question: inputValue,
        session_id: sessionId,
        model: selectedModel
      });

      const aiMessage = { role: 'assistant', content: response.data.answer };
      setMessages([...newMessages, aiMessage]);
      
      if (response.data.emotion && onEmotionChange) {
        onEmotionChange(response.data.emotion);
      }
      if (onResponseChange) {
        onResponseChange(response.data.answer);
      }

      // ✅ AUTO-SPEAK: Speak immediately if enabled
      if (autoSpeak) {
        // Small delay to ensure message is rendered
        setTimeout(() => {
          speakText(response.data.answer, true);
        }, 100);
      }

      if (!sessionId && response.data.session_id) {
        setSessionId(response.data.session_id);
        localStorage.setItem('ai_tutor_session', response.data.session_id);
      }
      
      toast.success('Response received!');
    } catch (error) {
      console.error('Error sending message:', error);
      
      // ✅ FIX BUG 1: Properly handle 429 quota error
      if (error.response && error.response.status === 429) {
        // Backend returns detail as object {message, retry_after_seconds}
        const detail = error.response.data.detail;
        const seconds = typeof detail === 'object' 
          ? detail.retry_after_seconds 
          : 3600;
        
        console.log('Quota exceeded. Retry after seconds:', seconds);
        setRetrySeconds(seconds);
        setCountdown(formatTime(seconds));
        setShowQuotaPopup(true);
        
        const errorMessage = { 
          role: 'error', 
          content: '⚠️ API limit reached. Check the popup for details.' 
        };
        setMessages([...newMessages, errorMessage]);
        
        // Also show a toast notification
        toast.error('Daily API limit reached!');
      } else {
        const errorMessage = { 
          role: 'error', 
          content: 'Failed to get response. Please try again.' 
        };
        setMessages([...newMessages, errorMessage]);
        toast.error('Failed to get response');
      }
      
      onEmotionChange && onEmotionChange('neutral');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>AI Tutor Chat</h2>
        <div className="header-controls">
          <div className="model-selector">
            <label>Model: </label>
            <select 
              value={selectedModel} 
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              <option value={MODELS.GEMINI_FLASH}>Gemini 2.5 Flash</option>
              <option value={MODELS.GEMINI_PRO}>Gemini Pro</option>
            </select>
          </div>
          
          <div className="voice-selector">
            <label>Voice: </label>
            <select 
              value={selectedVoice?.name || ''} 
              onChange={(e) => {
                const voice = voices.find(v => v.name === e.target.value);
                setSelectedVoice(voice);
              }}
            >
              {voices.map((voice) => (
                <option key={voice.name} value={voice.name}>
                  {voice.name} ({voice.lang})
                </option>
              ))}
            </select>
          </div>

          {/* ✅ FIX BUG 2: Speech rate control with number values */}
          <div className="speech-rate">
            <label>Speed: </label>
            <select 
              value={speechRate} 
              onChange={(e) => setSpeechRate(parseFloat(e.target.value))}
            >
              <option value={0.5}>0.5x (Slow)</option>
              <option value={0.75}>0.75x</option>
              <option value={1.0}>1.0x (Normal)</option>
              <option value={1.25}>1.25x</option>
              <option value={1.5}>1.5x (Fast)</option>
              <option value={2.0}>2.0x (Very Fast)</option>
            </select>
          </div>

          {/* ✅ NEW: Auto-Speak Toggle */}
          <div className="auto-speak-toggle">
            <label>
              <input 
                type="checkbox" 
                checked={autoSpeak}
                onChange={(e) => {
                  setAutoSpeak(e.target.checked);
                  toast.success(
                    e.target.checked 
                      ? '🔊 Auto-speak enabled' 
                      : '🔇 Auto-speak disabled'
                  );
                }}
              />
              Auto-speak responses
            </label>
          </div>
        </div>
      </div>

      <div className="messages-container">
        {safeMessages.length === 0 && (
          <div className="welcome-message">
            <h3>Welcome to AI Tutor!</h3>
            <p>Ask me anything about your uploaded documents.</p>
            <p>🎤 Click the microphone to use voice input</p>
            <p>🔊 {autoSpeak ? 'Responses will be spoken automatically' : 'Click speaker icon to hear responses'}</p>
          </div>
        )}
        
        {safeMessages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <div className="message-content">
              {message.role === 'assistant' ? (
                <ReactMarkdown>{message.content}</ReactMarkdown>
              ) : (
                <p>{message.content}</p>
              )}
            </div>
            
            {message.role === 'assistant' && (
              <button 
                className="speak-button"
                onClick={() => speakText(message.content, true, true)}
                title={isSpeaking ? "Stop speaking" : "Read aloud"}
              >
                {isSpeaking ? '🛑' : '🔊'}
              </button>
            )}
          </div>
        ))}
        
        {isLoading && <MessageSkeleton />}
        
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSendMessage} className="input-container">
        <button
          type="button"
          className={`mic-button ${isListening ? 'listening' : ''}`}
          onClick={toggleListening}
          title={isListening ? "Stop listening" : "Start voice input"}
        >
          {isListening ? '🔴' : '🎤'}
        </button>
        
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={isListening ? "Listening..." : "Type your question or use voice input..."}
          disabled={isLoading}
        />
        
        <button type="submit" disabled={isLoading || !inputValue.trim()}>
          {isLoading ? 'Sending...' : 'Send'}
        </button>
      </form>

      {/* Quota Limit Popup */}
      {showQuotaPopup && (
        <div className="quota-popup-overlay" onClick={() => setShowQuotaPopup(false)}>
          <div className="quota-popup" onClick={(e) => e.stopPropagation()}>
            <h3>⚠️ Daily Limit Reached</h3>
            <p>You have used your free daily quota for Gemini API.</p>
            
            <div className="timer-container">
              <p>You can try again in:</p>
              <div className="countdown-timer">{countdown}</div>
            </div>
            
            <p className="quota-info">
              Free tier quotas reset at midnight Pacific Time (PT).
            </p>
            
            <button className="close-popup-btn" onClick={() => setShowQuotaPopup(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ChatInterface;