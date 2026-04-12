import React, { useState } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Explore from './pages/Explore'
import Favorites from './pages/Favorites'
import Profile from './pages/Profile'
import Login from './pages/Login'
import Register from './pages/Register'
import Chat from './pages/Chat'
import './App.css'

function App() {
  // 从 localStorage 读取登录状态
  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return localStorage.getItem('isLoggedIn') === 'true'
  })

  const handleLogin = () => {
    setIsLoggedIn(true)
    localStorage.setItem('isLoggedIn', 'true')
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    localStorage.removeItem('isLoggedIn')
    localStorage.removeItem('user')
  }

  return (
    <Router>
      <div className="App">
        <Header isLoggedIn={isLoggedIn} onLogout={handleLogout} />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Explore />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/favorites" element={<Favorites isLoggedIn={isLoggedIn} />} />
            <Route path="/profile" element={<Profile isLoggedIn={isLoggedIn} />} />
            <Route path="/chat/:recommendationId" element={<Chat />} />
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/register" element={<Register onRegister={handleLogin} />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
