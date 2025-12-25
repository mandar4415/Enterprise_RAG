import axios from 'axios';

// Create Axios instance with base URL
const api = axios.create({
    baseURL: 'http://localhost:8000', // Matches your FastAPI backend
});

// Request Interceptor: Attach Token and handle Content-Type
api.interceptors.request.use(
    (config) => {
        // Attach auth token
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        // Only set Content-Type to JSON if not already FormData
        // FormData needs browser to set Content-Type with boundary
        if (config.data instanceof FormData) {
            // Don't set Content-Type for FormData - browser handles it
            delete config.headers['Content-Type'];
        } else if (!config.headers['Content-Type']) {
            config.headers['Content-Type'] = 'application/json';
        }

        return config;
    },
    (error) => Promise.reject(error)
);

// Response Interceptor: Handle Auth Errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        // If 401 Unauthorized, clear token and redirect to login
        if (error.response && error.response.status === 401) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

export default api;
