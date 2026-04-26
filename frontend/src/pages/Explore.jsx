import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./Explore.css";

const truncate = (text = "", len = 120) => {
  if (!text) return "";
  return text.length > len ? `${text.slice(0, len)}...` : text;
};

const Explore = () => {
  const navigate = useNavigate();
  const [blogs, setBlogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState(null);
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // 首屏加载推荐列表：已登录则带 user_id，未登录走默认推荐
  useEffect(() => {
    const fetchRecommendations = async () => {
      setLoading(true);
      try {
        const userStr = localStorage.getItem("user");
        let uid = null;
        if (userStr) {
          try {
            const u = JSON.parse(userStr);
            uid = u?.user_id;
            setUserId(uid || null);
          } catch (e) {
            console.warn("解析用户信息失败", e);
          }
        }

        const params = new URLSearchParams();
        params.append("limit", "20");
        if (uid) params.append("user_id", uid);

        const response = await fetch(
          `http://localhost:3001/recommendationOrchestrator/list?${params.toString()}`,
        );
        const data = await response.json();

        if (
          response.ok &&
          data.status === "success" &&
          data.data?.recommendations
        ) {
          const recs = data.data.recommendations.map((r, idx) => ({
            id: `${r.user_id}-${r.paper_id}-${idx}`,
            recommendation_id: r.id, // 添加recommendation_id
            user_id: r.user_id,
            paper_id: r.paper_id,
            title: r.title || "无标题",
            author: truncate(r.author || "未知作者", 40),
            date:
              (r.created_at || "").slice(0, 10) ||
              new Date().toISOString().split("T")[0],
            summary: truncate(r.abstract || "暂无摘要", 180),
            blog_content: r.blog || "",
            pdf_url: r.pdf_url,
            liked: !!r.liked,
          }));
          setBlogs(recs);
        } else {
          setBlogs([]);
        }
      } catch (err) {
        console.error("获取推荐博客失败:", err);
        setBlogs([]);
      } finally {
        setLoading(false);
      }
    };

    fetchRecommendations();
  }, []);

  const fetchSearch = async () => {
    // 语义搜索入口：按关键词拉取候选论文/博客
    if (!query.trim()) {
      alert("请输入搜索内容");
      return;
    }
    setIsSearching(true);
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("query", query.trim());
      params.append("topk", "5");
      const resp = await fetch(
        `http://localhost:3001/recommendationOrchestrator/search?${params.toString()}`,
      );
      const data = await resp.json();
      if (resp.ok && data.status === "success" && data.data?.results) {
        const recs = data.data.results.map((r, idx) => ({
          id: `s-${r.paper_id}-${idx}`,
          recommendation_id: r.id, // 添加recommendation_id
          user_id: r.blog_user_id,
          paper_id: r.paper_id,
          title: r.title || "无标题",
          author: truncate(r.author || "未知作者", 40),
          date: new Date().toISOString().split("T")[0],
          summary: truncate(r.abstract || "暂无摘要", 180),
          blog_content: r.blog || "",
          pdf_url: r.pdf_url,
          liked: false,
        }));
        setBlogs(recs);
      } else {
        setBlogs([]);
      }
    } catch (e) {
      console.error("搜索失败", e);
      setBlogs([]);
    } finally {
      setLoading(false);
    }
  };

  const resetToRecommend = async () => {
    setQuery("");
    setIsSearching(false);
    // 重新获取推荐
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("limit", "20");
      if (userId) params.append("user_id", userId);
      const response = await fetch(
        `http://localhost:3001/recommendationOrchestrator/list?${params.toString()}`,
      );
      const data = await response.json();
      if (
        response.ok &&
        data.status === "success" &&
        data.data?.recommendations
      ) {
        const recs = data.data.recommendations.map((r, idx) => ({
          id: `${r.user_id}-${r.paper_id}-${idx}`,
          recommendation_id: r.id, // 添加recommendation_id
          user_id: r.user_id,
          paper_id: r.paper_id,
          title: r.title || "无标题",
          author: truncate(r.author || "未知作者", 40),
          date:
            (r.created_at || "").slice(0, 10) ||
            new Date().toISOString().split("T")[0],
          summary: truncate(r.abstract || "暂无摘要", 180),
          blog_content: r.blog || "",
          pdf_url: r.pdf_url,
          liked: !!r.liked,
        }));
        setBlogs(recs);
      } else {
        setBlogs([]);
      }
    } catch (e) {
      console.error("获取推荐失败", e);
      setBlogs([]);
    } finally {
      setLoading(false);
    }
  };

  const openBlogMarkdown = (title, blogContent, fallbackPdf) => {
    // 优先展示博客正文；若无正文则降级打开论文 PDF
    if (!blogContent) {
      if (fallbackPdf) {
        window.open(fallbackPdf, "_blank");
      } else {
        alert("暂无博客内容");
      }
      return;
    }

    const win = window.open("", "_blank");
    if (!win) return;
    const safeTitle = title || "博客";
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
            const md = \`${blogContent.replace(/`/g, "\\`")}\`
            document.getElementById('app').innerHTML = marked.parse(md)
          </script>
        </body>
      </html>
    `;
    win.document.write(html);
    win.document.close();
  };

  const toggleLike = async (paperId, liked) => {
    // 收藏/取消收藏：需要登录后才允许操作
    if (!userId) {
      alert("请先登录再收藏");
      return;
    }
    try {
      const resp = await fetch(
        "http://localhost:3001/recommendationOrchestrator/like",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            paper_id: paperId,
            action: liked ? "unlike" : "like",
          }),
        },
      );
      const data = await resp.json();
      if (!resp.ok || data.status !== "success") {
        throw new Error(data.message || "操作失败");
      }
      setBlogs((prev) =>
        prev.map((b) => (b.paper_id === paperId ? { ...b, liked: !liked } : b)),
      );
    } catch (e) {
      console.error("收藏操作失败", e);
      alert("收藏操作失败，请稍后重试");
    }
  };

  if (loading) {
    return (
      <div className="explore-container">
        <div className="loading">
          <div className="loading-spinner"></div>
          <p>正在加载推荐博客...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="explore-container">
      <div className="explore-header">
        <h1>{isSearching ? "搜索结果" : "个性化推荐"}</h1>
        <p>
          {isSearching
            ? "基于语义搜索的匹配结果"
            : "基于兴趣与相似度，为你推荐的论文博客"}
        </p>
        <div
          style={{
            marginTop: 20,
            display: "flex",
            gap: 10,
            justifyContent: "center",
          }}
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入关键词进行语义搜索"
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #ddd",
              width: "320px",
            }}
          />
          <button className="btn-primary" onClick={fetchSearch}>
            搜索
          </button>
          <button className="btn-secondary" onClick={resetToRecommend}>
            回到推荐
          </button>
        </div>
      </div>

      <div className="blogs-grid">
        {blogs.length === 0 && (
          <div
            style={{ textAlign: "center", color: "#666", gridColumn: "1/-1" }}
          >
            暂无推荐数据
          </div>
        )}
        {blogs.map((blog) => (
          <div key={blog.id} className="blog-card">
            <div className="blog-header">
              <h3 className="blog-title">{blog.title}</h3>
              <div className="blog-meta">
                <span className="author">作者: {blog.author}</span>
                <span className="date">{blog.date}</span>
              </div>
            </div>
            <p className="blog-summary">{blog.summary}</p>
            {blog.liked && <div className="tag liked-tag">喜欢</div>}
            <div className="blog-actions">
              <button
                className="btn-primary"
                onClick={() =>
                  openBlogMarkdown(blog.title, blog.blog_content, blog.pdf_url)
                }
              >
                阅读博客
              </button>
              <button
                className="btn-ai"
                onClick={() => navigate(`/chat/${blog.recommendation_id}`)}
              >
                🤖 AI对话
              </button>
              <button
                className="btn-secondary"
                onClick={() =>
                  blog.pdf_url
                    ? window.open(blog.pdf_url, "_blank")
                    : alert("暂无PDF链接")
                }
              >
                查看原文 PDF
              </button>
              <button
                className="btn-secondary"
                onClick={() => toggleLike(blog.paper_id, blog.liked)}
              >
                {blog.liked ? "已收藏" : "收藏"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Explore;
