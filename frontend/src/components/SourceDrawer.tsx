import { useState } from 'react';
import { X, FileText, BarChart2, BookOpen, ChevronDown, ChevronUp, Hash, FileSearch } from 'lucide-react';
import '../styles/Dashboard.css';

interface Source {
  source_id: string;
  document: string;
  document_id: number;
  page_number: number | null;
  chunk_index: number;
  relevance_score: number;
  content_preview?: string;
  full_content: string;
}

interface SourceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sources: Source[];
  activeSourceId: string | null;
}

export default function SourceDrawer({ isOpen, onClose, sources, activeSourceId }: SourceDrawerProps) {
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  const toggleExpand = (index: number) => {
    setExpandedSources(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // Format relevance as percentage with color coding
  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return '#10b981'; // Green - High relevance
    if (score >= 0.6) return '#f59e0b'; // Amber - Medium relevance
    return '#64748b'; // Gray - Lower relevance
  };

  // Clean up content - remove excessive whitespace and dotted lines
  const cleanContent = (content: string) => {
    return content
      .replace(/\.{3,}/g, '...') // Replace long dots with ellipsis
      .replace(/\n{3,}/g, '\n\n') // Limit multiple newlines
      .trim();
  };

  // Get a short preview of the content
  const getPreview = (source: Source) => {
    const text = source.content_preview || source.full_content;
    const cleaned = cleanContent(text);
    if (cleaned.length <= 150) return cleaned;
    return cleaned.substring(0, 150) + '...';
  };

  return (
    <>
      {isOpen && <div className="source-drawer-overlay" onClick={onClose} />}
      <div className={`source-drawer ${isOpen ? 'open' : ''}`}>
        {/* Header */}
        <div className="drawer-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ 
              padding: '0.5rem', 
              background: 'rgba(99, 102, 241, 0.1)', 
              borderRadius: '0.5rem',
              border: '1px solid rgba(99, 102, 241, 0.2)'
            }}>
              <BookOpen size={20} color="#818cf8" />
            </div>
            <div>
              <h2 className="drawer-title">Cited Sources</h2>
              <p style={{ fontSize: '0.75rem', color: '#64748b', margin: 0 }}>
                {sources.length} source{sources.length !== 1 ? 's' : ''} found
              </p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            style={{ 
              padding: '0.5rem', 
              background: 'rgba(255,255,255,0.05)', 
              border: 'none',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              color: '#94a3b8',
              transition: 'all 0.2s'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="drawer-content">
          {sources.length === 0 ? (
            <div style={{ 
              textAlign: 'center', 
              color: '#64748b', 
              marginTop: '3rem',
              padding: '2rem'
            }}>
              <FileSearch size={48} style={{ opacity: 0.3, marginBottom: '1rem' }} />
              <p>No sources available for this response.</p>
            </div>
          ) : (
            sources.map((source, idx) => {
              const isExpanded = expandedSources.has(idx);
              const isActive = activeSourceId === source.source_id || 
                (activeSourceId && activeSourceId.includes(String(idx + 1)));
              const relevancePercent = Math.round(source.relevance_score * 100);
              
              return (
                <div 
                  key={idx} 
                  style={{
                    background: isActive ? 'rgba(99, 102, 241, 0.08)' : 'rgba(30, 41, 59, 0.5)',
                    border: `1px solid ${isActive ? 'rgba(99, 102, 241, 0.3)' : 'rgba(255, 255, 255, 0.05)'}`,
                    borderRadius: '0.75rem',
                    marginBottom: '0.75rem',
                    overflow: 'hidden',
                    transition: 'all 0.2s'
                  }}
                >
                  {/* Source Header */}
                  <div style={{
                    padding: '1rem',
                    borderBottom: isExpanded ? '1px solid rgba(255, 255, 255, 0.05)' : 'none'
                  }}>
                    {/* Top Row: Document name and relevance */}
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'flex-start',
                      marginBottom: '0.75rem'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: 0 }}>
                        <FileText size={16} color="#818cf8" style={{ flexShrink: 0 }} />
                        <span style={{ 
                          fontSize: '0.9rem',
                          fontWeight: 600,
                          color: '#e2e8f0',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }} title={source.document}>
                          {source.document}
                        </span>
                      </div>
                      <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '0.25rem',
                        padding: '0.25rem 0.5rem',
                        background: `${getRelevanceColor(source.relevance_score)}15`,
                        borderRadius: '0.375rem',
                        border: `1px solid ${getRelevanceColor(source.relevance_score)}30`,
                        flexShrink: 0,
                        marginLeft: '0.5rem'
                      }}>
                        <BarChart2 size={12} color={getRelevanceColor(source.relevance_score)} />
                        <span style={{ 
                          fontSize: '0.75rem', 
                          fontWeight: 600, 
                          color: getRelevanceColor(source.relevance_score) 
                        }}>
                          {relevancePercent}%
                        </span>
                      </div>
                    </div>

                    {/* Meta Row: Source ID, Page, Chunk */}
                    <div style={{ 
                      display: 'flex', 
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                      marginBottom: '0.75rem'
                    }}>
                      <span style={{
                        fontSize: '0.7rem',
                        padding: '0.2rem 0.5rem',
                        background: 'rgba(99, 102, 241, 0.15)',
                        color: '#a5b4fc',
                        borderRadius: '0.25rem',
                        fontWeight: 600
                      }}>
                        {source.source_id}
                      </span>
                      {source.page_number && (
                        <span style={{
                          fontSize: '0.7rem',
                          padding: '0.2rem 0.5rem',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: '#94a3b8',
                          borderRadius: '0.25rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.25rem'
                        }}>
                          Page {source.page_number}
                        </span>
                      )}
                      <span style={{
                        fontSize: '0.7rem',
                        padding: '0.2rem 0.5rem',
                        background: 'rgba(255, 255, 255, 0.05)',
                        color: '#94a3b8',
                        borderRadius: '0.25rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.25rem'
                      }}>
                        <Hash size={10} />
                        Chunk {source.chunk_index}
                      </span>
                    </div>

                    {/* Preview Text */}
                    <div style={{
                      fontSize: '0.85rem',
                      color: '#cbd5e1',
                      lineHeight: '1.5',
                      padding: '0.75rem',
                      background: 'rgba(0, 0, 0, 0.2)',
                      borderRadius: '0.5rem',
                      borderLeft: '3px solid rgba(99, 102, 241, 0.5)',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    }}>
                      {isExpanded ? cleanContent(source.full_content) : getPreview(source)}
                    </div>

                    {/* Expand/Collapse Button */}
                    {source.full_content.length > 150 && (
                      <button
                        onClick={() => toggleExpand(idx)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '0.5rem',
                          width: '100%',
                          marginTop: '0.75rem',
                          padding: '0.5rem',
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                          borderRadius: '0.375rem',
                          color: '#818cf8',
                          fontSize: '0.8rem',
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp size={14} />
                            Show Less
                          </>
                        ) : (
                          <>
                            <ChevronDown size={14} />
                            Show Full Content
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
}
