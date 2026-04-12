# SE-Program-ScholarLinkAI

### 本地部署Mysql数据库教程（张艺扬你在建数据库的时候把数据库的密码设置成111111，用户是root）
https://zhuanlan.zhihu.com/p/654087404

### 数据库字段设计

#### 元数据数据库

表1：papers
paper_id, abstract, pdf_url, title, author

表2：users
user_id, username, password, interest

表3：recommendations
user_id, paper_id, blog