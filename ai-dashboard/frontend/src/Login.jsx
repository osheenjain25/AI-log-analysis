import React, { useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Zap, Lock, User, ArrowRight, AlertCircle } from 'lucide-react';
import { useAuth } from './AuthContext';
const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(username, password);
        } catch (err) {
            setError('Invalid credentials. Please try again.');
        } finally {
            setLoading(false);
        }
    };
    console.log('Rendering Login component');
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            background: 'var(--bg-color)',
            color: '#fff',
            fontFamily: "'Inter', sans-serif"
        }}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                style={{
                    background: 'var(--panel-bg)',
                    padding: '48px',
                    borderRadius: '24px',
                    border: '1px solid var(--border-glass)',
                    boxShadow: 'var(--shadow-premium)',
                    width: '400px',
                    backdropFilter: 'blur(20px)'
                }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '32px' }}>
                    <motion.div
                        animate={{ rotate: [0, 10, 0] }}
                        transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
                        style={{ marginBottom: '16px' }}
                    >
                        <Zap color="var(--accent-primary)" fill="var(--accent-primary)" size={48} />
                    </motion.div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', margin: 0, letterSpacing: '-0.02em' }}>Welcome Back</h1>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '8px' }}>Sign in to access the dashboard</p>
                </div>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        style={{
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            color: '#ef4444',
                            padding: '12px',
                            borderRadius: '12px',
                            marginBottom: '24px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            fontSize: '0.9rem'
                        }}
                    >
                        <AlertCircle size={18} />
                        {error}
                    </motion.div>
                )}
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '20px' }}>
                        <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: '600' }}>Username</label>
                        <div style={{ position: 'relative' }}>
                            <User size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="Enter your username"
                                style={{
                                    width: '100%',
                                    padding: '14px 14px 14px 44px',
                                    background: 'rgba(255,255,255,0.03)',
                                    border: '1px solid var(--border-glass)',
                                    borderRadius: '12px',
                                    color: '#fff',
                                    outline: 'none',
                                    fontSize: '0.95rem',
                                    transition: 'border-color 0.2s'
                                }}
                                onFocus={(e) => e.target.style.borderColor = 'var(--accent-primary)'}
                                onBlur={(e) => e.target.style.borderColor = 'var(--border-glass)'}
                            />
                        </div>
                    </div>
                    <div style={{ marginBottom: '32px' }}>
                        <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: '600' }}>Password</label>
                        <div style={{ position: 'relative' }}>
                            <Lock size={18} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="Enter your password"
                                style={{
                                    width: '100%',
                                    padding: '14px 14px 14px 44px',
                                    background: 'rgba(255,255,255,0.03)',
                                    border: '1px solid var(--border-glass)',
                                    borderRadius: '12px',
                                    color: '#fff',
                                    outline: 'none',
                                    fontSize: '0.95rem',
                                    transition: 'border-color 0.2s'
                                }}
                                onFocus={(e) => e.target.style.borderColor = 'var(--accent-primary)'}
                                onBlur={(e) => e.target.style.borderColor = 'var(--border-glass)'}
                            />
                        </div>
                    </div>
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        type="submit"
                        disabled={loading}
                        style={{
                            width: '100%',
                            padding: '14px',
                            borderRadius: '14px',
                            background: 'var(--accent-primary)',
                            border: 'none',
                            color: '#000',
                            fontWeight: '800',
                            fontSize: '1rem',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            boxShadow: '0 10px 20px -5px hsla(185, 100%, 50%, 0.4)',
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            gap: '10px',
                            opacity: loading ? 0.7 : 1
                        }}
                    >
                        {loading ? 'Signing In...' : 'Sign In'}
                        {!loading && <ArrowRight size={18} />}
                    </motion.button>
                </form>
            </motion.div>
        </div>
    );
};
export default Login;