import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
const AuthContext = createContext(null);
export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        // Set up axios interceptor
        const interceptor = axios.interceptors.request.use(config => {
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
            return config;
        });
        return () => axios.interceptors.request.eject(interceptor);
    }, [token]);
    useEffect(() => {
        if (token) {
            // Verify token and get user details
            axios.get('/users/me/', {
                headers: { Authorization: `Bearer ${token}` }
            })
                .then(response => {
                    setUser(response.data);
                })
                .catch(() => {
                    logout();
                })
                .finally(() => {
                    setLoading(false);
                });
        } else {
            setLoading(false);
        }
    }, [token]);
    const login = async (username, password) => {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        const response = await axios.post('/token', formData);
        const newToken = response.data.access_token;
        localStorage.setItem('token', newToken);
        setToken(newToken);
        // Fetch user details immediately
        const userResp = await axios.get('/users/me/', {
            headers: { Authorization: `Bearer ${newToken}` }
        });
        setUser(userResp.data);
    };
    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    };
    return (
        <AuthContext.Provider value={{ user, token, login, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};
export const useAuth = () => useContext(AuthContext);