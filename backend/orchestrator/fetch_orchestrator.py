"""
论文抓取Orchestrator - 协调论文抓取、保存和查询功能
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from service.fetch_papers import PaperFetchService
from service.dbmanager import DbManager

logger = logging.getLogger(__name__)


class FetchOrchestrator:
    """论文抓取业务流程编排器"""

    def __init__(self):
        """初始化抓取orchestrator"""
        self.db = DbManager()
        self.fetch_service = PaperFetchService()
        logger.info("FetchOrchestrator初始化完成")

    def fetch_and_save_papers(self, max_results: Optional[int] = None) -> Dict[str, Any]:
        """
        抓取论文并保存到数据库

        Args:
            max_results: 最大抓取数量

        Returns:
            处理结果统计
        """
        try:
            logger.info(f"开始抓取论文，max_results={max_results}")

            # 1. 调用 fetch_papers 服务获取论文
            papers = self.fetch_service.fetch_papers(max_results=max_results)

            if not papers:
                return {
                    'message': '该时间窗口内没有找到新论文',
                    'fetched_count': 0,
                    'saved_count': 0,
                    'failed_count': 0,
                    'papers': []
                }

            logger.info(f"成功抓取 {len(papers)} 篇论文，开始保存到数据库...")

            # 2. 调用 DbManager 将论文保存到数据库
            saved_count = 0
            failed_count = 0
            saved_papers = []

            for paper in papers:
                try:
                    # 检查论文是否已存在（通过标题，因为没有 arxiv_id 字段）
                    existing = self.db.query_one(
                        "SELECT paper_id FROM papers WHERE title = %s",
                        (paper['title'],)
                    )

                    if existing:
                        logger.debug(f"论文 {paper['title'][:50]}... 已存在，跳过")
                        continue

                    # 准备数据：将作者列表转换为字符串（适配 author 字段）
                    authors_str = ', '.join(paper['authors'])

                    # 插入论文数据（只插入数据库设计中要求的字段）
                    result = self.db.execute(
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
                'fetched_count': len(papers),
                'saved_count': saved_count,
                'failed_count': failed_count,
                'papers': saved_papers[:10]  # 只返回前10篇的基本信息
            }

        except Exception as e:
            logger.error(f"抓取论文失败: {str(e)}", exc_info=True)
            raise

    def get_paper_list(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        获取论文列表

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            论文列表和分页信息
        """
        try:
            # 计算偏移量
            offset = (page - 1) * page_size

            # 获取所有论文（简化版，不支持分类过滤因为数据库中没有该字段）
            papers = self.db.query_all(
                """
                SELECT paper_id, title, author, abstract, pdf_url
                FROM papers
                ORDER BY paper_id DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset)
            )

            total = self.db.query_one("SELECT COUNT(*) as count FROM papers")

            total_count = total['count'] if total else 0
            total_pages = (total_count + page_size - 1) // page_size

            return {
                'papers': papers,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total_count,
                    'total_pages': total_pages
                }
            }

        except Exception as e:
            logger.error(f"获取论文列表失败: {str(e)}", exc_info=True)
            raise

    def get_paper_detail(self, paper_id: int) -> Optional[Dict[str, Any]]:
        """
        获取论文详情

        Args:
            paper_id: 论文ID

        Returns:
            论文详情，如果不存在返回None
        """
        try:
            paper = self.db.query_one(
                """
                SELECT * FROM papers WHERE paper_id = %s
                """,
                (paper_id,)
            )

            return paper

        except Exception as e:
            logger.error(f"获取论文详情失败: {str(e)}", exc_info=True)
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        获取抓取服务状态

        Returns:
            状态信息
        """
        try:
            # 获取论文总数
            total_papers = self.db.query_one("SELECT COUNT(*) as count FROM papers")
            total_count = total_papers['count'] if total_papers else 0

            # 获取有embedding的论文数
            embedded_papers = self.db.query_one("SELECT COUNT(*) as count FROM paper_embeddings")
            embedded_count = embedded_papers['count'] if embedded_papers else 0

            # 获取最近的论文
            recent_papers = self.db.query_all(
                """
                SELECT paper_id, title, author
                FROM papers
                ORDER BY paper_id DESC
                LIMIT 5
                """
            )

            return {
                'total_papers': total_count,
                'embedded_papers': embedded_count,
                'embedding_coverage': f"{embedded_count}/{total_count}" if total_count > 0 else "0/0",
                'recent_papers': recent_papers
            }

        except Exception as e:
            logger.error(f"获取抓取服务状态失败: {str(e)}", exc_info=True)
            raise


__all__ = ["FetchOrchestrator"]
