import React, { useState, useRef, useEffect } from 'react';
import { Send, Cpu, User as UserIcon, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import SourceDrawer from './SourceDrawer';
import { Source } from '../api/services';
import '../styles/Dashboard.css';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { 
  addMessage, 
  setActiveSources, 
  setDrawerOpen, 
  setActiveSourceId,
  askQuestion
} from '../features/chat/chatSlice';

export default function ChatInterface() {
  const [input, setInput] = useState('');
  
  // Use Redux state (The Warehouse)
  const { 
    messages, 
    isLoading, 
    activeSources, 
    isDrawerOpen, 
    activeSourceId, 
    currentStep 
  } = useAppSelector((state) => state.chat);
  
  const dispatch = useAppDispatch();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStep]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px';
    }
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userQuery = input.trim();
    
    // 1. Add user message locally
    dispatch(addMessage({ 
      id: Date.now().toString(), 
      role: 'user', 
      content: userQuery 
    }));

    setInput('');

    // 2. DISPATCH THE THUNK (The big move!)
    // All the complexity of API calls, thinking steps, and loading state
    // is now the "Manager's" (Thunk) responsibility.
    dispatch(askQuestion(userQuery));
  };

  const handleCitationClick = (sourceId: string, sources: Source[]) => {
    dispatch(setActiveSources(sources));
    dispatch(setActiveSourceId(sourceId));
    dispatch(setDrawerOpen(true));
  };

  // Render content with clickable citations
  const renderContent = (content: string, sources?: Source[]) => {
    if (!sources || sources.length === 0) {
      return <ReactMarkdown>{content}</ReactMarkdown>;
    }

    // Pattern to match various citation formats:
    // (Source 1 [Page 32, Chunk 102]: "text...")
    // (Source 1 [Page 32, Chunk 102])
    // (Source 1: "text")
    // [Source 1]
    const citationPattern = /(\(Source \d+[^)]*\)|\[Source \d+\])/g;
    const parts = content.split(citationPattern);
    
    return (
      <div>
        {parts.map((part, index) => {
          const sourceMatch = part.match(/Source (\d+)/);
          if (sourceMatch && (part.startsWith('(Source') || part.startsWith('[Source'))) {
            const sourceNum = parseInt(sourceMatch[1]);
            // Find the source for tooltip
            const source = sources.find(s => s.source_id === `Source ${sourceNum}`);
            
            return (
              <span 
                key={index} 
                className="citation-badge"
                onClick={() => handleCitationClick(`Source ${sourceNum}`, sources)}
                title={source ? `${source.document} - Page ${source.page_number || 'N/A'}` : undefined}
              >
                Source {sourceNum}
              </span>
            );
          }
          // Render markdown for non-citation parts
          return <ReactMarkdown key={index} components={{ p: React.Fragment }}>{part}</ReactMarkdown>;
        })}
      </div>
    );
  };

  return (
    <div className="chat-layout">
      {/* Source Drawer */}
      <SourceDrawer 
        isOpen={isDrawerOpen} 
        onClose={() => dispatch(setDrawerOpen(false))} 
        sources={activeSources}
        activeSourceId={activeSourceId}
      />

      {/* Chat History */}
      <div className="chat-history">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-row ${msg.role}`}>
            <div className={`message-avatar ${msg.role}`}>
              {msg.role === 'ai' ? <Cpu size={20} /> : <UserIcon size={20} />}
            </div>
            <div className={`message-bubble ${msg.role === 'ai' ? 'ai-content' : ''}`}>
              {msg.role === 'ai' ? (
                renderContent(msg.content, msg.sources)
              ) : (
                msg.content
              )}
              {/* Show sources count */}
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ 
                  marginTop: '1rem', 
                  paddingTop: '0.75rem', 
                  borderTop: '1px solid rgba(255,255,255,0.1)',
                  fontSize: '0.8rem',
                  color: '#94a3b8'
                }}>
                  <span 
                    onClick={() => handleCitationClick('all', msg.sources!)}
                    style={{ cursor: 'pointer', color: '#818cf8' }}
                  >
                    📚 View all {msg.sources.length} sources
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {/* Thinking Indicator */}
        {isLoading && currentStep && (
          <div className="message-row ai">
            <div className="message-avatar ai">
              <Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} />
            </div>
            <div className="status-indicator">
              <div className="pulse-dot" />
              <span>{currentStep}</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="input-area">
        <div className="input-container">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask a question about your documents..."
            className="chat-input"
            disabled={isLoading}
            rows={1}
          />
          <button 
            className="send-btn" 
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            title="Send message"
          >
            {isLoading ? (
              <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
