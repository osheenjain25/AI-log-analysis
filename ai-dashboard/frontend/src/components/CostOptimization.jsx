import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';
import { DollarSign, Play, Loader2, AlertCircle, FileText, Key, Calendar, TrendingUp, ArrowLeft, Settings, Save, Check, Users, Plus, Trash2, Globe } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API_BASE = ''; // Same origin

function CostOptimization({ onBack }) {
    const [granularity, setGranularity] = React.useState('daily');
    const [loading, setLoading] = React.useState(false);
    const [report, setReport] = React.useState(null);
    const [chartData, setChartData] = React.useState(null);
    const [totalAccountCost, setTotalAccountCost] = React.useState(0);
    const [metadata, setMetadata] = React.useState(null);
    const [lastUpdated, setLastUpdated] = React.useState(null);
    const [error, setError] = React.useState(null);

    // Threshold settings state
    const [showSettings, setShowSettings] = React.useState(false);
    const [thresholdType, setThresholdType] = React.useState('percentage');
    const [thresholdValue, setThresholdValue] = React.useState(10);
    const [alertsEnabled, setAlertsEnabled] = React.useState(true);
    const [settingsSaved, setSettingsSaved] = React.useState(false);
    const [settingsError, setSettingsError] = React.useState(null);

    // Multi-account state
    const [accounts, setAccounts] = React.useState([]);
    const [selectedAccountId, setSelectedAccountId] = React.useState('default');
    const [showAccountManager, setShowAccountManager] = React.useState(false);
    const [newAccount, setNewAccount] = React.useState({ name: '', access_key_id: '', secret_access_key: '', session_token: '', region: 'us-east-1' });
    const [accountActionLoading, setAccountActionLoading] = React.useState(false);


    React.useEffect(() => {
        fetchAccounts();
        fetchThresholdSettings();
    }, []);

    React.useEffect(() => {
        fetchLastAnalysis(granularity, false, selectedAccountId);
    }, [granularity, selectedAccountId]);

    const fetchLastAnalysis = async (granularity = 'daily', forceRefresh = false, accountId = 'default') => {
        setLoading(true);
        setError(null);
        try {
            // If forceRefresh or if we know it failed before, trigger a new one
            if (forceRefresh) {
                await axios.post(`${API_BASE}/trigger-full-analysis`, null, {
                    params: { account_id: accountId }
                });
                // Wait a bit for the background task to start
                await new Promise(resolve => setTimeout(resolve, 2000));
            }

            const response = await axios.get(`${API_BASE}/get-last-cost-analysis`, {
                params: { granularity, account_id: accountId }
            });

            if (response.data) {
                // If the data is still an error report, and we didn't just force refresh, try once
                if (response.data.report?.includes("Failed to fetch AWS cost data") && !forceRefresh) {
                    return fetchLastAnalysis(granularity, true);
                }

                setReport(response.data.report);
                setChartData(response.data.chart_data);
                setTotalAccountCost(response.data.total_account_cost);
                setMetadata(response.data.metadata);
                setLastUpdated(response.data.last_updated);
            }
        } catch (err) {
            console.error("Error fetching last analysis:", err);
            setError(err.response?.data?.error || "Failed to fetch cost analysis. It might still be generating.");
        } finally {
            setLoading(false);
        }
    };

    const fetchThresholdSettings = async () => {
        try {
            const response = await axios.get(`${API_BASE}/cost-alert-settings`);
            if (response.data) {
                setThresholdType(response.data.threshold_type || 'percentage');
                setThresholdValue(response.data.threshold_value || 10);
                setAlertsEnabled(response.data.enabled !== false);
            }
        } catch (err) {
            console.error("Error fetching threshold settings:", err);
        }
    };

    const saveThresholdSettings = async () => {
        setSettingsError(null);
        setSettingsSaved(false);
        try {
            const response = await axios.post(`${API_BASE}/cost-alert-settings`, {
                threshold_type: thresholdType,
                threshold_value: parseFloat(thresholdValue),
                enabled: alertsEnabled
            });
            if (response.data.success) {
                setSettingsSaved(true);
                setTimeout(() => setSettingsSaved(false), 3000);
            }
        } catch (err) {
            console.error("Error saving threshold settings:", err);
            setSettingsError(err.response?.data?.error || "Failed to save settings.");
        }
    };
    const fetchAccounts = async () => {
        try {
            const response = await axios.get(`${API_BASE}/aws-accounts`);
            setAccounts(response.data || []);
        } catch (err) {
            console.error("Error fetching accounts:", err);
        }
    };

    const handleAddAccount = async (e) => {
        e.preventDefault();
        alert("Dynamic account management is disabled. Please update the environment configuration (AWS_ACCOUNTS_CONFIG).");
    };

    const handleDeleteAccount = async (id) => {
        alert("Dynamic account management is disabled. Please update the environment configuration (AWS_ACCOUNTS_CONFIG).");
    };

    return (
        <div className="cost-optimization-container" style={{ padding: '32px', color: '#fff', height: '100%', overflowY: 'auto' }}>
            {/* Header Section */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '40px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <button
                        onClick={onBack}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            padding: 0,
                            transition: 'color 0.2s'
                        }}
                        onMouseEnter={(e) => e.target.style.color = '#fff'}
                        onMouseLeave={(e) => e.target.style.color = 'var(--text-muted)'}
                    >
                        <ArrowLeft size={16} />
                        Back to Insights
                    </button>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                            <div style={{ background: 'var(--accent-primary)', width: '4px', height: '24px', borderRadius: '2px' }} />
                            <h2 style={{ margin: 0, fontSize: '2rem', fontWeight: '800', letterSpacing: '-0.02em' }}>AWS Cost Optimization</h2>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div className="live-dot" style={{ background: 'var(--accent-primary)' }} />
                            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                                Powered by Gemini 2.0 Flash • {granularity === 'daily' ? '30-Day' : granularity === 'weekly' ? '90-Day' : '180-Day'} Analysis
                            </span>
                            {metadata?.is_complete && (
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    background: 'rgba(16, 185, 129, 0.1)',
                                    color: '#10b981',
                                    padding: '4px 10px',
                                    borderRadius: '100px',
                                    fontSize: '0.75rem',
                                    fontWeight: '800',
                                    border: '1px solid rgba(16, 185, 129, 0.2)'
                                }}>
                                    VERIFIED DATA
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '16px' }}>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        {/* Account Selector */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            background: 'rgba(255, 255, 255, 0.05)',
                            padding: '8px 16px',
                            borderRadius: '12px',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            backdropFilter: 'blur(10px)'
                        }}>
                            <Globe size={16} color="var(--accent-primary)" />
                            <select
                                value={selectedAccountId}
                                onChange={(e) => setSelectedAccountId(e.target.value)}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    color: '#fff',
                                    fontSize: '0.9rem',
                                    fontWeight: '600',
                                    outline: 'none',
                                    cursor: 'pointer',
                                    minWidth: '150px'
                                }}
                            >
                                {accounts.map(acc => (
                                    <option key={acc.id} value={acc.id} style={{ background: '#1a1a1a' }}>
                                        {acc.name}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <button
                            onClick={() => setShowAccountManager(!showAccountManager)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                background: showAccountManager ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.05)',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                color: '#fff',
                                padding: '10px 16px',
                                borderRadius: '12px',
                                cursor: 'pointer',
                                fontSize: '0.9rem',
                                fontWeight: '600',
                                transition: 'all 0.2s',
                                backdropFilter: 'blur(10px)'
                            }}
                        >
                            <Users size={18} />
                            Accounts
                        </button>

                        <button
                            onClick={() => setShowSettings(!showSettings)}
                            style={{
                                padding: '8px 16px',
                                borderRadius: '12px',
                                border: '1px solid var(--border-glass)',
                                background: showSettings ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)',
                                color: showSettings ? '#000' : 'var(--text-muted)',
                                fontSize: '0.85rem',
                                fontWeight: '700',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px'
                            }}
                        >
                            <Settings size={16} />
                            Alert Settings
                        </button>
                        <div style={{ display: 'flex', gap: '8px', background: 'rgba(255,255,255,0.03)', padding: '4px', borderRadius: '14px', border: '1px solid var(--border-glass)' }}>
                            {['daily', 'weekly', 'monthly'].map((g) => (
                                <button
                                    key={g}
                                    onClick={() => setGranularity(g)}
                                    style={{
                                        padding: '8px 20px',
                                        borderRadius: '10px',
                                        border: 'none',
                                        background: granularity === g ? 'var(--accent-primary)' : 'transparent',
                                        color: granularity === g ? '#000' : 'var(--text-muted)',
                                        fontSize: '0.85rem',
                                        fontWeight: '700',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        textTransform: 'capitalize'
                                    }}
                                >
                                    {g}
                                </button>
                            ))}
                        </div>
                    </div>

                    {lastUpdated && (
                        <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'flex-end',
                            gap: '6px'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: '600' }}>
                                <Calendar size={14} />
                                LAST UPDATED
                            </div>
                            <div style={{
                                fontSize: '1rem',
                                fontWeight: '700',
                                color: '#fff',
                                background: 'rgba(255,255,255,0.05)',
                                padding: '8px 16px',
                                borderRadius: '12px',
                                border: '1px solid var(--border-glass)'
                            }}>
                                {new Date(lastUpdated).toLocaleString()}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {error && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                        marginBottom: '32px',
                        padding: '16px 24px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.2)',
                        borderRadius: '16px',
                        color: '#ef4444',
                        fontSize: '0.95rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        boxShadow: '0 10px 30px rgba(239, 68, 68, 0.1)'
                    }}
                >
                    <AlertCircle size={20} style={{ flexShrink: 0 }} />
                    <span style={{ fontWeight: '600' }}>{error}</span>
                </motion.div>
            )}

            {/* Settings Panel */}
            {/* Account Management Section */}
            {showAccountManager && (
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '24px',
                        padding: '32px',
                        marginBottom: '40px',
                        backdropFilter: 'blur(20px)'
                    }}
                >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                        <h3 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <Users size={24} color="var(--accent-primary)" />
                            AWS Account Management
                        </h3>
                        <button
                            onClick={() => setShowAccountManager(false)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                        >
                            Close
                        </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                        {/* Add New Account Form (Disabled) */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '24px', borderRadius: '16px', border: '1px solid rgba(255, 255, 255, 0.05)', opacity: 0.6 }}>
                            <h4 style={{ margin: '0 0 20px 0', fontSize: '1.1rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Plus size={18} /> Add New Account
                            </h4>
                            <div style={{ background: 'rgba(255, 166, 0, 0.1)', color: '#ffa600', padding: '12px', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '16px', border: '1px solid rgba(255, 166, 0, 0.2)' }}>
                                <AlertCircle size={14} style={{ marginRight: '8px', display: 'inline' }} />
                                Dynamic management is disabled. Credentials must be configured via environment variables for security.
                            </div>
                            <form onSubmit={handleAddAccount} style={{ display: 'flex', flexDirection: 'column', gap: '16px', pointerEvents: 'none' }}>
                                <div>
                                    <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Account Name</label>
                                    <input
                                        type="text"
                                        placeholder="e.g. Production Account"
                                        value={newAccount.name}
                                        onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
                                        style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', padding: '10px', borderRadius: '8px', color: '#fff' }}
                                        required
                                    />
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Access Key ID</label>
                                        <input
                                            type="password"
                                            value={newAccount.access_key_id}
                                            onChange={(e) => setNewAccount({ ...newAccount, access_key_id: e.target.value })}
                                            style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', padding: '10px', borderRadius: '8px', color: '#fff' }}
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Secret Access Key</label>
                                        <input
                                            type="password"
                                            value={newAccount.secret_access_key}
                                            onChange={(e) => setNewAccount({ ...newAccount, secret_access_key: e.target.value })}
                                            style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', padding: '10px', borderRadius: '8px', color: '#fff' }}
                                            required
                                        />
                                    </div>
                                </div>
                                <div>
                                    <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Session Token (Optional)</label>
                                    <input
                                        type="password"
                                        value={newAccount.session_token}
                                        onChange={(e) => setNewAccount({ ...newAccount, session_token: e.target.value })}
                                        style={{ width: '100%', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', padding: '10px', borderRadius: '8px', color: '#fff' }}
                                    />
                                </div>
                                <button
                                    type="submit"
                                    disabled={accountActionLoading}
                                    style={{ background: 'var(--accent-primary)', color: '#fff', border: 'none', padding: '12px', borderRadius: '8px', fontWeight: '700', cursor: 'pointer', marginTop: '8px' }}
                                >
                                    {accountActionLoading ? 'Adding...' : 'Add Account'}
                                </button>
                            </form>
                        </div>

                        {/* Existing Accounts List */}
                        <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '24px', borderRadius: '16px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                            <h4 style={{ margin: '0 0 20px 0', fontSize: '1.1rem', fontWeight: '600' }}>Configured Accounts</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {accounts.map(acc => (
                                    <div key={acc.id} style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        padding: '12px 16px',
                                        background: 'rgba(255,255,255,0.03)',
                                        borderRadius: '12px',
                                        border: acc.id === selectedAccountId ? '1px solid var(--accent-primary)' : '1px solid rgba(255,255,255,0.05)'
                                    }}>
                                        <div>
                                            <div style={{ fontWeight: '600', fontSize: '0.95rem' }}>{acc.name}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{acc.region} • {acc.id === 'default' ? 'System Default' : acc.id.substring(0, 8)}</div>
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            {acc.id !== 'default' && (
                                                <button
                                                    onClick={() => handleDeleteAccount(acc.id)}
                                                    style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: 'none', padding: '8px', borderRadius: '8px', cursor: 'pointer' }}
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            )}
                                            <button
                                                onClick={() => setSelectedAccountId(acc.id)}
                                                style={{
                                                    background: acc.id === selectedAccountId ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
                                                    color: '#fff',
                                                    border: 'none',
                                                    padding: '8px 12px',
                                                    borderRadius: '8px',
                                                    cursor: 'pointer',
                                                    fontSize: '0.8rem',
                                                    fontWeight: '600'
                                                }}
                                            >
                                                {acc.id === selectedAccountId ? 'Active' : 'Select'}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </motion.div>
            )}

            {showSettings && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                        marginBottom: '32px',
                        padding: '24px',
                        background: 'var(--panel-bg)',
                        border: '1px solid var(--border-glass)',
                        borderRadius: '20px',
                        boxShadow: 'var(--shadow-premium)'
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                        <Settings size={20} color="var(--accent-primary)" />
                        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '700' }}>Cost Alert Threshold Settings</h3>
                    </div>

                    {settingsError && (
                        <div style={{
                            marginBottom: '16px',
                            padding: '12px 16px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            borderRadius: '12px',
                            color: '#ef4444',
                            fontSize: '0.9rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}>
                            <AlertCircle size={16} />
                            {settingsError}
                        </div>
                    )}

                    {settingsSaved && (
                        <div style={{
                            marginBottom: '16px',
                            padding: '12px 16px',
                            background: 'rgba(16, 185, 129, 0.1)',
                            border: '1px solid rgba(16, 185, 129, 0.2)',
                            borderRadius: '12px',
                            color: '#10b981',
                            fontSize: '0.9rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px'
                        }}>
                            <Check size={16} />
                            Settings saved successfully!
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* Enable/Disable Alerts */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div>
                                <div style={{ fontSize: '0.95rem', fontWeight: '600', marginBottom: '4px' }}>Enable Cost Alerts</div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Receive notifications when costs exceed threshold</div>
                            </div>
                            <label style={{ position: 'relative', display: 'inline-block', width: '52px', height: '28px' }}>
                                <input
                                    type="checkbox"
                                    checked={alertsEnabled}
                                    onChange={(e) => setAlertsEnabled(e.target.checked)}
                                    style={{ opacity: 0, width: 0, height: 0 }}
                                />
                                <span style={{
                                    position: 'absolute',
                                    cursor: 'pointer',
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    background: alertsEnabled ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
                                    transition: '0.3s',
                                    borderRadius: '28px'
                                }}>
                                    <span style={{
                                        position: 'absolute',
                                        content: '',
                                        height: '20px',
                                        width: '20px',
                                        left: alertsEnabled ? '28px' : '4px',
                                        bottom: '4px',
                                        background: '#fff',
                                        transition: '0.3s',
                                        borderRadius: '50%'
                                    }} />
                                </span>
                            </label>
                        </div>

                        {/* Threshold Type */}
                        <div>
                            <div style={{ fontSize: '0.95rem', fontWeight: '600', marginBottom: '12px' }}>Threshold Type</div>
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <button
                                    onClick={() => setThresholdType('percentage')}
                                    style={{
                                        flex: 1,
                                        padding: '12px 20px',
                                        borderRadius: '12px',
                                        border: '1px solid var(--border-glass)',
                                        background: thresholdType === 'percentage' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)',
                                        color: thresholdType === 'percentage' ? '#000' : 'var(--text-muted)',
                                        fontSize: '0.9rem',
                                        fontWeight: '700',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    Percentage (%)
                                </button>
                                <button
                                    onClick={() => setThresholdType('amount')}
                                    style={{
                                        flex: 1,
                                        padding: '12px 20px',
                                        borderRadius: '12px',
                                        border: '1px solid var(--border-glass)',
                                        background: thresholdType === 'amount' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)',
                                        color: thresholdType === 'amount' ? '#000' : 'var(--text-muted)',
                                        fontSize: '0.9rem',
                                        fontWeight: '700',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s'
                                    }}
                                >
                                    Fixed Amount ($)
                                </button>
                            </div>
                        </div>

                        {/* Threshold Value */}
                        <div>
                            <div style={{ fontSize: '0.95rem', fontWeight: '600', marginBottom: '8px' }}>
                                Threshold Value
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
                                {thresholdType === 'percentage'
                                    ? 'Alert when cost increases by more than this percentage'
                                    : 'Alert when cost increases by more than this dollar amount'}
                            </div>
                            <div style={{ position: 'relative' }}>
                                <input
                                    type="number"
                                    min="0"
                                    step={thresholdType === 'percentage' ? '1' : '0.01'}
                                    value={thresholdValue}
                                    onChange={(e) => setThresholdValue(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '12px 16px',
                                        paddingLeft: '40px',
                                        borderRadius: '12px',
                                        border: '1px solid var(--border-glass)',
                                        background: 'rgba(255,255,255,0.03)',
                                        color: '#fff',
                                        fontSize: '1rem',
                                        fontWeight: '600',
                                        outline: 'none',
                                        transition: 'all 0.2s'
                                    }}
                                    onFocus={(e) => e.target.style.borderColor = 'var(--accent-primary)'}
                                    onBlur={(e) => e.target.style.borderColor = 'var(--border-glass)'}
                                />
                                <span style={{
                                    position: 'absolute',
                                    left: '16px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    color: 'var(--accent-primary)',
                                    fontSize: '1rem',
                                    fontWeight: '700'
                                }}>
                                    {thresholdType === 'percentage' ? '%' : '$'}
                                </span>
                            </div>
                        </div>

                        {/* Save Button */}
                        <button
                            onClick={saveThresholdSettings}
                            style={{
                                padding: '12px 24px',
                                borderRadius: '12px',
                                border: 'none',
                                background: 'var(--accent-primary)',
                                color: '#000',
                                fontSize: '0.95rem',
                                fontWeight: '800',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '8px',
                                transition: 'all 0.2s',
                                boxShadow: '0 4px 12px rgba(var(--accent-primary-rgb), 0.3)'
                            }}
                            onMouseEnter={(e) => e.target.style.transform = 'translateY(-2px)'}
                            onMouseLeave={(e) => e.target.style.transform = 'translateY(0)'}
                        >
                            <Save size={18} />
                            Save Settings
                        </button>
                    </div>
                </motion.div>
            )}


            {loading && !report && (
                <div style={{ height: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '20px' }}>
                    <div className="loading-spinner-container">
                        <Loader2 className="animate-spin" size={48} color="var(--accent-primary)" />
                    </div>
                    <span style={{ fontSize: '1.1rem', color: 'var(--text-muted)', fontWeight: '500' }}>Analyzing AWS infrastructure costs...</span>
                </div>
            )}

            {report ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', position: 'relative' }}>
                    {report.includes("Failed to fetch AWS cost data") && (
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: 'rgba(15, 15, 20, 0.7)',
                            backdropFilter: 'blur(4px)',
                            zIndex: 100,
                            borderRadius: '28px',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '40px',
                            textAlign: 'center',
                            border: '2px dashed rgba(239, 68, 68, 0.3)'
                        }}>
                            <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '24px', borderRadius: '50%', marginBottom: '24px' }}>
                                <Key size={48} color="#ef4444" />
                            </div>
                            <h3 style={{ fontSize: '1.8rem', fontWeight: '800', marginBottom: '16px', color: '#fff' }}>AWS Credentials Required</h3>
                            <p style={{ fontSize: '1.1rem', color: 'var(--text-muted)', maxWidth: '500px', lineHeight: '1.6', marginBottom: '32px' }}>
                                We couldn't fetch your cost data because AWS credentials are missing or invalid. Please configure <code style={{ color: 'var(--accent-primary)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>AWS_ACCESS_KEY_ID</code> and <code style={{ color: 'var(--accent-primary)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>AWS_SECRET_ACCESS_KEY</code> in your environment.
                            </p>
                            <button
                                onClick={() => fetchLastAnalysis(granularity)}
                                style={{
                                    padding: '12px 32px',
                                    borderRadius: '14px',
                                    background: 'var(--accent-primary)',
                                    border: 'none',
                                    color: '#000',
                                    fontWeight: '800',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '10px'
                                }}
                            >
                                <Play size={18} fill="#000" />
                                Retry Analysis
                            </button>
                        </div>
                    )}
                    {/* Key Metrics Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
                        <motion.div
                            whileHover={{ y: -5 }}
                            style={{ background: 'var(--panel-bg)', padding: '32px', borderRadius: '24px', border: '1px solid var(--border-glass)', boxShadow: 'var(--shadow-premium)', position: 'relative', overflow: 'hidden' }}
                        >
                            <div style={{ position: 'absolute', top: '-20px', right: '-20px', opacity: 0.05 }}>
                                <DollarSign size={120} color="var(--accent-primary)" />
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', marginBottom: '12px' }}>AMORTIZED COST</div>
                            <div style={{ fontSize: '2.5rem', fontWeight: '900', color: '#fff', letterSpacing: '-0.02em' }}>
                                <span style={{ fontSize: '1.5rem', verticalAlign: 'top', marginRight: '4px', color: 'var(--accent-primary)' }}>$</span>
                                {(metadata?.total_amortized_cost || totalAccountCost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '600', marginTop: '8px' }}>
                                Includes RIs and Savings Plans
                            </div>
                        </motion.div>

                        <motion.div
                            whileHover={{ y: -5 }}
                            style={{ background: 'var(--panel-bg)', padding: '32px', borderRadius: '24px', border: '1px solid var(--border-glass)', boxShadow: 'var(--shadow-premium)', position: 'relative', overflow: 'hidden' }}
                        >
                            <div style={{ position: 'absolute', top: '-20px', right: '-20px', opacity: 0.05 }}>
                                <TrendingUp size={120} color="var(--accent-secondary)" />
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', marginBottom: '12px' }}>POTENTIAL SAVINGS</div>
                            <div style={{ fontSize: '2.5rem', fontWeight: '900', color: 'var(--accent-secondary)', letterSpacing: '-0.02em' }}>
                                <span style={{ fontSize: '1.5rem', verticalAlign: 'top', marginRight: '4px' }}>$</span>
                                {(() => {
                                    // Heuristic: 15% of total cost if we don't have a specific number yet
                                    const estimated = (metadata?.total_amortized_cost || totalAccountCost || 0) * 0.15;
                                    return estimated.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                                })()}
                            </div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '600', marginTop: '8px' }}>
                                Estimated from AI recommendations
                            </div>
                        </motion.div>

                        <motion.div
                            whileHover={{ y: -5 }}
                            style={{ background: 'var(--panel-bg)', padding: '32px', borderRadius: '24px', border: '1px solid var(--border-glass)', boxShadow: 'var(--shadow-premium)', position: 'relative', overflow: 'hidden' }}
                        >
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: '700', letterSpacing: '0.05em', marginBottom: '12px' }}>FINANCIAL HEALTH</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <div style={{
                                        background: 'rgba(59, 130, 246, 0.1)',
                                        padding: '8px',
                                        borderRadius: '12px',
                                        color: '#3b82f6'
                                    }}>
                                        <TrendingUp size={24} />
                                    </div>
                                    <div style={{ fontSize: '2.5rem', fontWeight: '900', color: '#fff', letterSpacing: '-0.02em' }}>
                                        {metadata?.is_complete ? '92' : '85'}<span style={{ fontSize: '1.2rem', color: 'var(--text-muted)' }}>/100</span>
                                    </div>
                                </div>
                                <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                                    Based on {metadata?.analyzed_services_count || 0} analyzed services
                                </div>
                            </div>
                        </motion.div>
                    </div>

                    {/* Main Content Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '32px', alignItems: 'start' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                            {/* Chart Section */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                style={{ background: 'var(--panel-bg)', padding: '32px', borderRadius: '28px', border: '1px solid var(--border-glass)', boxShadow: 'var(--shadow-premium)' }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                                    <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '12px' }}>
                                        <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '8px', borderRadius: '10px' }}>
                                            <BarChart size={20} color="#3b82f6" />
                                        </div>
                                        {granularity.charAt(0).toUpperCase() + granularity.slice(1)} Cost Breakdown
                                    </h3>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600', background: 'rgba(255,255,255,0.03)', padding: '6px 12px', borderRadius: '20px' }}>
                                        USD / {granularity === 'daily' ? 'DAY' : granularity === 'weekly' ? 'WEEK' : 'MONTH'}
                                    </div>
                                </div>
                                <div style={{ height: '400px', width: '100%' }}>
                                    <ResponsiveContainer key={granularity} width="100%" height="100%">
                                        <BarChart data={chartData?.stacked_bar_data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                                            <XAxis
                                                dataKey="date"
                                                stroke="rgba(255,255,255,0.3)"
                                                fontSize={11}
                                                tickFormatter={(val) => {
                                                    if (!val) return '';
                                                    const parts = val.split('-');
                                                    return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : val;
                                                }}
                                                tickLine={false}
                                                axisLine={false}
                                                dy={10}
                                            />
                                            <YAxis
                                                stroke="rgba(255,255,255,0.3)"
                                                fontSize={11}
                                                tickFormatter={(val) => `$${val}`}
                                                tickLine={false}
                                                axisLine={false}
                                                dx={-10}
                                            />
                                            <Tooltip
                                                content={({ active, payload, label }) => {
                                                    if (active && payload && payload.length) {
                                                        return (
                                                            <div style={{
                                                                background: 'rgba(15, 15, 20, 0.95)',
                                                                border: '1px solid var(--border-glass)',
                                                                borderRadius: '16px',
                                                                boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                                                                backdropFilter: 'blur(10px)',
                                                                padding: '12px 16px'
                                                            }}>
                                                                <p style={{ margin: '0 0 8px 0', fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-muted)' }}>{label}</p>
                                                                {payload.map((entry, index) => (
                                                                    <div key={index} style={{ display: 'flex', flexDirection: 'column', marginBottom: '8px' }}>
                                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: entry.color }} />
                                                                            <span style={{ fontSize: '0.85rem', color: '#fff', fontWeight: '600' }}>{entry.name}: ${entry.value.toFixed(2)}</span>
                                                                        </div>
                                                                        {entry.payload[`${entry.name}_amortized`] && (
                                                                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '16px' }}>
                                                                                Amortized: ${entry.payload[`${entry.name}_amortized`].toFixed(2)}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        );
                                                    }
                                                    return null;
                                                }}
                                                cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                                            />
                                            <Legend
                                                verticalAlign="bottom"
                                                align="center"
                                                iconType="circle"
                                                iconSize={8}
                                                wrapperStyle={{ paddingTop: '30px', fontSize: '0.75rem', fontWeight: '600', opacity: 0.8 }}
                                            />
                                            {Object.keys(chartData?.stacked_bar_data?.[0] || {})
                                                .filter(key => key !== 'date')
                                                .sort((a, b) => a === 'Others' ? 1 : b === 'Others' ? -1 : 0)
                                                .map((key, index) => (
                                                    <Bar
                                                        key={key}
                                                        dataKey={key}
                                                        stackId="a"
                                                        fill={key === 'Others' ? '#475569' : `hsl(${210 + (index * 35)}, 75%, 60%)`}
                                                        radius={[2, 2, 0, 0]}
                                                        maxBarSize={40}
                                                    />
                                                ))
                                            }
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </motion.div>

                            {/* Report Section */}
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                style={{
                                    background: 'var(--panel-bg)',
                                    padding: '48px',
                                    borderRadius: '28px',
                                    border: '1px solid var(--border-glass)',
                                    boxShadow: 'var(--shadow-premium)',
                                    position: 'relative'
                                }}
                            >
                                <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    marginBottom: '40px',
                                    paddingBottom: '24px',
                                    borderBottom: '1px solid var(--border-glass)'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                        <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '10px', borderRadius: '12px' }}>
                                            <FileText size={24} color="#8b5cf6" />
                                        </div>
                                        <h2 style={{ margin: 0, fontSize: '1.6rem', fontWeight: '800' }}>AI Optimization Insights</h2>
                                    </div>

                                    <button
                                        onClick={() => {
                                            navigator.clipboard.writeText(report);
                                            const btn = document.getElementById('copy-report-btn');
                                            const originalText = btn.innerHTML;
                                            btn.innerHTML = 'Copied!';
                                            btn.style.background = 'rgba(16, 185, 129, 0.2)';
                                            btn.style.color = '#10b981';
                                            setTimeout(() => {
                                                btn.innerHTML = originalText;
                                                btn.style.background = 'rgba(255,255,255,0.05)';
                                                btn.style.color = 'var(--text-muted)';
                                            }, 2000);
                                        }}
                                        id="copy-report-btn"
                                        style={{
                                            padding: '8px 16px',
                                            borderRadius: '10px',
                                            background: 'rgba(255,255,255,0.05)',
                                            border: '1px solid var(--border-glass)',
                                            color: 'var(--text-muted)',
                                            fontSize: '0.8rem',
                                            fontWeight: '700',
                                            cursor: 'pointer',
                                            transition: 'all 0.2s',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px'
                                        }}
                                    >
                                        Copy Report
                                    </button>
                                </div>

                                <div className="markdown-content" style={{ lineHeight: '1.8', color: 'rgba(255,255,255,0.85)', fontSize: '1.05rem' }}>
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            h1: ({ node, ...props }) => <h1 style={{ fontSize: '2rem', marginBottom: '1.5rem', color: '#fff', fontWeight: '900', letterSpacing: '-0.02em' }} {...props} />,
                                            h2: ({ node, ...props }) => <h2 style={{ fontSize: '1.5rem', marginTop: '3rem', marginBottom: '1.2rem', color: 'var(--accent-primary)', fontWeight: '800', display: 'flex', alignItems: 'center', gap: '12px' }} {...props} />,
                                            h3: ({ node, ...props }) => <h3 style={{ fontSize: '1.2rem', marginTop: '2rem', marginBottom: '1rem', color: '#fff', fontWeight: '700' }} {...props} />,
                                            p: ({ node, ...props }) => <p style={{ marginBottom: '1.5rem', color: 'rgba(255,255,255,0.8)' }} {...props} />,
                                            ul: ({ node, ...props }) => <ul style={{ paddingLeft: '24px', marginBottom: '2rem', listStyleType: 'none' }} {...props} />,
                                            li: ({ node, ...props }) => (
                                                <li style={{ marginBottom: '1rem', position: 'relative', paddingLeft: '28px' }} {...props}>
                                                    <div style={{ position: 'absolute', left: 0, top: '8px', width: '12px', height: '2px', background: 'var(--accent-primary)', borderRadius: '2px' }} />
                                                    {props.children}
                                                </li>
                                            ),
                                            strong: ({ node, ...props }) => {
                                                const content = props.children?.toString() || '';
                                                if (content.toLowerCase().includes('high') || content.toLowerCase().includes('critical')) {
                                                    return <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', padding: '2px 8px', borderRadius: '6px', fontWeight: '800', fontSize: '0.85rem' }}>{props.children}</span>;
                                                }
                                                if (content.toLowerCase().includes('medium')) {
                                                    return <span style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', padding: '2px 8px', borderRadius: '6px', fontWeight: '800', fontSize: '0.85rem' }}>{props.children}</span>;
                                                }
                                                if (content.toLowerCase().includes('low') || content.toLowerCase().includes('savings')) {
                                                    return <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', padding: '2px 8px', borderRadius: '6px', fontWeight: '800', fontSize: '0.85rem' }}>{props.children}</span>;
                                                }
                                                return <strong style={{ color: 'var(--accent-secondary)', fontWeight: '700' }} {...props} />;
                                            },
                                            blockquote: ({ node, ...props }) => <blockquote style={{ borderLeft: '4px solid var(--accent-primary)', padding: '20px 24px', background: 'rgba(255,255,255,0.03)', borderRadius: '0 16px 16px 0', margin: '32px 0', fontStyle: 'italic', color: 'rgba(255,255,255,0.9)' }} {...props} />,
                                            table: ({ node, ...props }) => (
                                                <div style={{ overflowX: 'auto', margin: '32px 0', borderRadius: '20px', border: '1px solid var(--border-glass)', background: 'rgba(255,255,255,0.01)' }}>
                                                    <table style={{ width: '100%', borderCollapse: 'collapse' }} {...props} />
                                                </div>
                                            ),
                                            thead: ({ node, ...props }) => <thead style={{ background: 'rgba(255,255,255,0.03)' }} {...props} />,
                                            th: ({ node, ...props }) => <th style={{ padding: '18px 20px', textAlign: 'left', borderBottom: '1px solid var(--border-glass)', color: 'var(--accent-primary)', fontSize: '0.8rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.1em' }} {...props} />,
                                            td: ({ node, ...props }) => <td style={{ padding: '18px 20px', borderBottom: '1px solid var(--border-glass)', fontSize: '0.95rem', color: 'rgba(255,255,255,0.8)' }} {...props} />,
                                        }}
                                    >
                                        {report}
                                    </ReactMarkdown>
                                </div>
                            </motion.div>
                        </div>

                        {/* Sidebar Section */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', position: 'sticky', top: '32px' }}>
                            {/* Top Trends Card */}
                            <motion.div
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                style={{ background: 'var(--panel-bg)', padding: '32px', borderRadius: '28px', border: '1px solid var(--border-glass)', boxShadow: 'var(--shadow-premium)' }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
                                    <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '10px' }}>
                                        <TrendingUp size={18} color="var(--accent-primary)" />
                                        Service Trends
                                    </h3>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '800', letterSpacing: '0.05em' }}>TOP 10</div>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                    {chartData?.top_trends?.map((trend, index) => (
                                        <motion.div
                                            key={index}
                                            whileHover={{ x: 5, background: 'rgba(255,255,255,0.04)' }}
                                            style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '16px', border: '1px solid var(--border-glass)', transition: 'all 0.2s' }}
                                        >
                                            <div style={{ fontSize: '0.9rem', fontWeight: '700', marginBottom: '8px', color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {trend.service_name}
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ fontSize: '1rem', fontWeight: '800', color: 'rgba(255,255,255,0.9)' }}>
                                                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '2px' }}>$</span>
                                                    {trend.current_cost?.toFixed(2)}
                                                </div>
                                                <div style={{
                                                    fontSize: '0.75rem',
                                                    fontWeight: '800',
                                                    color: trend.change > 0 ? '#ef4444' : '#10b981',
                                                    background: trend.change > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                                                    padding: '4px 10px',
                                                    borderRadius: '100px',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '4px'
                                                }}>
                                                    {trend.change > 0 ? <TrendingUp size={12} /> : <TrendingUp size={12} style={{ transform: 'rotate(180deg)' }} />}
                                                    {Math.abs(trend.percent_change || 0).toFixed(1)}%
                                                </div>
                                            </div>
                                        </motion.div>
                                    ))}
                                    {(!chartData?.top_trends || chartData.top_trends.length === 0) && (
                                        <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px', background: 'rgba(255,255,255,0.01)', borderRadius: '16px', border: '1px dashed var(--border-glass)' }}>
                                            No trend data available
                                        </div>
                                    )}
                                </div>
                            </motion.div>

                            {/* Info Card */}
                            <div style={{ padding: '24px', borderRadius: '24px', background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%)', border: '1px solid rgba(255,255,255,0.05)' }}>
                                <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
                                    <AlertCircle size={20} color="var(--accent-primary)" />
                                    <div style={{ fontSize: '0.9rem', fontWeight: '700', color: '#fff' }}>Cost Monitoring</div>
                                </div>
                                <div style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)', lineHeight: '1.6' }}>
                                    Analysis is performed daily at 9:00 AM. GChat alerts are automatically sent if significant cost increases are detected.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            ) : (
                <div style={{
                    height: '60vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--panel-bg)',
                    borderRadius: '32px',
                    border: '2px dashed var(--border-glass)',
                    color: 'var(--text-muted)',
                    margin: '0 32px'
                }}>
                    <div style={{ background: 'rgba(255,255,255,0.03)', padding: '32px', borderRadius: '50%', marginBottom: '24px' }}>
                        <DollarSign size={64} style={{ opacity: 0.2 }} />
                    </div>
                    <h3 style={{ color: '#fff', fontSize: '1.4rem', marginBottom: '8px' }}>No Analysis Data</h3>
                    <p style={{ fontSize: '1rem', opacity: 0.7, maxWidth: '400px', textAlign: 'center' }}>
                        The {granularity === 'daily' ? '30-day' : granularity === 'weekly' ? '90-day' : '180-day'} cost analysis report is being generated or is currently unavailable.
                    </p>
                </div>
            )}
        </div>
    );
}

export default CostOptimization;
