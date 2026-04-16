#!/usr/bin/env python3
"""
宏观新闻分析工具
获取CCTV财经新闻、东方财富全球资讯等宏观市场新闻
为新闻分析师提供市场整体走势和宏观经济背景分析

特性：
- 多数据源整合（CCTV + 东方财富）
- 智能去重（基于标题相似度）
- 长度控制（防止超出LLM上下文限制）
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

# 长度控制常量
MAX_TOTAL_LENGTH = 8000  # 总长度上限（字符）
MAX_NEWS_PER_SOURCE = 15  # 每个数据源最大条数
DEDUP_SIMILARITY_THRESHOLD = 0.65  # 去重相似度阈值（LCS比例>65%视为重复）
DEDUP_MIN_COMMON_WORDS = 3  # 最少共同关键词数（低于此数量不判定为重复）


class NewsItem:
    """新闻条目结构"""
    def __init__(self, title: str, content: str, source: str, time: str = "", channel: str = ""):
        self.title = title.strip()
        self.content = content.strip()
        self.source = source  # 来源标识：cctv / em_global
        self.time = time
        self.channel = channel

    def __repr__(self):
        return f"NewsItem(title={self.title[:30]}..., source={self.source})"


class MacroNewsAnalyzer:
    """宏观新闻分析器，整合多个宏观新闻源"""

    def __init__(self, toolkit):
        """初始化宏观新闻分析器

        Args:
            toolkit: 包含各种工具的工具包（用于调用OpenAI fallback）
        """
        self.toolkit = toolkit

    def get_macro_news(self, curr_date: str, max_news: int = MAX_NEWS_PER_SOURCE) -> str:
        """
        获取宏观市场新闻（带去重和长度控制）

        数据源优先级：
        1. AKShare news_cctv() - CCTV财经新闻（权威、及时）
        2. AKShare stock_info_global_em() - 东方财富全球资讯
        3. OpenAI API fallback

        处理流程：
        1. 分别获取各数据源的原始新闻列表
        2. 合并所有新闻条目
        3. 基于标题相似度去重
        4. 格式化输出并控制总长度

        Args:
            curr_date: 当前日期，格式 yyyy-mm-dd
            max_news: 每个数据源最大新闻数量

        Returns:
            str: 格式化的宏观新闻内容
        """
        logger.info(f"[宏观新闻工具] 开始获取宏观市场新闻，日期: {curr_date}")

        # 步骤1: 获取原始新闻列表
        all_news_items: List[NewsItem] = []

        # 优先级1: CCTV财经新闻
        try:
            cctv_items = self._get_cctv_news_raw(curr_date, max_news)
            if cctv_items:
                all_news_items.extend(cctv_items)
                logger.info(f"[宏观新闻工具] ✅ CCTV新闻获取成功: {len(cctv_items)} 条")
            else:
                logger.warning(f"[宏观新闻工具] ⚠️ CCTV新闻获取失败")
        except Exception as e:
            logger.warning(f"[宏观新闻工具] CCTV新闻获取失败: {e}")

        # 优先级2: 东方财富全球资讯
        try:
            em_items = self._get_global_em_news_raw(curr_date, max_news)
            if em_items:
                all_news_items.extend(em_items)
                logger.info(f"[宏观新闻工具] ✅ 东方财富全球资讯获取成功: {len(em_items)} 条")
            else:
                logger.warning(f"[宏观新闻工具] ⚠️ 东方财富全球资讯获取失败")
        except Exception as e:
            logger.warning(f"[宏观新闻工具] 东方财富全球资讯获取失败: {e}")

        # 如果以上数据源都失败，使用OpenAI fallback
        if not all_news_items:
            logger.info(f"[宏观新闻工具] 尝试使用OpenAI fallback...")
            try:
                if hasattr(self.toolkit, 'get_global_news_openai'):
                    openai_news = self.toolkit.get_global_news_openai.invoke({"curr_date": curr_date})
                    if openai_news and len(openai_news.strip()) > 100:
                        # OpenAI返回的是文本，直接使用
                        return self._format_text_result(openai_news, "OpenAI宏观新闻", curr_date)
            except Exception as e:
                logger.error(f"[宏观新闻工具] OpenAI fallback失败: {e}")

        if not all_news_items:
            return self._generate_fallback_message(curr_date)

        # 步骤2: 去重
        deduped_items = self._deduplicate_news(all_news_items)
        logger.info(f"[宏观新闻工具] 🔄 去重完成: {len(all_news_items)} → {len(deduped_items)} 条")

        # 步骤3: 格式化并控制长度
        formatted_result = self._format_news_items(deduped_items, curr_date)
        logger.info(f"[宏观新闻工具] 最终结果长度: {len(formatted_result)} 字符")

        return formatted_result

    def _get_cctv_news_raw(self, curr_date: str, max_news: int) -> List[NewsItem]:
        """从AKShare获取CCTV财经新闻（原始列表）

        Args:
            curr_date: 当前日期
            max_news: 最大新闻数量

        Returns:
            List[NewsItem]: CCTV新闻条目列表
        """
        logger.info(f"[宏观新闻工具] 尝试获取CCTV财经新闻（原始数据）...")

        try:
            import akshare as ak

            # 获取CCTV财经新闻
            cctv_df = ak.news_cctv()

            if cctv_df is None or cctv_df.empty:
                logger.warning(f"[宏观新闻工具] CCTV新闻DataFrame为空")
                return []

            logger.info(f"[宏观新闻工具] CCTV新闻获取到 {len(cctv_df)} 条原始数据")

            news_items = []
            for i, row in cctv_df.head(max_news).iterrows():
                title = row.get('title', '') or row.get('新闻标题', '')
                content = row.get('content', '') or row.get('内容', '')
                publish_time = row.get('publish_time', '') or row.get('发布时间', '')
                channel = row.get('channel', '') or row.get('频道', '')

                if title and len(title.strip()) > 5:  # 过滤空标题或过短标题
                    news_items.append(NewsItem(
                        title=title.strip(),
                        content=content.strip()[:200] if content else "",  # 截取摘要
                        source="cctv",
                        time=str(publish_time),
                        channel=str(channel) if channel else ""
                    ))

            return news_items

        except ImportError:
            logger.warning(f"[宏观新闻工具] akshare未安装")
            return []
        except Exception as e:
            logger.error(f"[宏观新闻工具] CCTV新闻获取异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _get_global_em_news_raw(self, curr_date: str, max_news: int) -> List[NewsItem]:
        """从AKShare获取东方财富全球资讯（原始列表）

        Args:
            curr_date: 当前日期
            max_news: 最大新闻数量

        Returns:
            List[NewsItem]: 东方财富全球资讯条目列表
        """
        logger.info(f"[宏观新闻工具] 尝试获取东方财富全球资讯（原始数据）...")

        try:
            import akshare as ak

            # 获取东方财富全球资讯
            global_df = ak.stock_info_global_em()

            if global_df is None or global_df.empty:
                logger.warning(f"[宏观新闻工具] 东方财富全球资讯DataFrame为空")
                return []

            logger.info(f"[宏观新闻工具] 东方财富全球资讯获取到 {len(global_df)} 条原始数据")

            news_items = []
            for i, row in global_df.head(max_news).iterrows():
                title = row.get('标题', '') or row.get('title', '')
                content = row.get('内容', '') or row.get('content', '')
                time_str = row.get('时间', '') or row.get('time', '')

                if title and len(title.strip()) > 5:
                    news_items.append(NewsItem(
                        title=title.strip(),
                        content=content.strip()[:200] if content else "",
                        source="em_global",
                        time=str(time_str),
                        channel=""
                    ))

            return news_items

        except ImportError:
            logger.warning(f"[宏观新闻工具] akshare未安装")
            return []
        except Exception as e:
            logger.error(f"[宏观新闻工具] 东方财富全球资讯获取异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _deduplicate_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """去重新闻条目（基于标题相似度）

        算法：
        1. 精确匹配去重（相同标题）
        2. 相似度去重（需同时满足两个条件）：
           - 标题相似度 > 阈值 (70%)
           - 共同关键词数量 >= 最小阈值 (3个)

        Args:
            news_items: 原始新闻列表

        Returns:
            List[NewsItem]: 去重后的新闻列表
        """
        if not news_items:
            return []

        deduped = []
        seen_titles = set()  # 用于精确匹配去重

        for item in news_items:
            # 步骤1: 精确匹配
            normalized_title = self._normalize_title(item.title)
            if normalized_title in seen_titles:
                logger.debug(f"[宏观新闻工具] 🔄 精确去重: '{item.title[:30]}...'")
                continue

            # 步骤2: 相似度检查（双重条件）
            is_duplicate = False
            for existing in deduped:
                similarity, common_count = self._calculate_title_similarity_with_count(
                    item.title, existing.title
                )
                # 双重条件：相似度 > 70% 且 共同关键词 >= 3个
                if similarity > DEDUP_SIMILARITY_THRESHOLD and common_count >= DEDUP_MIN_COMMON_WORDS:
                    logger.debug(
                        f"[宏观新闻工具] 🔄 相似度去重: '{item.title[:30]}...' "
                        f"与 '{existing.title[:30]}...' (相似度={similarity:.2f}, 共同词={common_count})"
                    )
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduped.append(item)
                seen_titles.add(normalized_title)

        return deduped

    def _normalize_title(self, title: str) -> str:
        """标准化标题（用于精确匹配）

        Args:
            title: 原始标题

        Returns:
            str: 标准化后的标题
        """
        # 去除空格、标点，转小写
        import re
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', title)  # 保留中文和字母数字
        return normalized.lower().strip()

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """计算标题相似度（基于关键词重叠）

        Args:
            title1: 标题1
            title2: 标题2

        Returns:
            float: 相似度 (0-1)
        """
        similarity, _ = self._calculate_title_similarity_with_count(title1, title2)
        return similarity

    def _calculate_title_similarity_with_count(self, title1: str, title2: str) -> Tuple[float, int]:
        """计算标题相似度并返回共同关键词数量

        算法（优化版）：
        1. 主指标：LCS比例（最长公共子序列）- 更稳健
        2. 辅指标：关键词重叠数

        Args:
            title1: 标题1
            title2: 标题2

        Returns:
            Tuple[float, int]: (相似度, 共同关键词数量)
        """
        # 计算最长公共子序列（LCS）
        def lcs_length(s1: str, s2: str) -> int:
            """计算两个字符串的最长公共子序列长度"""
            m, n = len(s1), len(s2)
            # 使用动态规划（优化版，只保留两行）
            prev = [0] * (n + 1)
            curr = [0] * (n + 1)

            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i-1] == s2[j-1]:
                        curr[j] = prev[j-1] + 1
                    else:
                        curr[j] = max(prev[j], curr[j-1])
                prev, curr = curr, [0] * (n + 1)

            return prev[n]

        # 计算LCS比例
        lcs_len = lcs_length(title1, title2)
        max_len = max(len(title1), len(title2))

        if max_len == 0:
            return 0.0, 0

        lcs_ratio = lcs_len / max_len

        # 提取关键词用于辅助判断
        def extract_common_words(s1: str, s2: str) -> int:
            """提取共同关键词数量"""
            import re
            # 提取2-4字的词片段（全覆盖）
            words1 = set()
            words2 = set()

            for length in [4, 3, 2]:
                for i in range(len(s1) - length + 1):
                    seg = s1[i:i+length]
                    if re.match(r'^[\u4e00-\u9fff]+$', seg):
                        words1.add(seg)
                for i in range(len(s2) - length + 1):
                    seg = s2[i:i+length]
                    if re.match(r'^[\u4e00-\u9fff]+$', seg):
                        words2.add(seg)

            return len(words1 & words2)

        common_count = extract_common_words(title1, title2)

        # 相似度使用LCS比例（更稳健）
        return lcs_ratio, common_count

    def _format_news_items(self, news_items: List[NewsItem], curr_date: str) -> str:
        """格式化新闻条目并控制长度

        Args:
            news_items: 去重后的新闻列表
            curr_date: 当前日期

        Returns:
            str: 格式化的新闻报告
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 按来源分组
        cctv_items = [item for item in news_items if item.source == "cctv"]
        em_items = [item for item in news_items if item.source == "em_global"]

        # 构建内容
        content_parts = []

        if cctv_items:
            cctv_content = self._format_source_news(cctv_items, "CCTV财经新闻")
            content_parts.append(cctv_content)

        if em_items:
            em_content = self._format_source_news(em_items, "东方财富全球资讯")
            content_parts.append(em_content)

        combined_content = "\n\n---\n\n".join(content_parts)

        # 长度控制
        if len(combined_content) > MAX_TOTAL_LENGTH:
            logger.warning(f"[宏观新闻工具] ⚠️ 内容过长({len(combined_content)}字符)，进行智能截断...")
            combined_content = self._smart_truncate(combined_content, MAX_TOTAL_LENGTH)

        # 构建最终报告
        formatted_result = f"""
=== 📰 宏观市场新闻 ===
获取时间: {timestamp}
分析日期: {curr_date}
新闻总数: {len(news_items)} 条 (已去重)
来源分布: CCTV {len(cctv_items)}条 + 东方财富 {len(em_items)}条

=== 📋 新闻内容 ===
{combined_content}

=== 💡 分析指引 ===
请重点关注以下宏观因素对个股的影响：
1. **政策变化**：货币政策、财政政策、产业政策调整
2. **经济数据**：GDP、通胀、就业、PMI等关键指标
3. **国际形势**：全球经济、地缘政治、贸易政策
4. **市场情绪**：大盘走势、板块轮动、资金流向
5. **行业动态**：行业政策、监管变化、竞争格局

=== ✅ 数据状态 ===
状态: 成功获取宏观新闻 (已去重)
来源: CCTV财经 + 东方财富全球资讯
时间戳: {timestamp}
"""
        return formatted_result.strip()

    def _format_source_news(self, items: List[NewsItem], source_name: str) -> str:
        """格式化单个来源的新闻

        Args:
            items: 新闻条目列表
            source_name: 来源名称

        Returns:
            str: 格式化的新闻内容
        """
        news_lines = [f"## {source_name}\n"]

        for i, item in enumerate(items, 1):
            line = f"{i}. **{item.title}**"
            if item.time:
                line += f" [{item.time}]"
            if item.channel:
                line += f" [{item.channel}]"
            if item.content:
                line += f"\n   {item.content}"
            news_lines.append(line)

        return "\n".join(news_lines)

    def _smart_truncate(self, content: str, max_length: int) -> str:
        """智能截断内容（优先保留重要新闻）

        Args:
            content: 原始内容
            max_length: 最大长度

        Returns:
            str: 截断后的内容
        """
        # 定义重要关键词（政策、经济数据、重大事件）
        important_keywords = [
            '央行', '货币政策', '利率', 'GDP', '通胀', 'PMI',
            '政策', '国务院', '监管', '经济', '财政',
            '美联储', '加息', '降息', '贸易', '关税',
            '股市', '大盘', '指数', '板块'
        ]

        # 分行处理
        lines = content.split('\n')
        important_lines = []
        other_lines = []

        for line in lines:
            is_important = any(kw in line for kw in important_keywords)
            if is_important:
                important_lines.append(line)
            else:
                other_lines.append(line)

        # 优先保留重要内容
        result_lines = important_lines[:]

        # 计算剩余空间
        current_length = sum(len(line) + 1 for line in result_lines)
        remaining_space = max_length - current_length - 100  # 留100字符给结尾说明

        # 添加其他内容直到达到限制
        for line in other_lines:
            if current_length + len(line) + 1 < remaining_space:
                result_lines.append(line)
                current_length += len(line) + 1
            else:
                break

        result = "\n".join(result_lines)
        result += "\n\n... (内容已智能截断，优先保留重要新闻)"

        return result

    def _format_text_result(self, text: str, source: str, curr_date: str) -> str:
        """格式化纯文本结果（用于OpenAI fallback）

        Args:
            text: 文本内容
            source: 来源名称
            curr_date: 当前日期

        Returns:
            str: 格式化的结果
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 长度控制
        if len(text) > MAX_TOTAL_LENGTH:
            text = text[:MAX_TOTAL_LENGTH] + "...(已截断)"

        return f"""
