import React, { useContext } from 'react'
import { Routes, Route, NavLink, useLocation, Navigate } from 'react-router-dom'
import { AuthProvider, AuthContext } from './context/AuthContext.jsx'
import Upload from './pages/Upload.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Report from './pages/Report.jsx'
import Home from './pages/Home.jsx'
import ComplaintLetter from './pages/ComplaintLetter.jsx'
import HistoryPage from './pages/History.jsx'
import Login from './pages/Login.jsx'
import Pricing from './pages/Pricing.jsx'
import { LogOut, User, Search } from 'lucide-react'

function Navbar() {
  const { user, logout } = useContext(AuthContext);

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <NavLink to="/" className="navbar-brand" style={{ textDecoration: 'none' }}>
          <div className="logo-dot" />
          BillGuard <span style={{ color: 'var(--teal-400)' }}>AI</span>
        </NavLink>
        <div className="navbar-nav" style={{ alignItems: 'center' }}>
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Home</NavLink>
          <NavLink to="/pricing" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Search size={14} /> Price Finder
          </NavLink>
          {user && (
            <>
              <NavLink to="/upload" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Analyze Bill</NavLink>
              <NavLink to="/history" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>History</NavLink>
              
              <div style={{ width: '1px', height: '20px', backgroundColor: 'var(--border-color)', margin: '0 0.5rem' }}></div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                <User size={14} />
                <span className="truncate" style={{ maxWidth: '120px' }}>{user.email}</span>
                <button onClick={logout} className="btn btn-ghost btn-sm" style={{ padding: '0.4rem', color: 'var(--text-muted)' }} title="Sign out">
                  <LogOut size={16} />
                </button>
              </div>
            </>
          )}
          {!user && (
            <NavLink to="/login" className="btn btn-primary btn-sm" style={{ padding: '0.4rem 1rem' }}>Sign In</NavLink>
          )}
        </div>
      </div>
    </nav>
  )
}

function ProtectedRoute({ children }) {
  const { user } = useContext(AuthContext);
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <Navbar />
      <Routes>
        <Route path="/"                        element={<Home />} />
        <Route path="/login"                   element={<Login />} />
        <Route path="/pricing"                 element={<Pricing />} />
        
        {/* Protected Routes */}
        <Route path="/upload"                  element={<ProtectedRoute><Upload /></ProtectedRoute>} />
        <Route path="/dashboard"               element={<Navigate to="/history" replace />} />
        <Route path="/dashboard/:jobId"        element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/report/:jobId"           element={<ProtectedRoute><Report /></ProtectedRoute>} />
        <Route path="/complaint/:jobId"        element={<ProtectedRoute><ComplaintLetter /></ProtectedRoute>} />
        <Route path="/history"                 element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
      </Routes>
    </AuthProvider>
  )
}
