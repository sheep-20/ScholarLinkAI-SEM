"""
Paper Fetching Service
从 arXiv 抓取前两天到前一天的 CS 类论文元数据，并自动计算embeddings
"""

import arxiv
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

from .dbmanager import DbManager
from .openrouter_embedding import OpenRouterEmbedding

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperFetchService:
    """
    论文抓取服务类
    负责从 arXiv 获取前两天到前一天的论文元数据
    """
    
    def __init__(self):
        """初始化 arXiv 客户端、embedding服务和数据库连接"""
        self.client = arxiv.Client()
        self.arxiv_pool = set()  # 用于去重的论文 ID 集合
        self.db = DbManager()
        self.embedding_service = OpenRouterEmbedding()
    
    def fetch_papers(self, max_results: Optional[int] = None) -> List[Dict]:
        """
        抓取前两天到前一天的论文
        
        时间窗口：[当前时间 - 2天, 当前时间 - 1天]
        
        Args:
            max_results: 最大返回结果数，None 表示不限制
            
        Returns:
            论文元数据列表
        """
        # 计算时间窗口：前两天到前一天
        current_time = datetime.utcnow()
        end_time = current_time - timedelta(days=1)    # 前一天
        start_time = current_time - timedelta(days=2)  # 前两天
        
        # 格式化时间为 arXiv API 要求的格式: YYYYMMDDHHMMSS
        start_time_str = start_time.strftime("%Y%m%d%H%M%S")
        end_time_str = end_time.strftime("%Y%m%d%H%M%S")
        
        logger.info(f"开始抓取时间窗口: [{start_time_str} TO {end_time_str}]")
        logger.info(f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
        
        # 构建查询
        query = f"cat:cs.* AND submittedDate:[{start_time_str} TO {end_time_str}]"
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        logger.info(f"正在从 arXiv 抓取 CS 类论文...")
        
        try:
            # 获取搜索结果
            results = self.client.results(search)
            results_list = list(results)
            
            logger.info(f"成功搜索! 共找到 {len(results_list)} 篇论文")
            
            # 解析论文数据
            papers = self._parse_papers(results_list)

            logger.info(f"成功解析 {len(papers)} 篇论文元数据")

            # 将论文存储到数据库并计算embeddings
            stored_count = self._store_papers_and_compute_embeddings(papers)

            logger.info(f"成功存储并计算embedding: {stored_count}/{len(papers)} 篇论文")

            return papers
            
        except Exception as e:
            logger.error(f"抓取论文时出错: {str(e)}")
            raise
    
    def _parse_papers(self, results_list: List) -> List[Dict]:
        """
        解析论文结果列表，提取元数据
        
        Args:
            results_list: arXiv API 返回的结果列表
            
        Returns:
            解析后的论文元数据列表
        """
        papers = []
        failed_count = 0
        
        for idx, result in enumerate(results_list):
            try:
                # 提取 arxiv_id (去掉版本号)
                arxiv_id = result.entry_id.split('/abs/')[-1].split('v')[0]
                
                # 去重检查
                if arxiv_id in self.arxiv_pool:
                    logger.debug(f"论文 {arxiv_id} 已存在，跳过")
                    continue
                
                # 提取元数据
                paper_data = {
                    'arxiv_id': arxiv_id,
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'categories': result.categories,
                    'primary_category': result.primary_category,
                    'published_date': result.published.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_date': result.updated.strftime("%Y-%m-%d %H:%M:%S"),
                    'abstract': result.summary,
                    'pdf_url': result.pdf_url,
                    'entry_url': result.entry_id,
                    'comment': result.comment if hasattr(result, 'comment') else None,
                    'journal_ref': result.journal_ref if hasattr(result, 'journal_ref') else None,
                }
                
                papers.append(paper_data)
                self.arxiv_pool.add(arxiv_id)
                
                # arXiv API 限流：每3秒最多1个请求
                # 为了安全，在处理每篇论文后稍微延迟
                if (idx + 1) % 10 == 0:  # 每处理10篇论文延迟一次
                    time.sleep(3)
                    logger.debug(f"已处理 {idx + 1} 篇论文...")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"解析论文时出错 (索引 {idx}): {str(e)}")
                # 记录失败的论文ID（如果可以获取）
                try:
                    failed_id = result.entry_id if hasattr(result, 'entry_id') else 'Unknown'
                    logger.error(f"失败的论文ID: {failed_id}")
                except:
                    pass
                continue
        
        if failed_count > 0:
            logger.warning(f"共有 {failed_count} 篇论文解析失败")

        return papers

    def _store_papers_and_compute_embeddings(self, papers: List[Dict]) -> int:
        """
        将论文存储到数据库并计算embeddings

        Args:
            papers: 论文数据列表

        Returns:
            成功处理的数量
        """
        if not papers:
            return 0

        success_count = 0
        batch_size = 5  # 每批处理5篇论文，避免API限流

        logger.info(f"开始批量存储并计算 {len(papers)} 篇论文的embeddings")

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            batch_success = 0

            for paper in batch:
                try:
                    # 存储论文到数据库
                    paper_id = self._store_paper_to_db(paper)
                    if not paper_id:
                        logger.warning(f"存储论文失败: {paper['arxiv_id']}")
                        continue

                    # 计算并存储embedding
                    if self._compute_and_store_paper_embedding(paper_id, paper):
                        batch_success += 1
                        success_count += 1
                    else:
                        logger.warning(f"计算论文embedding失败: {paper['arxiv_id']}")

                except Exception as e:
                    logger.error(f"处理论文时出错 {paper['arxiv_id']}: {str(e)}")
                    continue

            logger.info(f"已处理批次 {i//batch_size + 1}, 当前批次成功: {batch_success}/{len(batch)}")

            # 批次间稍作延迟，避免API限流
            if i + batch_size < len(papers):
                time.sleep(2)

        logger.info(f"批量处理完成，总成功: {success_count}/{len(papers)}")
        return success_count

    def _store_paper_to_db(self, paper: Dict) -> Optional[int]:
        """
        将单篇论文存储到数据库

        Args:
            paper: 论文数据

        Returns:
            paper_id 如果成功，否则None
        """
        try:
            # 将作者列表转换为字符串
            authors_str = ", ".join(paper['authors']) if paper['authors'] else ""

            # 插入论文数据
            self.db.execute(
                """
                INSERT INTO papers (abstract, pdf_url, title, author)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    abstract = VALUES(abstract),
                    pdf_url = VALUES(pdf_url),
                    title = VALUES(title),
                    author = VALUES(author)
                """,
                (
                    paper['abstract'],
                    paper['pdf_url'],
                    paper['title'],
                    authors_str
                )
            )

            # 获取刚插入的paper_id
            result = self.db.query_one(
                "SELECT paper_id FROM papers WHERE pdf_url = %s",
                (paper['pdf_url'],)
            )

            if result:
                return result['paper_id']
            else:
                logger.error(f"无法获取论文ID: {paper['arxiv_id']}")
                return None

        except Exception as e:
            logger.error(f"存储论文到数据库失败 {paper['arxiv_id']}: {str(e)}")
            return None

    def _compute_and_store_paper_embedding(self, paper_id: int, paper: Dict) -> bool:
        """
        计算论文embedding并存储到数据库

        Args:
            paper_id: 论文ID
            paper: 论文数据

        Returns:
            是否成功
        """
        try:
            # 组合标题和摘要作为embedding输入
            text = f"{paper['title']} {paper['abstract']}".strip()
            if not text:
                logger.warning(f"论文{paper_id}没有有效文本内容")
                return False

            # 计算embedding
            embedding = self.embedding_service.embed_text(text, normalize=True)

            # 转换为JSON字符串
            embedding_str = json.dumps(embedding)

            # 存储到paper_embeddings表
            self.db.execute(
                """
                INSERT INTO paper_embeddings (paper_id, embedding)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE embedding = VALUES(embedding)
                """,
                (paper_id, embedding_str)
            )

            logger.debug(f"论文{paper_id}的embedding计算并存储成功")
            return True

        except RuntimeError as e:
            error_msg = str(e)
            if "quota" in error_msg.lower() or "429" in error_msg or "rate limit" in error_msg.lower():
                logger.warning(f"论文{paper_id}的embedding计算失败（配额限制）: {error_msg}")
            else:
                logger.error(f"论文{paper_id}的embedding计算失败: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"计算论文{paper_id}的embedding时出错: {str(e)}")
            return False


# 使用示例
if __name__ == "__main__":
    # 创建服务实例
    service = PaperFetchService()
    
    # 抓取前两天到前一天的论文
    papers = service.fetch_papers(max_results=None)
    
    # 打印结果
    print(f"\n成功抓取 {len(papers)} 篇论文")
    if papers:
        print("\n第一篇论文示例:")
        first_paper = papers[0]
        print(f"ID: {first_paper['arxiv_id']}")
        print(f"标题: {first_paper['title']}")
        print(f"作者: {', '.join(first_paper['authors'][:3])}...")
        print(f"发布日期: {first_paper['published_date']}")
        print(f"PDF链接: {first_paper['pdf_url']}")
