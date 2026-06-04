import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import './Favorites.css'
import '../pages/Explore.css'

const truncate = (text = '', len = 180) => {
  if (!text) return ''
  return text.length > len ? `${text.slice(0, len)}...` : text
}

const Favorites = ({ isLoggedIn }) => {
  const [favs, setFavs] = useState([])
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState(null)

  useEffect(() => {
    if (!isLoggedIn) return
    const userStr = localStorage.getItem('user')
    let uid = null
    if (userStr) {
      try {
        uid = JSON.parse(userStr)?.user_id
      } catch (e) {
        console.warn('解析用户信息失败', e)
      }
    }
    setUserId(uid)
    if (!uid) {
      setLoading(false)
      return
    }

    const fetchFavs = async () => {
      setLoading(true)
      try {
        const resp = await fetch(`http://localhost:3001/recommendationOrchestrator/favorites?user_id=${uid}&limit=50`)
        const data = await resp.json()
        if (resp.ok && data.status === 'success' && data.data?.favorites) {
          const list = data.data.favorites.map((r, idx) => ({
            id: `${r.user_id}-${r.paper_id}-${idx}`,
            user_id: r.user_id,
            paper_id: r.paper_id,
            title: r.title || '无标题',
            author: truncate(r.author || '未知作者', 40),
            date: (r.liked_at || '').slice(0, 10) || (r.blog_created_at || '').slice(0, 10),
            summary: truncate(r.abstract || '暂无摘要', 180),
            blog_content: r.blog || '',
            pdf_url: r.pdf_url,
            liked: true
          }))
          setFavs(list)
        } else {
          setFavs([])
        }
      } catch (e) {
        console.error('获取收藏失败', e)
        setFavs([])
      } finally {
        setLoading(false)
      }
    }

    fetchFavs()
  }, [isLoggedIn])

  const openBlogMarkdown = (title, blogContent, fallbackPdf) => {
    if (!blogContent) {
      if (fallbackPdf) {
        window.open(fallbackPdf, '_blank')
      } else {
        alert('暂无博客内容')
      }
      return
    }
    const win = window.open('', '_blank')
    if (!win) return
    const safeTitle = title || '博客'
    const html = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>${safeTitle}</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 30px; max-width: 960px; margin: auto; line-height: 1.6; }
            pre { background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }
            code { background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }
            h1, h2, h3 { color: #333; }
            a { color: #667eea; }
          </style>
          <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        </head>
        <body>
          <h1>${safeTitle}</h1>
          <div id="app"></div>
          <script>
            const md = \`${blogContent.replace(/`/g, '\\`')}\`
            document.getElementById('app').innerHTML = marked.parse(md)
          </script>
        </body>
      </html>
    `
    win.document.write(html)
    win.document.close()
  }

  const cancelLike = async (paperId) => {
    if (!userId) {
      alert('请先登录')
      return
    }
    try {
      const resp = await fetch('http://localhost:3001/recommendationOrchestrator/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          paper_id: paperId,
          action: 'unlike'
        })
      })
      const data = await resp.json()
      if (!resp.ok || data.status !== 'success') {
        throw new Error(data.message || '取消收藏失败')
      }
      setFavs(prev => prev.filter(f => f.paper_id !== paperId))
    } catch (e) {
      console.error('取消收藏失败', e)
      alert('取消收藏失败，请稍后重试')
    }
  }

  if (!isLoggedIn) {
    return (
      <div className="favorites-container">
        <div className="login-prompt">
          <h2>我的收藏</h2>
          <p>请先登录以查看您的收藏论文</p>
          <Link to="/login" className="btn-login">
            立即登录
          </Link>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="favorites-container">
        <div className="loading">
          <div className="loading-spinner"></div>
          <p>加载收藏中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="favorites-container">
      <div className="favorites-header">
        <h1>我的收藏</h1>
        <p>您收藏的论文和博客</p>
      </div>
      
      <div className="blogs-grid">
        {favs.length === 0 && (
          <div style={{ textAlign: 'center', color: '#666', gridColumn: '1/-1' }}>
            暂无收藏，去 <Link to="/explore">探索</Link> 吧
          </div>
        )}
        {favs.map(blog => (
          <div key={blog.id} className="blog-card">
            <div className="blog-header">
              <h3 className="blog-title">{blog.title}</h3>
              <div className="blog-meta">
                <span className="author">作者: {blog.author}</span>
                <span className="date">{blog.date}</span>
              </div>
            </div>
            <p className="blog-summary">{blog.summary}</p>
            <div className="tag liked-tag">喜欢</div>
            <div className="blog-actions">
              <button 
                className="btn-primary" 
                onClick={() => openBlogMarkdown(blog.title, blog.blog_content, blog.pdf_url)}
              >
                阅读博客
              </button>
              <button 
                className="btn-secondary" 
                onClick={() => (blog.pdf_url ? window.open(blog.pdf_url, '_blank') : alert('暂无PDF链接'))}
              >
                查看原文 PDF
              </button>
              <button 
                className="btn-secondary" 
                onClick={() => cancelLike(blog.paper_id)}
              >
                取消收藏
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default Favorites
