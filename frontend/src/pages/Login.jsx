import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Login.css'

const Login = ({ onLogin }) => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
    // 清除错误信息
    if (error) setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')
    
    try {
      // 调用后端登录 API
      const response = await fetch('http://localhost:3001/users/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          password: formData.password
        })
      })

      const data = await response.json()

      if (response.ok && data.status === 'success') {
        // 保存用户信息到 localStorage
        localStorage.setItem('user', JSON.stringify(data.data))
        localStorage.setItem('isLoggedIn', 'true')
        
        // 通知父组件登录成功
        onLogin()
        
        // 跳转到首页
        navigate('/')
      } else {
        // 登录失败
        setError(data.message || '登录失败，请检查用户名和密码')
      }
    } catch (err) {
      console.error('登录错误:', err)
      setError('网络错误，请检查后端服务是否启动')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>登录</h1>
          <p>欢迎回到 ScholarLink AI</p>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}
          
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="请输入您的用户名"
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入您的密码"
              required
            />
          </div>
          
          <button 
            type="submit" 
            className="btn-login-submit"
            disabled={isLoading}
          >
            {isLoading ? '登录中...' : '登录'}
          </button>
        </form>
        
        <div className="login-footer">
          <p>还没有账户？ <Link to="/register" className="link">立即注册</Link></p>
          <a href="#" className="link">忘记密码？</a>
        </div>
      </div>
    </div>
  )
}

export default Login
