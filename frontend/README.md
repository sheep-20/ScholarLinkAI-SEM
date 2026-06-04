# ScholarLink AI 前端

这是一个仿照 PaperIgnition 风格的学术论文探索平台前端应用。

## 功能特性

- **Explore（探索）**: 展示默认的博客/论文列表，预留 API 接口
- **Favorites（收藏）**: 用户收藏的论文（需要登录）
- **Profile（个人资料）**: 用户个人信息管理（需要登录）
- **Login（登录）**: 用户登录页面

## 技术栈

- React 18
- React Router DOM
- Vite
- CSS3 (现代渐变和动画效果)

## 快速开始

cd frontend

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将在 http://localhost:3000 启动

### 构建生产版本

```bash
npm run build
```

## 项目结构

```
src/
├── components/
│   ├── Header.jsx          # 导航栏组件
│   └── Header.css
├── pages/
│   ├── Explore.jsx         # 探索页面
│   ├── Explore.css
│   ├── Favorites.jsx       # 收藏页面
│   ├── Favorites.css
│   ├── Profile.jsx         # 个人资料页面
│   ├── Profile.css
│   ├── Login.jsx           # 登录页面
│   └── Login.css
├── App.jsx                 # 主应用组件
├── App.css
├── main.jsx               # 应用入口
└── index.css              # 全局样式
```

## API 接口预留

在 `Explore.jsx` 中，已经预留了 API 接口的位置：

```javascript
// 模拟从 API 获取博客数据
useEffect(() => {
  // 这里将来会替换为真实的 API 调用
  // 例如: fetch('/api/blogs').then(res => res.json()).then(setBlogs)
}, [])
```

## 设计特色

- 仿照 PaperIgnition 的简洁现代风格
- 响应式设计，支持移动端
- 渐变色彩搭配和流畅动画
- 卡片式布局，提升用户体验
- 毛玻璃效果的导航栏

## 登录状态管理

应用使用简单的状态管理来处理登录状态：
- 未登录时显示登录按钮
- 登录后显示登出按钮
- 收藏和个人资料页面需要登录才能访问
