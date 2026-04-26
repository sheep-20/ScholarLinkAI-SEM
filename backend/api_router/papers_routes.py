"""
Papers API - 论文抓取和管理接口
"""
from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from datetime import datetime
import sys
import os
import logging

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.fetch_papers import PaperFetchService
from service.dbmanager import DbManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建命名空间
papers_ns = Namespace('papers', description='论文抓取和管理接口')

# 定义响应模型（匹配数据库结构：paper_id, title, author, abstract, pdf_url）
paper_model = papers_ns.model('Paper', {
    'paper_id': fields.Integer(description='论文ID'),
    'title': fields.String(required=True, description='论文标题'),
    'author': fields.String(description='作者'),
    'abstract': fields.String(description='摘要'),
    'pdf_url': fields.String(description='PDF链接')
})

fetch_response_model = papers_ns.model('FetchPapersResponse', {
    'message': fields.String(description='响应消息'),
    'status': fields.String(description='响应状态'),
    'timestamp': fields.String(description='时间戳'),
    'data': fields.Raw(description='响应数据')
})

fetch_request_model = papers_ns.model('FetchPapersRequest', {
    'max_results': fields.Integer(description='最大结果数，不指定则获取所有论文', required=False)
})


@papers_ns.route('/fetch')
class FetchPapers(Resource):
    @papers_ns.doc('fetch_papers')
    @papers_ns.expect(fetch_request_model, validate=False)
    @papers_ns.marshal_with(fetch_response_model)
    def post(self):
        """
        抓取论文并保存到数据库
        
        从 arXiv 抓取前两天到前一天的 CS 类论文，并自动保存到数据库中
        """
        try:
            # 获取请求参数
            data = request.get_json() or {}
            max_results = data.get('max_results', None)
            
            logger.info(f"开始抓取论文，max_results={max_results}")
            
            # 1. 调用 fetch_papers 服务获取论文
            fetch_service = PaperFetchService()
            papers = fetch_service.fetch_papers(max_results=max_results)
            
            if not papers:
                return {
                    'message': '该时间窗口内没有找到新论文',
                    'status': 'success',
                    'timestamp': datetime.now().isoformat(),
                    'data': {
                        'fetched_count': 0,
                        'saved_count': 0,
                        'failed_count': 0,
                        'papers': []
                    }
                }
            
            logger.info(f"成功抓取 {len(papers)} 篇论文，开始保存到数据库...")
            
            # 2. 调用 DbManager 将论文保存到数据库
            db = DbManager()
            saved_count = 0
            failed_count = 0
            saved_papers = []
            
            for paper in papers:
                try:
                    # 检查论文是否已存在（通过标题，因为没有 arxiv_id 字段）
                    existing = db.query_one(
                        "SELECT paper_id FROM papers WHERE title = %s",
                        (paper['title'],)
                    )
                    
                    if existing:
                        logger.debug(f"论文 {paper['title'][:50]}... 已存在，跳过")
                        continue
                    
                    # 准备数据：将作者列表转换为字符串（适配 author 字段）
                    authors_str = ', '.join(paper['authors'])
                    
                    # 插入论文数据（只插入数据库设计中要求的字段）
                    result = db.execute(
                        """
                        INSERT INTO papers 
                        (title, author, abstract, pdf_url)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            paper['title'],
                            authors_str,
                            paper['abstract'],
                            paper['pdf_url']
                        )
                    )
                    
                    saved_count += 1
                    saved_papers.append({
                        'paper_id': result['lastrowid'],
                        'title': paper['title']
                    })
                    
                    logger.debug(f"成功保存论文: {paper['title'][:50]}...")
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"保存论文 {paper.get('title', 'Unknown')[:50]} 失败: {str(e)}")
                    continue
            
            logger.info(f"论文保存完成: 抓取 {len(papers)} 篇, 保存 {saved_count} 篇, 失败 {failed_count} 篇")
            
            return {
                'message': f'成功抓取并保存 {saved_count} 篇论文',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'fetched_count': len(papers),
                    'saved_count': saved_count,
                    'failed_count': failed_count,
                    'papers': saved_papers[:10]  # 只返回前10篇的基本信息
                }
            }
            
        except Exception as e:
            logger.error(f"抓取论文失败: {str(e)}", exc_info=True)
            return {
                'message': f'抓取论文失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@papers_ns.route('/list')
class ListPapers(Resource):
    @papers_ns.doc('list_papers')
    def get(self):
        """
        获取论文列表
        
        支持分页（page, page_size 参数）
        """
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            # 构建查询
            db = DbManager()
            
            # 获取所有论文（简化版，不支持分类过滤因为数据库中没有该字段）
            papers = db.query_all(
                """
                SELECT paper_id, title, author, abstract, pdf_url
                FROM papers 
                ORDER BY paper_id DESC 
                LIMIT %s OFFSET %s
                """,
                (page_size, offset)
            )
            
            total = db.query_one("SELECT COUNT(*) as count FROM papers")
            
            total_count = total['count'] if total else 0
            total_pages = (total_count + page_size - 1) // page_size
            
            return {
                'message': '获取论文列表成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'papers': papers,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total_count,
                        'total_pages': total_pages
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"获取论文列表失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取论文列表失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@papers_ns.route('/<int:paper_id>')
class PaperDetail(Resource):
    @papers_ns.doc('get_paper')
    def get(self, paper_id):
        """
        获取论文详情
        
        根据 paper_id 获取单篇论文的完整信息
        """
        try:
            db = DbManager()
            paper = db.query_one(
                """
                SELECT * FROM papers WHERE paper_id = %s
                """,
                (paper_id,)
            )
            
            if not paper:
                return {
                    'message': f'论文不存在 (paper_id={paper_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404
            
            return {
                'message': '获取论文详情成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'paper': paper
                }
            }
            
        except Exception as e:
            logger.error(f"获取论文详情失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取论文详情失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500



