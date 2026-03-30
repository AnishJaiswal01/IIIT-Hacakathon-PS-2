import React from 'react';
import './LoginPage.css';

// Minimalist inline icons
const UserIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="input-icon">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
    <circle cx="12" cy="7" r="4"></circle>
  </svg>
);

const MailIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="input-icon">
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
    <polyline points="22,6 12,13 2,6"></polyline>
  </svg>
);

const LockIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="input-icon">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
  </svg>
);

const LogoIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="logo-icon">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
    <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
    <line x1="12" y1="22.08" x2="12" y2="12"></line>
  </svg>
);

export default function LoginPage({ onLogin }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onLogin) onLogin();
  };

  return (
    <div className="login-page-container">
      <div className="login-card">
        
        <div className="login-header">
          <div className="logo-placeholder">
            <LogoIcon />
          </div>
          <h1 className="welcome-title">Welcome Back</h1>
          <p className="welcome-subtitle">Sign in to initialize the structural engine.</p>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Username Field */}
          <div className="input-group">
            <input 
              type="text" 
              className="lux-input" 
              placeholder="Username" 
              required
            />
            <UserIcon />
          </div>

          {/* Email Field */}
          <div className="input-group">
            <input 
              type="email" 
              className="lux-input" 
              placeholder="Email address" 
              required
            />
            <MailIcon />
          </div>

          {/* Password Field */}
          <div className="input-group" style={{ marginBottom: "16px" }}>
            <input 
              type="password" 
              className="lux-input" 
              placeholder="Password" 
              required
            />
            <LockIcon />
          </div>

          {/* Links Row */}
          <div className="form-actions">
            <a href="#" className="forgot-link">Forgot Password?</a>
          </div>

          {/* Submit Action */}
          <button type="submit" className="primary-btn">
            Sign In
          </button>
        </form>

        <div className="footer-link">
          Don't have an account? 
          <a href="#">Sign Up</a>
        </div>

      </div>
    </div>
  );
}
