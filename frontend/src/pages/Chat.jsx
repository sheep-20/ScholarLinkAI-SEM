import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import "./Chat.css";

const Chat = () => {
  const { recommendationId } = useParams();
  const navigate = useNavigate();
  const [chatHistory, setChatHistory] = useState([]);
  const [paperInfo, setPaperInfo] = useState(null);
  const [newMessage, setNewMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory]);

  useEffect(() => {
    if (recommendationId) {
      loadChatHistory();
    }
  }, [recommendationId]);

  const loadChatHistory = async () => {
    try {
      // 根据 recommendationId 拉取历史对话与论文基础信息
      setIsLoadingHistory(true);
      const response = await fetch(
        `http://localhost:3001/chat/history/${recommendationId}`,
      );
      const data = await response.json();

      if (data.status === "success") {
        setChatHistory(data.data.chat_history);
        setPaperInfo(data.data.paper_info);
      } else {
        alert("加载对话历史失败：" + data.message);
      }
    } catch (error) {
      console.error("加载对话历史失败:", error);
      alert("加载对话历史失败，请稍后重试");
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || isLoading) return;

    const userMessage = newMessage.trim();
    setNewMessage("");
    setIsLoading(true);

    // 乐观更新：先显示用户消息，待接口返回后再刷新为真实记录
    const tempUserMessage = {
      id: Date.now(),
      recommendation_id: parseInt(recommendationId),
      user_message: userMessage,
      ai_response: "",
      created_at: new Date().toISOString(),
      isPending: true,
    };
    setChatHistory((prev) => [...prev, tempUserMessage]);

    try {
      const response = await fetch("http://localhost:3001/chat/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          recommendation_id: parseInt(recommendationId),
          user_message: userMessage,
        }),
      });

      const data = await response.json();

      if (data.status === "success") {
        // 更新消息历史
        await loadChatHistory();
      } else {
        alert("发送消息失败：" + data.message);
        // 移除临时消息
        setChatHistory((prev) => prev.filter((msg) => !msg.isPending));
      }
    } catch (error) {
      console.error("发送消息失败:", error);
      alert("发送消息失败，请稍后重试");
      // 移除临时消息
      setChatHistory((prev) => prev.filter((msg) => !msg.isPending));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    // 输入体验：Enter 发送，Shift + Enter 换行
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoadingHistory) {
    return (
      <div className="chat-container">
        <div className="loading">加载中...</div>
      </div>
    );
  }

  if (!paperInfo) {
    return (
      <div className="chat-container">
        <div className="error">未找到论文信息</div>
      </div>
    );
  }

  return (
    <div className="chat-container">
      {/* 论文信息头部 */}
      <div className="chat-header">
        <button className="back-button" onClick={() => navigate(-1)}>
          ← 返回
        </button>
        <div className="paper-info">
          <h2>{paperInfo.title}</h2>
          <p className="author">作者: {paperInfo.author}</p>
        </div>
      </div>

      {/* 对话区域 */}
      <div className="chat-messages">
        {chatHistory.length === 0 ? (
          <div className="welcome-message">
            <h3>开始与AI对话</h3>
            <p>关于这篇论文，您有什么问题吗？</p>
            <div className="suggestions">
              <div
                className="suggestion-tag"
                onClick={() => setNewMessage("请总结一下这篇论文的主要贡献")}
              >
                请总结一下这篇论文的主要贡献
              </div>
              <div
                className="suggestion-tag"
                onClick={() => setNewMessage("这篇论文使用了什么方法？")}
              >
                这篇论文使用了什么方法？
              </div>
              <div
                className="suggestion-tag"
                onClick={() => setNewMessage("论文的结果如何？")}
              >
                论文的结果如何？
              </div>
            </div>
          </div>
        ) : (
          chatHistory.map((chat) => (
            <div key={chat.id} className="message-group">
              {/* 用户消息 */}
              <div className="message user-message">
                <div className="message-avatar">我</div>
                <div className="message-content">
                  <div className="message-text">{chat.user_message}</div>
                  <div className="message-time">
                    {formatTime(chat.created_at)}
                  </div>
                </div>
              </div>

              {/* AI回复 */}
              <div className="message ai-message">
                <div className="message-avatar">AI</div>
                <div className="message-content">
                  <div className="message-text">
                    {chat.isPending ? (
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    ) : (
                      <ReactMarkdown>{chat.ai_response}</ReactMarkdown>
                    )}
                  </div>
                  {!chat.isPending && (
                    <div className="message-time">
                      {formatTime(chat.created_at)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="chat-input">
        <div className="input-container">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题..."
            disabled={isLoading}
            rows={1}
          />
          <button
            onClick={sendMessage}
            disabled={!newMessage.trim() || isLoading}
            className="send-button"
          >
            {isLoading ? "发送中..." : "发送"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chat;
