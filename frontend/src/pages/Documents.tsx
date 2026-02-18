import React, { useEffect, useState } from 'react';
import { Upload, FileText, Trash2, Clock, Database, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import DashboardLayout from '../components/DashboardLayout';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { 
  fetchDocuments, 
  uploadDocument, 
  deleteDocument,
  clearDocError 
} from '../features/documents/documentSlice';
import './Documents.css';

export default function Documents() {
  const dispatch = useAppDispatch();
  const { 
    items: documents, 
    isLoading, 
    isUploading, 
    uploadProgress, 
    error 
  } = useAppSelector(state => state.documents);
  
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    dispatch(fetchDocuments());
  }, [dispatch]);

  const handleUpload = async (file: File) => {
    dispatch(uploadDocument(file));
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleUpload(e.target.files[0]);
      e.target.value = ''; // Reset input
    }
  };

  const handleDelete = async (id: number, filename: string) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;
    dispatch(deleteDocument(id));
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const onDragLeave = () => setIsDragging(false);
  
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <div>
          <h1 className="page-title">Knowledge Base</h1>
          <p className="page-subtitle">Upload and manage documents for AI-powered querying</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.875rem', color: '#94a3b8' }}>Total Documents</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'white' }}>{documents.length}</div>
        </div>
      </div>

      <div className="content-padding">
        
        {/* Error Message */}
        {error && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '1rem',
            marginBottom: '1rem',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '0.5rem',
            color: '#fca5a5'
          }}>
            <AlertCircle size={20} />
            <span>{error}</span>
            <button 
              onClick={() => dispatch(clearDocError())}
              style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: '#fca5a5', cursor: 'pointer' }}
            >
              ✕
            </button>
          </div>
        )}
        
        {/* Upload Zone */}
        <div 
          className={`upload-zone ${isDragging ? 'drag-active' : ''}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <input 
            type="file" 
            className="file-input" 
            onChange={onFileChange} 
            accept=".pdf,.docx,.txt" 
            disabled={isUploading}
          />
          
          {isUploading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Loader2 size={48} color="#6366f1" style={{ animation: 'spin 1s linear infinite', marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'white' }}>Processing Document...</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '0.5rem' }}>{uploadProgress}</p>
              <p style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '0.25rem' }}>This may take a minute for large files</p>
            </div>
          ) : (
            <>
              <Upload size={48} color="#64748b" style={{ marginBottom: '1rem' }} />
              <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'white' }}>Drop your files here</h3>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '0.5rem' }}>Supports PDF, DOCX, TXT (Max 50MB)</p>
              <button 
                style={{ 
                  marginTop: '1rem', 
                  padding: '0.5rem 1rem', 
                  background: 'rgba(51, 65, 85, 0.5)', 
                  border: 'none',
                  borderRadius: '0.375rem', 
                  fontSize: '0.875rem', 
                  fontWeight: 500, 
                  color: '#a5b4fc',
                  cursor: 'pointer',
                  pointerEvents: 'none'
                }}
              >
                Or click to browse
              </button>
            </>
          )}
        </div>

        {/* Document List */}
        <div className="doc-list">
          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
              <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', marginBottom: '1rem' }} />
              <p>Loading documents...</p>
            </div>
          ) : documents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
              <FileText size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
              <p>No documents uploaded yet.</p>
              <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>Upload your first document to get started!</p>
            </div>
          ) : (
            documents.map((doc) => (
              <div key={doc.id} className="doc-row">
                <div className="doc-icon-wrapper">
                  <FileText size={24} />
                </div>
                <div className="doc-info">
                  <div className="doc-name">{doc.filename}</div>
                  <div className="doc-meta">
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Clock size={12} />
                      {formatDate(doc.created_at)}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Database size={12} />
                      {formatSize(doc.file_size)}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#10b981' }}>
                      <CheckCircle size={12} />
                      {doc.num_chunks} Chunks
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <span className="status-badge">Ready</span>
                  <button 
                    className="action-btn" 
                    onClick={() => handleDelete(doc.id, doc.filename)} 
                    title="Delete Document"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
