import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import './Login.css'

const Register = ({ onRegister }) => {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    interest: ''
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
    
    // 验证密码确认
    if (formData.password !== formData.confirmPassword) {
      setError('两次输入的密码不一致')
      setIsLoading(false)
      return
    }

    // 验证密码长度
    if (formData.password.length < 6) {
      setError('密码长度至少为6位')
      setIsLoading(false)
      return
    }
    
    try {
      // 调用后端注册 API
      const response = await fetch('http://localhost:3001/users/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          password: formData.password,
          interest: formData.interest || undefined
        })
      })

      const data = await response.json()

      if (response.ok && data.status === 'success') {
        // 注册成功，保存用户信息
        localStorage.setItem('user', JSON.stringify(data.data))
        localStorage.setItem('isLoggedIn', 'true')
        
        // 通知父组件注册成功（自动登录）
        if (onRegister) {
          onRegister()
        }
        
        // 跳转到首页
        navigate('/')
      } else {
        // 注册失败
        setError(data.message || '注册失败，请重试')
      }
    } catch (err) {
      console.error('注册错误:', err)
      setError('网络错误，请检查后端服务是否启动')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>注册</h1>
          <p>创建您的 ScholarLink AI 账户</p>
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
              placeholder="请输入用户名"
              required
              minLength={3}
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
              placeholder="请输入密码（至少6位）"
              required
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">确认密码</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              required
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="interest">研究兴趣（可选）</label>
            <input
              type="text"
              id="interest"
              name="interest"
              value={formData.interest}
              onChange={handleChange}
              placeholder="例如：Machine Learning, NLP, Computer Vision"
            />
            <small className="form-hint">设置您的研究兴趣，系统将为您推荐相关论文</small>
          </div>
          
          <button 
            type="submit" 
            className="btn-login-submit"
            disabled={isLoading}
          >
            {isLoading ? '注册中...' : '注册'}
          </button>
        </form>
        
        <div className="login-footer">
          <p>已有账户？ <Link to="/login" className="link">立即登录</Link></p>
        </div>
      </div>
    </div>
  )
}

export default Register


