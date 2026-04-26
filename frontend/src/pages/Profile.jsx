import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './Profile.css'

const Profile = ({ isLoggedIn }) => {
  const [user, setUser] = useState(null)
  const [interest, setInterest] = useState('')
  const [isEditingInterest, setIsEditingInterest] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    // 从localStorage获取用户信息
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        const userData = JSON.parse(userStr)
        setUser(userData)
        setInterest(userData.interest || '')
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }
  }, [])

  // 如果没有登录，显示登录提示
  if (!isLoggedIn) {
    return (
      <div className="profile-container">
        <div className="login-prompt">
          <h2>个人资料</h2>
          <p>请先登录以查看和管理您的个人资料</p>
          <Link to="/login" className="btn-login">
            立即登录
          </Link>
        </div>
      </div>
    )
  }

  // 如果没有用户信息，尝试从API获取
  useEffect(() => {
    if (isLoggedIn && user && user.user_id) {
      fetchUserInfo(user.user_id)
    }
  }, [isLoggedIn, user?.user_id])

  const fetchUserInfo = async (userId) => {
    try {
      const response = await fetch(`http://localhost:3001/users/${userId}`)
      const data = await response.json()
      if (response.ok && data.status === 'success') {
        const userData = data.data.user
        setUser(userData)
        setInterest(userData.interest || '')
      }
    } catch (err) {
      console.error('获取用户信息失败:', err)
    }
  }

  const handleInterestChange = (e) => {
    setInterest(e.target.value)
    setError('')
    setSuccess('')
  }

  const handleSaveInterest = async () => {
    if (!user || !user.user_id) {
      setError('用户信息不完整')
      return
    }

    setIsLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await fetch(`http://localhost:3001/users/${user.user_id}/interest`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          interest: interest.trim()
        })
      })

      const data = await response.json()

      if (response.ok && data.status === 'success') {
        setSuccess('兴趣更新成功！系统正在更新推荐索引...')
        setIsEditingInterest(false)
        
        // 更新本地用户信息
        const updatedUser = { ...user, interest: interest.trim() }
        setUser(updatedUser)
        localStorage.setItem('user', JSON.stringify(updatedUser))
        
        // 3秒后清除成功消息
        setTimeout(() => setSuccess(''), 3000)
      } else {
        setError(data.message || '更新失败，请重试')
      }
    } catch (err) {
      console.error('更新兴趣失败:', err)
      setError('网络错误，请检查后端服务是否启动')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancelEdit = () => {
    // 恢复原始兴趣
    setInterest(user?.interest || '')
    setIsEditingInterest(false)
    setError('')
    setSuccess('')
  }

  if (!user) {
    return (
      <div className="profile-container">
        <div className="loading">加载中...</div>
      </div>
    )
  }

  return (
    <div className="profile-container">
      <div className="profile-header">
        <h1>个人资料</h1>
        <p>管理您的账户信息和偏好设置</p>
      </div>
      
      <div className="profile-content">
        <div className="profile-card">
          <div className="profile-avatar">
            <div className="avatar-placeholder">👤</div>
          </div>
          <div className="profile-info">
            <h3>{user.username}</h3>
            <p>用户ID: {user.user_id}</p>
            <div className="profile-stats">
              <div className="stat">
                <span className="stat-number">0</span>
                <span className="stat-label">收藏论文</span>
              </div>
              <div className="stat">
                <span className="stat-number">0</span>
                <span className="stat-label">阅读历史</span>
              </div>
            </div>
          </div>
        </div>
        
        <div className="profile-section">
          <h2>研究兴趣</h2>
          <p className="section-description">
            设置您的研究兴趣领域，系统将基于此为您推荐相关论文
          </p>
          
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}
          
          {success && (
            <div className="success-message">
              {success}
            </div>
          )}
          
          {isEditingInterest ? (
            <div className="interest-edit-form">
              <textarea
                className="interest-input"
                value={interest}
                onChange={handleInterestChange}
                placeholder="例如：Machine Learning, Natural Language Processing, Computer Vision"
                rows={4}
                disabled={isLoading}
              />
              <div className="interest-actions">
                <button
                  className="btn-primary"
                  onClick={handleSaveInterest}
                  disabled={isLoading || !interest.trim()}
                >
                  {isLoading ? '保存中...' : '保存'}
                </button>
                <button
                  className="btn-secondary"
                  onClick={handleCancelEdit}
                  disabled={isLoading}
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <div className="interest-display">
              <div className="interest-content">
                {interest ? (
                  <p>{interest}</p>
                ) : (
                  <p className="no-interest">暂未设置研究兴趣</p>
                )}
              </div>
              <button
                className="btn-primary"
                onClick={() => setIsEditingInterest(true)}
              >
                编辑兴趣
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Profile
