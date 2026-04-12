import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import './Header.css'

const Header = ({ isLoggedIn, onLogout }) => {
  const location = useLocation()

  return (
    <header className="header">
      <div className="header-container">
        <div className="logo">
          <Link to="/">ScholarLink AI</Link>
        </div>
        
        <nav className="nav">
          <Link 
            to="/explore" 
            className={`nav-link ${location.pathname === '/explore' || location.pathname === '/' ? 'active' : ''}`}
          >
            Explore
          </Link>
          <Link 
            to="/favorites" 
            className={`nav-link ${location.pathname === '/favorites' ? 'active' : ''}`}
          >
            Favorites
          </Link>
          <Link 
            to="/profile" 
            className={`nav-link ${location.pathname === '/profile' ? 'active' : ''}`}
          >
            Profile
          </Link>
          {isLoggedIn ? (
            <button className="nav-button logout" onClick={onLogout}>
              Log Out
            </button>
          ) : (
            <Link to="/login" className="nav-button login">
              Log In
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}

export default Header
