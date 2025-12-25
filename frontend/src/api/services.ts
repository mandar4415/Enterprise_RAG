import api from './client';

export interface User {
    id: number;
    email: string;
    name: string;
    auth_provider: string;
    is_email_verified: boolean;
}

export interface AuthResponse {
    access_token: string;
    user: User;
}

export interface QueryResponse {
    query: string;
    answer: string;
    sources: Source[];
    status: string;
}

export interface Source {
    source_id: string;
    document: string;
    document_id: number;
    page_number: number | null;
    chunk_index: number;
    relevance_score: number;
    content_preview: string;
    full_content: string;
}

export const authService = {
    login: async (email: string, password: string): Promise<AuthResponse> => {
        const response = await api.post<AuthResponse>('/auth/login', { email, password });
        return response.data;
    },

    signup: async (name: string, email: string, password: string) => {
        const response = await api.post('/auth/signup', { name, email, password });
        return response.data;
    },

    verifyOtp: async (email: string, otp_code: string): Promise<AuthResponse> => {
        const response = await api.post<AuthResponse>('/auth/verify-otp', { email, otp_code });
        return response.data;
    },

    me: async (): Promise<User> => {
        const response = await api.get<User>('/auth/me');
        return response.data;
    },

    resendOtp: async (email: string) => {
        const response = await api.post('/auth/resend-otp', { email });
        return response.data;
    },

    getGoogleLoginUrl: async (): Promise<string> => {
        const response = await api.get<{ login_url: string }>('/auth/google/login');
        return response.data.login_url;
    }
};

export const ragService = {
    query: async (queryText: string, documentIds?: number[]): Promise<QueryResponse> => {
        const response = await api.post<QueryResponse>('/query', {
            query: queryText,
            document_ids: documentIds
        });
        return response.data;
    },

    uploadDocument: async (file: File) => {
        const formData = new FormData();
        formData.append('file', file);

        // Don't set Content-Type manually - browser sets it with boundary
        // Allow long timeout for large files/ingestion (5 minutes)
        const response = await api.post('/upload', formData, {
            timeout: 300000 // 5 minutes for large file processing
        });
        return response.data;
    },

    listDocuments: async () => {
        const response = await api.get('/documents');
        return response.data;
    },

    deleteDocument: async (id: number) => {
        const response = await api.delete(`/documents/${id}`);
        return response.data;
    }
};
