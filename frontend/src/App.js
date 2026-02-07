import React, { useState, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import DocumentManager from './components/DocumentManager';
import Mascot from './components/Mascot';
import './App.css';
import { Toaster } from 'react-hot-toast'; 
import ErrorBoundary from './components/ErrorBoundary';

function App() {
  const [sessionId, setSessionId] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [currentEmotion, setCurrentEmotion] = useState('neutral');
  const [isMascotSpeaking, setIsMascotSpeaking] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [sessionMessages, setSessionMessages] = useState({});
  const [sessions,setSessions] = useState([]);
  const [showSessionList, setShowSessionList] = useState(false);


  useEffect(() => {
    const savedSession = localStorage.getItem('ai_tutor_session');
    const savedMessages = localStorage.getItem('ai_tutor_messages');
    const savedSessions = localStorage.getItem('ai_tutor_sessions');

    if (savedSession) {
      setSessionId(savedSession);
    }
    if (savedMessages) {
      try{
        setSessionMessages(JSON.parse(savedMessages));
      }catch(e){
        console.error("Failed to parse saved messages:", e);
      }
    } 
    if (savedSessions) {
        try {
            const parsed = JSON.parse(savedSessions);
            // Only load sessions that have messages
            const validSessions = parsed.filter(s => s.messageCount > 0);
            setSessions(validSessions);
        } catch(e) {
            console.error("Failed to parse saved sessions:", e);
        }
    }
  }, []);
  useEffect(() => {
    if (Object.keys(sessionMessages).length > 0) {
      localStorage.setItem('ai_tutor_messages', JSON.stringify(sessionMessages));
    }
  }, [sessionMessages]);
  
  useEffect(() => {
    // Only save if there are actually sessions with messages
    if (sessions.length > 0) {
        // Filter out any sessions that might have 0 messages
        const validSessions = sessions.filter(s => s.messageCount > 0);
        if (validSessions.length > 0) {
            localStorage.setItem('ai_tutor_sessions', JSON.stringify(validSessions));
        }
    }
  }, [sessions]);

  const handleNewSession = () => {
    if (sessionId && sessionMessages[sessionId]?.length > 0) {
      const existingSession = sessions.find(s => s.id === sessionId);
      if (!existingSession) {
        const newSession = {
          id: sessionId,
          timestamp: new Date().toISOString(),
          messageCount: sessionMessages[sessionId].length,
          preview:sessionMessages[sessionId][0]?.content.substring(0,50)+'...'
        };
        setSessions(prev => [ newSession,...prev, ]);
      }
    }
    const newSessionId = Date.now().toString(36) + Math.random().toString(36).substring(2);
    setSessionId(newSessionId);
    localStorage.setItem('ai_tutor_session', newSessionId);

      
    setCurrentEmotion('neutral');
    setCurrentResponse('');
    setIsMascotSpeaking(false);
    
    // Switch to chat tab
    setActiveTab('chat');
  };
   const handleLoadSession = (loadSessionId) => {
    setSessionId(loadSessionId);
    localStorage.setItem('ai_tutor_session', loadSessionId);
    setShowSessionList(false);
    setActiveTab('chat');
    
    // Reset mascot
    setCurrentEmotion('neutral');
    setCurrentResponse('');
    setIsMascotSpeaking(false);
  };

  const handleDeleteSession = (deleteSessionId) => {
    // Remove from sessions list
    setSessions(prev => prev.filter(s => s.id !== deleteSessionId));
    
    // Remove messages for this session
    setSessionMessages(prev => {
      const updated = { ...prev };
      delete updated[deleteSessionId];
      return updated;
    });
    
    // If current session is deleted, create new one
    if (deleteSessionId === sessionId) {
      handleNewSession();
    }
  };

  const updateSessionMessages = (newMessages) => {
    setSessionMessages(prev => ({
      ...prev,
      [sessionId]: newMessages
    }));
  };

  const handleSpeakingChange = (speaking) => {
    setIsMascotSpeaking(speaking);
    
    // Reset emotion to neutral when speaking stops
    if (!speaking) {
      setTimeout(() => {
        setCurrentEmotion('neutral');
        setCurrentResponse('');
      }, 300);
    }
  };

  const handleEmotionChange = (emotion) => {
    setCurrentEmotion(emotion);
  };

  const handleResponseChange = (response) => {
    setCurrentResponse(response);
  };

  return (
    <ErrorBoundary> {/* ✅ Wrap with ErrorBoundary */}
      <Toaster 
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 2000,
            iconTheme: {
              primary: '#4ade80',
              secondary: '#fff',
            },
          },
          error: {
            duration: 4000,
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      /> {/* ✅ Add Toast container */}
    <div className="app">
      <header className="app-header">
        <h1>AI Tutor</h1>
        <div className="header-actions">
          <button 
            className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 Chat
          </button>
          <button 
            className={`tab-button ${activeTab === 'documents' ? 'active' : ''}`}
            onClick={() => setActiveTab('documents')}
          >
            📚 Documents
          </button>
          <button 
            className="history-button"
            onClick={() => setShowSessionList(!showSessionList)}
          >
            📜 History ({sessions.length})
          </button>
          <button className="new-session-button" onClick={handleNewSession}>
            ➕ New Session
          </button>
        </div>
      </header>

      {/* Session History Dropdown */}
      {showSessionList && sessions.length > 0 && (
        <div className="session-list-dropdown">
          <div className="session-list-header">
            <h3>Previous Sessions</h3>
            <button onClick={() => setShowSessionList(false)}>❌</button>
          </div>
          <div className="session-list">
            {sessions.map(session => (
              <div 
                key={session.id} 
                className={`session-item ${session.id === sessionId ? 'active' : ''}`}
              >
                <div 
                  className="session-info"
                  onClick={() => handleLoadSession(session.id)}
                >
                  <div className="session-preview">{session.preview}</div>
                  <div className="session-meta">
                    {new Date(session.timestamp).toLocaleString()} â€¢ {session.messageCount} messages
                  </div>
                </div>
                <button 
                  className="delete-session-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSession(session.id);
                  }}
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <main className="app-main">
        {activeTab === 'chat' && (
          <div className="chat-layout">
            <div className="mascot-panel">
              <Mascot 
                emotion={currentEmotion} 
                isSpeaking={isMascotSpeaking}
                currentText={currentResponse}
              />
            </div>
            <div className="chat-panel">
              <ChatInterface 
                key={sessionId}
                sessionId={sessionId} 
                setSessionId={setSessionId}
                messages={sessionMessages[sessionId] || []}
                setMessages={updateSessionMessages}
                onEmotionChange={handleEmotionChange}
                onSpeakingChange={handleSpeakingChange}
                onResponseChange={handleResponseChange}
              />
            </div>
          </div>
        )}
        
        {activeTab === 'documents' && (
          <div className="documents-section">
            <DocumentManager sessionId={sessionId} />
          </div>
        )}
      </main>
    </div>
    </ErrorBoundary>

  );
}

export default App;