=== 📰 宏观市场新闻 ===
获取时间: {timestamp}
分析日期: {curr_date}
数据来源: {source}

=== 📋 新闻内容 ===
{text}

=== ✅ 数据状态 ===
状态: 成功获取宏观新闻
来源: {source}
时间戳: {timestamp}
""".strip()

    def _generate_fallback_message(self, curr_date: str) -> str:
        """生成备选消息（当所有数据源都失败时）

        Args:
            curr_date: 当前日期

        Returns:
            str: 备选消息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""
=== ⚠️ 宏观新闻获取失败 ===
获取时间: {timestamp}
分析日期: {curr_date}

抱歉，当前无法获取宏观市场新闻数据。可能的原因：
1. 网络连接问题
2. AKShare数据源暂时不可用
3. 需要安装akshare依赖

建议：
- 请检查网络连接
- 确保已安装akshare: pip install akshare
- 可以尝试稍后重新获取

注意：虽然无法获取宏观新闻，您仍应基于个股新闻和市场数据进行分析，
但请在报告中注明宏观背景数据缺失的情况。
""".strip()


def create_macro_news_tool(toolkit):
    """创建宏观新闻工具函数

    Args:
        toolkit: 工具包对象

    Returns:
        function: 宏观新闻获取工具函数
    """
    analyzer = MacroNewsAnalyzer(toolkit)

    def get_macro_market_news(curr_date: str, max_news: int = MAX_NEWS_PER_SOURCE):
        """
        获取宏观市场新闻工具（带去重和长度控制）

        Args:
            curr_date (str): 当前日期，格式 yyyy-mm-dd
            max_news (int): 每个数据源最大新闻数量，默认15

        Returns:
            str: 格式化的宏观新闻内容（已去重）
        """
        if not curr_date:
            return "❌ 错误: 未提供日期参数"

        return analyzer.get_macro_news(curr_date, max_news)

    # 设置工具属性
    get_macro_market_news.name = "get_macro_market_news"
    get_macro_market_news.description = """
宏观市场新闻获取工具 - 获取影响整体市场的宏观经济新闻

功能:
- 获取CCTV财经新闻（权威、及时）
- 获取东方财富全球资讯
- **智能去重**：自动去除重复新闻
- **长度控制**：防止超出LLM上下文限制
- 获取宏观经济政策、经济数据、国际形势等新闻
- 提供宏观因素对个股影响的分析指引

重点关注:
- 货币政策、财政政策调整
- GDP、通胀、就业、PMI等经济数据
- 全球经济形势和地缘政治
- 大盘走势和资金流向
- 行业政策和监管变化

使用场景:
- 分析个股时了解整体市场环境
- 评估政策变化对股票的影响
- 判断宏观经济背景下的投资时机

技术特性:
- 标题相似度去重（阈值60%）
- 总长度上限8000字符
- 智能截断保留重要新闻
"""

    return get_macro_market_news