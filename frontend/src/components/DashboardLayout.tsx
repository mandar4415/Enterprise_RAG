import React from 'react';
import { 
  LayoutDashboard, 
  MessageSquare, 
  Files, 
  Settings, 
  LogOut,
  Cpu
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { logout as logoutAction } from '../features/auth/authSlice';
import '../styles/Dashboard.css';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(state => state.auth);

  const handleLogout = () => {
    dispatch(logoutAction());
    navigate('/login');
  };

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
           <div style={{ padding: '0.375rem', background: 'rgba(99, 102, 241, 0.1)', borderRadius: '0.5rem', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
              <Cpu size={24} color="#818cf8" />
           </div>
           <div className="brand-text">
             Enterprise <span>RAG</span>
           </div>
        </div>

        <nav className="nav-menu">
          <div 
            onClick={() => navigate('/dashboard')} 
            className={`nav-item ${location.pathname === '/dashboard' ? 'active' : ''}`}
          >
            <MessageSquare size={20} />
            <span>Chat</span>
          </div>
          <div 
            onClick={() => navigate('/documents')} 
            className={`nav-item ${location.pathname === '/documents' ? 'active' : ''}`}
          >
            <Files size={20} />
            <span>Documents</span>
          </div>
          <div className="nav-item" style={{ opacity: 0.5, cursor: 'not-allowed' }} title="Coming Soon">
            <LayoutDashboard size={20} />
            <span>Evaluate</span>
          </div>
          <div style={{ flex: 1 }} />
          <div className="nav-item" style={{ opacity: 0.5, cursor: 'not-allowed' }} title="Coming Soon">
            <Settings size={20} />
            <span>Settings</span>
          </div>
        </nav>

        <div className="user-profile">
          {user?.profile_picture ? (
            <img 
              src={user.profile_picture} 
              alt={user.name}
              style={{ width: 36, height: 36, borderRadius: '50%' }}
            />
          ) : (
            <div className="avatar">
              {user ? getInitials(user.name) : 'U'}
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.875rem', fontWeight: 500, color: 'white', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.name || 'User'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || ''}
            </div>
          </div>
          <button 
            onClick={handleLogout} 
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: '#64748b', 
              cursor: 'pointer',
              padding: '0.5rem',
              borderRadius: '0.375rem',
              transition: 'all 0.2s'
            }}
            title="Logout"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}
