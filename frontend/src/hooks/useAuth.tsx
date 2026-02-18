import React, { createContext, useContext, ReactNode } from 'react';
import { useAppSelector, useAppDispatch } from '../store/hooks';
import { setCredentials, logout as logoutAction } from '../features/auth/authSlice';

interface User {
  id: number;
  email: string;
  name: string;
  profile_picture?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

// We keep the Context to avoid breaking types, but it's now a thin wrapper around Redux
const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { user, token, isAuthenticated, isLoading } = useAppSelector((state) => state.auth);
  const dispatch = useAppDispatch();

  const login = (newToken: string, newUser: User) => {
    dispatch(setCredentials({ token: newToken, user: newUser }));
  };

  const logout = () => {
    dispatch(logoutAction());
  };

  return (
    <AuthContext.Provider value={{
      user,
      token,
      isAuthenticated,
      isLoading,
      login,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
