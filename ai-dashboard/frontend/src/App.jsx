import React, { useState, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Sparkles, Activity, Terminal, BarChart3,
  ChevronRight, Search, Filter, Shield, Cpu,
  Layers, Zap, AlertCircle, Clock, CheckCircle2,
  LayoutDashboard, Bell, Ticket, MoreHorizontal, ChevronDown
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import ReactMarkdown from 'react-markdown';
import { useAuth } from './AuthContext';
import Login from './Login';
import CostOptimization from './components/CostOptimization';
import { LogOut, DollarSign } from 'lucide-react';
const API_BASE = ''; // Same origin
const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#ef4444', '#f59e0b', '#10b981', '#6366f1', '#64748b'];
const CATEGORIES = [
  { id: 'application', name: 'Application', icon: Zap },
  { id: 'infrastructure', name: 'Infrastructure', icon: Cpu },
  { id: 'distributed', name: 'Distributed', icon: Layers },
  { id: 'security', name: 'Security', icon: Shield },
  { id: 'performance', name: 'Performance', icon: Activity },
  { id: 'ci/cd', name: 'CI/CD', icon: Terminal },
  { id: 'data pipelines', name: 'Data Pipelines', icon: BarChart3 },
];
const NAV_ITEMS = [
  { id: 'all', name: 'All Insights', icon: LayoutDashboard },
  { id: 'tickets', name: 'Tickets', icon: Ticket },
];
const SUGGESTED_QUESTIONS = [
  "Summarize recent security risks",
  "What is the most common error category?",
  "Explain the blast radius of the last timeout",
  "Are there any performance trends?"
];
function App() {
  const { user, token, logout, loading } = useAuth();
  const [insights, setInsights] = useState([]);
  const [analytics, setAnalytics] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [costSummary, setCostSummary] = useState(null);
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Hello! I am your AI SRE assistant. I have access to your recent logs and insights. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');
  const [activeDropdownId, setActiveDropdownId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [insightSort, setInsightSort] = useState('newest'); // newest, oldest, frequent
  const [ticketSort, setTicketSort] = useState('newest'); // newest, oldest, frequent, status
  const [ticketStatusFilter, setTicketStatusFilter] = useState('all'); // all, OPEN, IN_PROGRESS, RESOLVED
  const chatEndRef = useRef(null);

  const [activeView, setActiveView] = useState('dashboard'); // 'dashboard', 'cost-optimization'
  const [showChat, setShowChat] = useState(true);
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);
  useEffect(() => {
    if (user) {
      fetchData();
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    }
  }, [user]);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.custom-dropdown')) {
        setActiveDropdownId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  const fetchData = async () => {
    try {
      const [insightsResp, analyticsResp, ticketsResp, costResp] = await Promise.all([
        axios.get(`${API_BASE}/insights`),
        axios.get(`${API_BASE}/analytics`),
        axios.get(`${API_BASE}/tickets`),
        axios.get(`${API_BASE}/get-last-cost-analysis?granularity=daily`).catch(() => ({ data: null }))
      ]);
      setInsights(insightsResp.data);
      setAnalytics(analyticsResp.data);
      setTickets(ticketsResp.data);
      if (costResp && costResp.data) {
        setCostSummary(costResp.data);
      }
    } catch (err) {
      console.error('Error fetching data:', err);
      if (err.response && err.response.status === 401) {
        logout();
      }
    }
  };
  const handleSend = async (text = input) => {
    const queryText = typeof text === 'string' ? text : input;
    if (!queryText.trim()) return;
    const userMsg = { role: 'user', content: queryText };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);
    try {
      const resp = await axios.post(`${API_BASE}/query`, { query: queryText });
      setMessages(prev => [...prev, { role: 'ai', content: resp.data.answer }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: 'Sorry, I encountered an error while processing your request.' }]);
    } finally {
      setIsTyping(false);
    }
  };
  const handleTicketStatusUpdate = async (ticketId, newStatus) => {
    try {
      await axios.post(`${API_BASE}/tickets/${encodeURIComponent(ticketId)}/status`, { status: newStatus });
      // Optimistic update
      setTickets(prev => prev.map(t => t.id === ticketId ? { ...t, status: newStatus } : t));
    } catch (err) {
      console.error('Error updating ticket status:', err);
      alert('Failed to update ticket status');
    }
  };
  const filteredInsights = useMemo(() => {
    let result = insights.filter(insight => {
      const category = insight.category || 'default';
      const matchesFilter = activeFilter === 'all' || category.toLowerCase().includes(activeFilter);
      // Handle details as object or string for search
      const detailsStr = typeof insight.details === 'object' ?
        JSON.stringify(insight.details).toLowerCase() :
        String(insight.details || '').toLowerCase();
      const summary = insight.summary || '';
      const matchesSearch = summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
        detailsStr.includes(searchQuery.toLowerCase());
      return matchesFilter && matchesSearch;
    });
    // Apply Sorting
    return [...result].sort((a, b) => {
      const timeA = parseInt(a.last_seen || a.timestamp) || 0;
      const timeB = parseInt(b.last_seen || b.timestamp) || 0;
      if (insightSort === 'newest') return timeB - timeA;
      if (insightSort === 'oldest') return timeA - timeB;
      if (insightSort === 'frequent') return (b.count || 1) - (a.count || 1);
      if (insightSort === 'first_seen') {
        const firstA = parseInt(a.first_seen) || timeA;
        const firstB = parseInt(b.first_seen) || timeB;
        return firstA - firstB;
      }
      return 0;
    });
  }, [insights, activeFilter, searchQuery, insightSort]);
  const filteredTickets = useMemo(() => {
    let result = tickets.filter(ticket => {
      const matchesStatus = ticketStatusFilter === 'all' || ticket.status === ticketStatusFilter;
      const title = ticket.title || '';
      const description = ticket.description || '';
      const matchesSearch = title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesStatus && matchesSearch;
    });
    // Apply Sorting
    return [...result].sort((a, b) => {
      const timeA = parseInt(a.updated_at || a.created_at) || 0;
      const timeB = parseInt(b.updated_at || b.created_at) || 0;
      if (ticketSort === 'newest') return timeB - timeA;
      if (ticketSort === 'oldest') return timeA - timeB;
      if (ticketSort === 'frequent') return (b.occurrences || 1) - (a.occurrences || 1);
      if (ticketSort === 'first_seen') {
        const firstA = parseInt(a.first_seen) || timeA;
        const firstB = parseInt(b.first_seen) || timeB;
        return firstA - firstB;
      }
      if (ticketSort === 'status') {
        const statusOrder = { 'OPEN': 0, 'IN_PROGRESS': 1, 'REOPENED': 2, 'RESOLVED': 3 };
        return (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99);
      }
      return 0;
    });
  }, [tickets, searchQuery, ticketSort, ticketStatusFilter]);
  const criticalCount = insights.filter(i => {
    const cat = (i.category || '').toLowerCase();
    return cat.includes('security') || cat.includes('distributed');
  }).length;
  if (loading) {
    console.log('App is loading...');
    return (
      <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: 'var(--bg-color)', color: 'var(--accent-primary)' }}>
        <Zap size={48} className="animate-pulse" />
      </div>
    );
  }
  if (!user) {
    console.log('No user, rendering Login');
    return <Login />;
  }
  console.log('User authenticated, rendering Dashboard', user);
  const getCategoryStyles = (category) => {
    const cat = (category || '').toLowerCase();
    if (cat.includes('application')) return { color: 'var(--cat-application)', bg: 'rgba(59, 130, 246, 0.1)' };
    if (cat.includes('infrastructure')) return { color: 'var(--cat-infrastructure)', bg: 'rgba(139, 92, 246, 0.1)' };
    if (cat.includes('distributed')) return { color: 'var(--cat-distributed)', bg: 'rgba(236, 72, 153, 0.1)' };
    if (cat.includes('security')) return { color: 'var(--cat-security)', bg: 'rgba(239, 68, 68, 0.1)' };
    if (cat.includes('performance')) return { color: 'var(--cat-performance)', bg: 'rgba(245, 158, 11, 0.1)' };
    if (cat.includes('ci/cd')) return { color: 'var(--cat-cicd)', bg: 'rgba(16, 185, 129, 0.1)' };
    if (cat.includes('data pipelines')) return { color: 'var(--cat-data)', bg: 'rgba(99, 102, 241, 0.1)' };
    return { color: 'var(--cat-default)', bg: 'rgba(100, 116, 139, 0.1)' };
  };
  const getStatusColor = (status) => {
    switch (status) {
      case 'OPEN': return '#ef4444';
      case 'IN_PROGRESS': return '#f59e0b';
      case 'RESOLVED': return '#10b981';
      case 'REOPENED': return '#ec4899';
      default: return '#64748b';
    }
  };
  const getProgressWidth = (status) => {
    switch (status) {
      case 'OPEN': return '33%';
      case 'IN_PROGRESS': return '66%';
      case 'RESOLVED': return '100%';
      case 'REOPENED': return '50%';
      default: return '0%';
    }
  };

  return (
    <div className={`app-layout ${!showChat ? 'hide-chat' : ''}`}>
      {/* Header */}
      <header className="app-header">
        <div className="logo-section">
          <motion.div
            animate={{ rotate: [0, 10, 0] }}
            transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
          >
            <Zap color="var(--accent-primary)" fill="var(--accent-primary)" size={32} />
          </motion.div>
          <h1 className="logo-text">AetherCost</h1>
        </div>
        <div className="header-metrics">
          <div className="metric-item">
            <span className="metric-label">Total Insights</span>
            <motion.span
              key={insights.length}
              initial={{ scale: 1.5, color: 'var(--accent-primary)' }}
              animate={{ scale: 1, color: 'var(--text-main)' }}
              className="metric-value"
            >
              {insights.length}
            </motion.span>
          </div>
          <div className="metric-item">
            <span className="metric-label">Active Tickets</span>
            <span className="metric-value" style={{ color: '#f59e0b' }}>{tickets.filter(t => t.status !== 'RESOLVED').length}</span>
          </div>
          <div className="metric-item">
            <span className="metric-label">System Status</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="live-dot" />
              <span className="metric-value" style={{ color: 'var(--accent-primary)', fontSize: '0.9rem' }}>LIVE</span>
            </div>
          </div>
          <div className="header-actions" style={{ marginLeft: '20px', paddingLeft: '20px', borderLeft: '1px solid var(--border-glass)' }}>
            <motion.button
              whileHover={{ scale: 1.05, background: 'rgba(255,255,255,0.05)' }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowChat(!showChat)}
              className={`chat-toggle-btn ${showChat ? 'active' : ''}`}
              title={showChat ? "Hide AI Assistant" : "Show AI Assistant"}
              style={{
                background: showChat ? 'rgba(0, 242, 255, 0.1)' : 'transparent',
                border: '1px solid var(--border-glass)',
                borderRadius: '12px',
                padding: '10px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: showChat ? 'var(--accent-primary)' : 'var(--text-muted)',
                transition: 'all 0.3s ease'
              }}
            >
              <Sparkles size={20} />
            </motion.button>
          </div>
        </div>
      </header>
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div className="sidebar-section">
          <div className="filter-list" style={{ gap: '8px' }}>
            {NAV_ITEMS.map(item => (
              <motion.div
                key={item.id}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className={`filter-item ${activeFilter === item.id ? 'active' : ''}`}
                onClick={() => {
                  setActiveFilter(item.id);
                  setActiveView('dashboard');
                }}
                style={{
                  background: activeFilter === item.id ? 'rgba(6, 182, 212, 0.1)' : 'transparent',
                  border: activeFilter === item.id ? '1px solid rgba(6, 182, 212, 0.2)' : '1px solid transparent',
                  borderRadius: '12px',
                  padding: '12px 16px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <item.icon size={20} color={activeFilter === item.id ? 'var(--accent-primary)' : 'var(--text-muted)'} />
                  <span style={{
                    fontWeight: activeFilter === item.id ? '700' : '500',
                    color: activeFilter === item.id ? 'var(--accent-primary)' : 'var(--text-muted)'
                  }}>
                    {item.name}
                  </span>
                </div>
                <span className="filter-count" style={{
                  background: activeFilter === item.id ? 'rgba(6, 182, 212, 0.2)' : 'rgba(255,255,255,0.05)',
                  color: activeFilter === item.id ? 'var(--accent-primary)' : 'var(--text-muted)'
                }}>
                  {item.id === 'all' ? insights.length : tickets.filter(t => t.status !== 'RESOLVED').length}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
        <div className="sidebar-section">
          <h3>Intelligence</h3>
          <div className="filter-list">
            {CATEGORIES.map(cat => (
              <motion.div
                key={cat.id}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className={`filter-item ${activeFilter === cat.id ? 'active' : ''}`}
                onClick={() => {
                  setActiveFilter(cat.id);
                  setActiveView('dashboard');
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <cat.icon size={20} />
                  <span style={{ fontWeight: activeFilter === cat.id ? '700' : '500' }}>{cat.name}</span>
                </div>
                <span className="filter-count">
                  {cat.id === 'all' ? insights.length :
                    cat.id === 'tickets' ? tickets.filter(t => t.status !== 'RESOLVED').length :
                      insights.filter(i => (i.category || '').toLowerCase().includes(cat.id)).length}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
        <div className="sidebar-section">
          <h3>Tools</h3>
          <div className="filter-list">
            <motion.div
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.98 }}
              className={`filter-item ${activeView === 'cost-optimization' ? 'active' : ''}`}
              onClick={() => setActiveView('cost-optimization')}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <DollarSign size={20} />
                <span style={{ fontWeight: activeView === 'cost-optimization' ? '700' : '500' }}>Cost Optimization</span>
              </div>
            </motion.div>
          </div>
        </div>
        <div className="sidebar-section" style={{ marginTop: 'auto' }}>
          <div className="filter-item" onClick={logout} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <LogOut size={20} color="#ef4444" />
              <span style={{ color: '#ef4444' }}>Logout</span>
            </div>
          </div>
        </div>
      </aside>
      {/* Main Content */}
      <main className="main-content">
        {activeView === 'cost-optimization' ? (
          <CostOptimization onBack={() => setActiveView('dashboard')} />
        ) : (
          <>
            <div className="section-title">
              <h2>{activeFilter === 'tickets' ? 'Error Tickets' : 'Intelligence Overview'}</h2>
              <div style={{ position: 'relative' }}>
                <Search size={20} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', opacity: 0.5 }} />
                <input
                  type="text"
                  placeholder={activeFilter === 'tickets' ? "Search tickets..." : "Search insights..."}
                  style={{
                    width: '340px', paddingLeft: '48px', height: '48px',
                    background: 'var(--panel-bg)', border: '1px solid var(--border-glass)',
                    borderRadius: '16px', color: '#fff', outline: 'none',
                    fontSize: '0.95rem', backdropFilter: 'blur(10px)'
                  }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              {/* Sorting and Filtering Controls */}
              <div style={{ display: 'flex', gap: '12px' }}>
                {activeFilter === 'tickets' ? (
                  <>
                    <div className="custom-dropdown">
                      <div
                        className="dropdown-trigger"
                        onClick={() => setActiveDropdownId(activeDropdownId === 'ticket-status-filter' ? null : 'ticket-status-filter')}
                      >
                        <Filter size={16} color="var(--accent-primary)" />
                        <span>{ticketStatusFilter === 'all' ? 'All Status' : ticketStatusFilter.replace('_', ' ')}</span>
                        <ChevronDown size={16} color="var(--accent-primary)" />
                      </div>
                      <AnimatePresence>
                        {activeDropdownId === 'ticket-status-filter' && (
                          <motion.div
                            className="dropdown-options"
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                          >
                            {['all', 'OPEN', 'IN_PROGRESS', 'RESOLVED'].map(status => (
                              <div
                                key={status}
                                className={`dropdown-option ${ticketStatusFilter === status ? 'active' : ''}`}
                                onClick={() => {
                                  setTicketStatusFilter(status);
                                  setActiveDropdownId(null);
                                }}
                              >
                                {status === 'all' ? 'All Status' : status.replace('_', ' ')}
                              </div>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                    <div className="custom-dropdown">
                      <div
                        className="dropdown-trigger"
                        onClick={() => setActiveDropdownId(activeDropdownId === 'ticket-sort' ? null : 'ticket-sort')}
                      >
                        <BarChart3 size={16} color="var(--accent-primary)" />
                        <span>Sort: {ticketSort.charAt(0).toUpperCase() + ticketSort.slice(1)}</span>
                        <ChevronDown size={16} color="var(--accent-primary)" />
                      </div>
                      <AnimatePresence>
                        {activeDropdownId === 'ticket-sort' && (
                          <motion.div
                            className="dropdown-options"
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                          >
                            {[
                              { id: 'newest', label: 'Newest' },
                              { id: 'oldest', label: 'Oldest' },
                              { id: 'first_seen', label: 'First Seen' },
                              { id: 'frequent', label: 'Most Frequent' },
                              { id: 'status', label: 'Status' }
                            ].map(opt => (
                              <div
                                key={opt.id}
                                className={`dropdown-option ${ticketSort === opt.id ? 'active' : ''}`}
                                onClick={() => {
                                  setTicketSort(opt.id);
                                  setActiveDropdownId(null);
                                }}
                              >
                                {opt.label}
                              </div>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </>
                ) : (
                  <div className="custom-dropdown">
                    <div
                      className="dropdown-trigger"
                      onClick={() => setActiveDropdownId(activeDropdownId === 'insight-sort' ? null : 'insight-sort')}
                    >
                      <BarChart3 size={16} color="var(--accent-primary)" />
                      <span>Sort: {insightSort.charAt(0).toUpperCase() + insightSort.slice(1)}</span>
                      <ChevronDown size={16} color="var(--accent-primary)" />
                    </div>
                    <AnimatePresence>
                      {activeDropdownId === 'insight-sort' && (
                        <motion.div
                          className="dropdown-options"
                          initial={{ opacity: 0, y: -10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                        >
                          {[
                            { id: 'newest', label: 'Newest' },
                            { id: 'oldest', label: 'Oldest' },
                            { id: 'first_seen', label: 'First Seen' },
                            { id: 'frequent', label: 'Most Frequent' }
                          ].map(opt => (
                            <div
                              key={opt.id}
                              className={`dropdown-option ${insightSort === opt.id ? 'active' : ''}`}
                              onClick={() => {
                                setInsightSort(opt.id);
                                setActiveDropdownId(null);
                              }}
                            >
                              {opt.label}
                            </div>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </div>
            </div>
            {
              activeFilter !== 'tickets' && (
                <div className="analytics-grid">
                  <div className="chart-card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: '700', letterSpacing: '0.05em' }}>
                      <BarChart3 size={18} color="var(--accent-primary)" />
                      <span>CATEGORY DISTRIBUTION</span>
                    </div>
                    <ResponsiveContainer width="100%" height="85%">
                      <PieChart>
                        <Pie
                          data={analytics}
                          cx="50%"
                          cy="45%"
                          innerRadius={60}
                          outerRadius={90}
                          paddingAngle={8}
                          dataKey="value"
                          stroke="none"
                          cornerRadius={6}
                        >
                          {analytics.map((entry, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={COLORS[index % COLORS.length]}
                              style={{ filter: `drop-shadow(0 0 8px ${COLORS[index % COLORS.length]}44)` }}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            background: 'rgba(10, 10, 15, 0.95)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '16px',
                            boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
                            backdropFilter: 'blur(10px)',
                            padding: '12px 16px'
                          }}
                          itemStyle={{ color: '#fff', fontWeight: '600' }}
                        />
                        <Legend
                          verticalAlign="bottom"
                          align="center"
                          iconType="circle"
                          iconSize={10}
                          wrapperStyle={{ paddingTop: '20px' }}
                          formatter={(value) => <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: '700', letterSpacing: '0.05em' }}>{(value || '').toUpperCase()}</span>}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="chart-card" style={{ cursor: 'pointer' }} onClick={() => setActiveView('cost-optimization')}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', fontSize: '0.85rem', fontWeight: '700', letterSpacing: '0.05em' }}>
                        <DollarSign size={18} color="var(--accent-primary)" />
                        <span>COST OVERVIEW</span>
                      </div>
                      <ChevronRight size={16} color="var(--text-muted)" />
                    </div>

                    {costSummary ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%', justifyContent: 'center' }}>
                        <div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600', marginBottom: '4px' }}>AMORTIZED COST (DAILY)</div>
                          <div style={{ fontSize: '2.2rem', fontWeight: '900', color: '#fff' }}>
                            <span style={{ fontSize: '1.2rem', color: 'var(--accent-primary)', marginRight: '4px' }}>$</span>
                            {(costSummary.metadata?.total_amortized_cost || costSummary.total_account_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '12px' }}>
                          <div style={{ flex: 1, background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border-glass)' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '700', marginBottom: '4px' }}>HEALTH</div>
                            <div style={{ fontSize: '1.1rem', fontWeight: '800', color: costSummary.metadata?.is_complete ? '#10b981' : '#f59e0b' }}>
                              {costSummary.metadata?.is_complete ? '92' : '85'}<span style={{ fontSize: '0.8rem', opacity: 0.5 }}>/100</span>
                            </div>
                          </div>
                          <div style={{ flex: 1, background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '12px', border: '1px solid var(--border-glass)' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: '700', marginBottom: '4px' }}>SAVINGS</div>
                            <div style={{ fontSize: '1.1rem', fontWeight: '800', color: 'var(--accent-secondary)' }}>
                              ${((costSummary.metadata?.total_amortized_cost || costSummary.total_account_cost || 0) * 0.15).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </div>
                          </div>
                        </div>

                        {costSummary.report?.includes("Failed to fetch") && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '0.75rem', fontWeight: '600', background: 'rgba(239, 68, 68, 0.1)', padding: '8px 12px', borderRadius: '10px' }}>
                            <AlertCircle size={14} />
                            AWS Credentials Required
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        Loading cost data...
                      </div>
                    )}
                  </div>
                </div>
              )
            }
            <div className="section-title" style={{ marginTop: '16px' }}>
              <h2>{activeFilter === 'tickets' ? 'All Tickets' : 'Recent Insights'}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div className="live-dot" style={{ animationDelay: '0.5s' }} />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                  Monitoring {activeFilter === 'tickets' ? filteredTickets.length : filteredInsights.length} active signals
                </span>
              </div>
            </div>
            <div className="insights-list">
              <AnimatePresence>
                {activeFilter === 'tickets' ? (
                  filteredTickets.map((ticket, i) => {
                    const styles = getCategoryStyles(ticket.category);
                    return (
                      <motion.div
                        key={ticket.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ delay: i * 0.05 }}
                        className="insight-card"
                        style={{
                          '--cat-color': styles.color,
                          '--cat-bg': styles.bg,
                          zIndex: activeDropdownId === ticket.id ? 1000 : 1,
                          overflow: activeDropdownId === ticket.id ? 'visible' : 'hidden'
                        }}
                      >
                        <div className="card-header">
                          <span className="category-badge">{ticket.category}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.05)', padding: '4px 12px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '800', color: 'var(--accent-primary)' }}>
                              <Activity size={14} />
                              {ticket.occurrences} EVENTS
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Clock size={14} color="var(--text-muted)" />
                              <span className="timestamp">
                                {(() => {
                                  const ts = parseInt(ticket.updated_at || ticket.created_at);
                                  return isNaN(ts) ? 'Just now' : new Date(ts / 1000000).toLocaleTimeString();
                                })()}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="summary-text">
                          {ticket.title}
                        </div>
                        <div className="insight-blocks">
                          <div className="insight-block">
                            <div className="block-label"><Ticket size={14} /> Status Control</div>
                            <div className="block-content" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                              <span style={{
                                color: getStatusColor(ticket.status),
                                fontWeight: '800',
                                display: 'flex', alignItems: 'center', gap: '8px',
                                fontSize: '0.85rem'
                              }}>
                                <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: getStatusColor(ticket.status), boxShadow: `0 0 10px ${getStatusColor(ticket.status)}` }} />
                                {ticket.status}
                              </span>
                              <div className="custom-dropdown">
                                <div
                                  className="dropdown-trigger"
                                  onClick={() => setActiveDropdownId(activeDropdownId === ticket.id ? null : ticket.id)}
                                >
                                  <span>{ticket.status}</span>
                                  <ChevronDown size={16} color="var(--accent-primary)" />
                                </div>
                                <AnimatePresence>
                                  {activeDropdownId === ticket.id && (
                                    <motion.div
                                      className="dropdown-options"
                                      initial={{ opacity: 0, y: -10 }}
                                      animate={{ opacity: 1, y: 0 }}
                                      exit={{ opacity: 0, y: -10 }}
                                    >
                                      {['OPEN', 'IN_PROGRESS', 'RESOLVED'].map(status => (
                                        <div
                                          key={status}
                                          className={`dropdown-option ${ticket.status === status ? 'active' : ''}`}
                                          onClick={() => {
                                            handleTicketStatusUpdate(ticket.id, status);
                                            setActiveDropdownId(null);
                                          }}
                                        >
                                          {status.replace('_', ' ')}
                                        </div>
                                      ))}
                                    </motion.div>
                                  )}
                                </AnimatePresence>
                              </div>
                            </div>
                          </div>
                          <div className="insight-block" style={{ marginTop: '12px' }}>
                            <div className="block-label"><Clock size={14} /> Incident History</div>
                            <div className="block-content" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              First Seen: {(() => {
                                const ts = parseInt(ticket.first_seen);
                                return isNaN(ts) ? 'Unknown' : new Date(ts / 1000000).toLocaleString();
                              })()}
                              {ticket.incident_timings && ticket.incident_timings.length > 1 && (
                                <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                  {ticket.incident_timings.slice(-5).reverse().map((ts, idx) => (
                                    <span key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                                      {new Date(parseInt(ts) / 1000000).toLocaleTimeString()}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="progress-container">
                            <motion.div
                              className="progress-bar"
                              initial={{ width: 0 }}
                              animate={{ width: getProgressWidth(ticket.status) }}
                            />
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                ) : (
                  filteredInsights.map((insight, i) => {
                    const styles = getCategoryStyles(insight.category);
                    return (
                      <motion.div
                        key={(insight.last_seen || insight.timestamp) + i}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ delay: i * 0.05 }}
                        className="insight-card"
                        style={{ '--cat-color': styles.color, '--cat-bg': styles.bg }}
                      >
                        <div className="card-header">
                          <span className="category-badge">{insight.category}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            {insight.count > 1 && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.05)', padding: '4px 12px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: '800', color: 'var(--accent-primary)' }}>
                                <Activity size={14} />
                                {insight.count} SIGNALS
                              </div>
                            )}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Clock size={14} color="var(--text-muted)" />
                              <span className="timestamp">
                                {(() => {
                                  const ts = parseInt(insight.last_seen || insight.timestamp);
                                  return isNaN(ts) ? 'Just now' : new Date(ts / 1000000).toLocaleTimeString();
                                })()}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="summary-text">
                          {(insight.summary || '').replace(/\*\*/g, '')}
                        </div>
                        {insight.details && typeof insight.details === 'object' && (
                          <div className="insight-blocks">
                            {insight.details.root_cause && (
                              <div className="insight-block">
                                <div className="block-label"><AlertCircle size={14} /> Root Cause Analysis</div>
                                <div className="block-content">{insight.details.root_cause}</div>
                              </div>
                            )}
                            {insight.details.blast_radius && (
                              <div className="insight-block">
                                <div className="block-label"><Layers size={14} /> Impact Radius</div>
                                <div className="block-content">{insight.details.blast_radius}</div>
                              </div>
                            )}
                            {insight.details.actionable_fix && (
                              <div className="insight-block">
                                <div className="block-label"><CheckCircle2 size={14} /> Recommended Action</div>
                                <div className="block-content" style={{ color: 'var(--text-main)', fontWeight: '500' }}>{insight.details.actionable_fix}</div>
                              </div>
                            )}
                            <div className="insight-block">
                              <div className="block-label"><Clock size={14} /> Incident History</div>
                              <div className="block-content" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                First Seen: {(() => {
                                  const ts = parseInt(insight.first_seen);
                                  return isNaN(ts) ? 'Unknown' : new Date(ts / 1000000).toLocaleString();
                                })()}
                                {insight.incident_timings && insight.incident_timings.length > 1 && (
                                  <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                    {insight.incident_timings.slice(-5).reverse().map((ts, idx) => (
                                      <span key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                                        {new Date(parseInt(ts) / 1000000).toLocaleTimeString()}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
              {((activeFilter === 'tickets' && filteredTickets.length === 0) || (activeFilter !== 'tickets' && filteredInsights.length === 0)) && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  style={{ textAlign: 'center', padding: '100px', color: 'var(--text-muted)' }}
                >
                  <Activity size={64} style={{ opacity: 0.1, marginBottom: '24px' }} />
                  <p style={{ fontSize: '1.1rem', fontWeight: '500' }}>No active signals detected in this category.</p>
                </motion.div>
              )}
            </div>
          </>
        )}
      </main>
      {/* Chat Panel */}
      <AnimatePresence>
        {showChat && (
          <motion.aside
            initial={{ x: 420, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 420, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="chat-panel"
          >
            <div className="panel-header" style={{ padding: '32px', borderBottom: '1px solid var(--border-glass)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <Sparkles color="var(--accent-primary)" size={28} />
                <h2 style={{ fontSize: '1.4rem', fontWeight: '700' }}>AI Assistant</h2>
              </div>
            </div>
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`msg ${msg.role}`}
                >
                  {msg.role === 'ai' ? (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </motion.div>
              ))}
              {isTyping && (
                <div className="msg ai" style={{ opacity: 0.6 }}>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1 }}>.</motion.span>
                    <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }}>.</motion.span>
                    <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }}>.</motion.span>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            <div className="chat-footer">
              <div className="suggestions">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <motion.div
                    key={i}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="suggest-chip"
                    onClick={() => handleSend(q)}
                  >
                    {q}
                  </motion.div>
                ))}
              </div>
              <div className="input-box" style={{ gap: '16px' }}>
                <input
                  placeholder="Query system intelligence..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                />
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  className="send-button"
                  onClick={handleSend}
                >
                  <Sparkles size={24} color="#000" />
                </motion.button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div >
  );
}
export default App;