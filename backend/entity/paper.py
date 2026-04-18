"""
Paper Entity - 论文实体类
匹配数据库结构：paper_id, title, author, abstract, pdf_url
"""
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Paper(Base):
    __tablename__ = 'papers'
    
    paper_id = Column(Integer, primary_key=True, autoincrement=True, comment='论文ID')
    title = Column(String(1000), nullable=False, comment='论文标题')
    author = Column(String(1000), nullable=True, comment='作者')
    abstract = Column(Text, nullable=True, comment='摘要')
    pdf_url = Column(String(512), nullable=True, comment='PDF链接')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'paper_id': self.paper_id,
            'title': self.title,
            'author': self.author,
            'abstract': self.abstract,
            'pdf_url': self.pdf_url
        }
