import React, { useEffect, useState, useRef } from 'react';
import './Mascot.css';

function Mascot({ emotion = 'neutral', isSpeaking = false, currentText = '' }) {
  const [displayEmotion, setDisplayEmotion] = useState('neutral');
  const [mouthMoving, setMouthMoving] = useState(false);
  const speechIntervalRef = useRef(null);

  useEffect(() => {
    setDisplayEmotion(emotion);
  }, [emotion]);

  useEffect(() => {
    if (isSpeaking) {
      setMouthMoving(true);
      // Animate mouth while speaking
      speechIntervalRef.current = setInterval(() => {
        setMouthMoving(prev => !prev);
      }, 200);
    } else {
      setMouthMoving(false);
      if (speechIntervalRef.current) {
        clearInterval(speechIntervalRef.current);
      }
    }

    return () => {
      if (speechIntervalRef.current) {
        clearInterval(speechIntervalRef.current);
      }
    };
  }, [isSpeaking]);

  const getEyeStyle = () => {
    switch (displayEmotion) {
      case 'happy':
        return 'eyes-happy';
      case 'thinking':
        return 'eyes-thinking';
      case 'encouraging':
        return 'eyes-encouraging';
      case 'explaining':
        return 'eyes-explaining';
      default:
        return 'eyes-neutral';
    }
  };

  const getMouthStyle = () => {
    if (mouthMoving) return 'mouth-speaking';
    
    switch (displayEmotion) {
      case 'happy':
        return 'mouth-happy';
      case 'thinking':
        return 'mouth-thinking';
      case 'encouraging':
        return 'mouth-encouraging';
      case 'explaining':
        return 'mouth-explaining';
      default:
        return 'mouth-neutral';
    }
  };

  return (
    <div className="mascot-container">
      <div className={`mascot ${displayEmotion}`}>
        <div className="mascot-head">
          {/* Robot head design */}
          <div className="antenna">
            <div className="antenna-ball"></div>
          </div>
          
          {/* Face screen */}
          <div className="face-screen">
            {/* Eyes */}
            <div className="eyes">
              <div className={`eye left-eye ${getEyeStyle()}`}>
                <div className="pupil"></div>
              </div>
              <div className={`eye right-eye ${getEyeStyle()}`}>
                <div className="pupil"></div>
              </div>
            </div>
            
            {/* Mouth */}
            <div className={`mouth ${getMouthStyle()}`}>
              <div className="mouth-inner"></div>
            </div>
          </div>

          {/* Side details */}
          <div className="ear left-ear"></div>
          <div className="ear right-ear"></div>
        </div>

        {/* Emotion indicator */}
        <div className="emotion-indicator">
          <span className="emotion-label">{displayEmotion}</span>
        </div>
      </div>

    </div>
  );
}

export default Mascot;