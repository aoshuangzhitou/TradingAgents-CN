"""
QuotesService: 提供A股批量实时快照获取（AKShare东方财富 spot 接口），带内存TTL缓存。
- 不使用通达信（TDX）作为兜底数据源。
- 仅用于筛选返回前对 items 进行行情富集。
"""
from __future__ import annotations

import asyncio
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        # 处理字符串中的逗号/百分号/空白
        if isinstance(v, str):
            s = v.strip().replace(",", "")
            if s.endswith("%"):
                s = s[:-1]
            if s == "-" or s == "":
                return None
            return float(s)
        # 处理 pandas/numpy 数值
        return float(v)
    except Exception:
        return None


class QuotesService:
    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = ttl_seconds
        self._cache_ts: float = 0.0
        self._cache: Dict[str, Dict[str, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get_quotes(self, codes: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """获取一批股票的近实时快照（最新价、涨跌幅、成交额）。
        - 优先使用缓存；缓存超时或为空则刷新一次全市场快照。
        - 返回仅包含请求的 codes。
        """
        codes = [c.strip() for c in codes if c]
        now = time.time()
        async with self._lock:
            if self._cache and (now - self._cache_ts) < self._ttl:
                return {c: q for c, q in self._cache.items() if c in codes and q}
            # 刷新缓存（阻塞IO放到线程）
            data = await asyncio.to_thread(self._fetch_spot_akshare)
            self._cache = data
            self._cache_ts = time.time()
            return {c: q for c, q in self._cache.items() if c in codes and q}

    def _fetch_spot_akshare(self) -> Dict[str, Dict[str, Optional[float]]]:
        """通过 AKShare 获取全市场快照，并标准化为字典。
        预期列（常见）：代码、名称、最新价、涨跌幅、成交额。
        不同版本可能有差异，做多列名兼容。

        🔥 优先使用东方财富接口，失败时回退到新浪接口
        """
        result: Dict[str, Dict[str, Optional[float]]] = {}

        # 1. 尝试东方财富接口（首选）
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not getattr(df, "empty", True):
                # 兼容常见列名
                code_col = next((c for c in ["代码", "代码code", "symbol", "股票代码"] if c in df.columns), None)
                price_col = next((c for c in ["最新价", "现价", "最新价(元)", "price", "最新"] if c in df.columns), None)
                pct_col = next((c for c in ["涨跌幅", "涨跌幅(%)", "涨幅", "pct_chg"] if c in df.columns), None)
                amount_col = next((c for c in ["成交额", "成交额(元)", "amount", "成交额(万元)"] if c in df.columns), None)

                if code_col and price_col:
                    for _, row in df.iterrows():
                        code_raw = row.get(code_col)
                        if not code_raw:
                            continue
                        code_str = str(code_raw).strip()
                        if code_str.isdigit():
                            code_clean = code_str.lstrip('0') or '0'
                            code = code_clean.zfill(6)
                        else:
                            code = code_str.zfill(6)
                        close = _safe_float(row.get(price_col))
                        pct = _safe_float(row.get(pct_col)) if pct_col else None
                        amt = _safe_float(row.get(amount_col)) if amount_col else None
                        result[code] = {"close": close, "pct_chg": pct, "amount": amt}
                    logger.info(f"✅ AKShare 东方财富 spot 拉取完成: {len(result)} 条")
                    return result
                else:
                    logger.warning(f"⚠️ 东方财富 spot 缺少必要列: code={code_col}, price={price_col}")
        except Exception as e:
            logger.warning(f"⚠️ 东方财富 spot 失败: {e}, 尝试新浪备用...")

        # 2. 回退到新浪接口（代码格式：sz000001, sh600036）
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot()
            if df is not None and not getattr(df, "empty", True):
                code_col = next((c for c in ["代码", "代码code", "symbol", "股票代码"] if c in df.columns), None)
                price_col = next((c for c in ["最新价", "现价", "最新价(元)", "price", "最新"] if c in df.columns), None)
                pct_col = next((c for c in ["涨跌幅", "涨跌幅(%)", "涨幅", "pct_chg"] if c in df.columns), None)
                amount_col = next((c for c in ["成交额", "成交额(元)", "amount", "成交额(万元)"] if c in df.columns), None)

                if code_col and price_col:
                    for _, row in df.iterrows():
                        code_raw = row.get(code_col)
                        if not code_raw:
                            continue
                        code_str = str(code_raw).strip().lower()

                        # 🔥 新浪接口代码格式：sz000001, sh600036, bj920005
                        # 需要去掉市场前缀，只保留6位数字代码
                        if code_str.startswith('sz') or code_str.startswith('sh') or code_str.startswith('bj'):
                            # 市场前缀格式：去掉前缀，保留纯数字
                            pure_code = code_str[2:]  # 去掉前2位市场前缀
                            if pure_code.isdigit():
                                code_clean = pure_code.lstrip('0') or '0'
                                code = code_clean.zfill(6)
                            else:
                                code = pure_code.zfill(6)
                        elif code_str.isdigit():
                            # 纯数字格式
                            code_clean = code_str.lstrip('0') or '0'
                            code = code_clean.zfill(6)
                        else:
                            # 其他格式，保留原样
                            code = code_str

                        close = _safe_float(row.get(price_col))
                        pct = _safe_float(row.get(pct_col)) if pct_col else None
                        amt = _safe_float(row.get(amount_col)) if amount_col else None
                        result[code] = {"close": close, "pct_chg": pct, "amount": amt}
                    logger.info(f"✅ AKShare 新浪 spot 拉取完成: {len(result)} 条")
                    return result
                else:
                    logger.error(f"❌ 新浪 spot 缺少必要列: code={code_col}, price={price_col}")
        except Exception as e:
            logger.error(f"❌ 新浪 spot 也失败: {e}")

        return result


_quotes_service: Optional[QuotesService] = None


def get_quotes_service() -> QuotesService:
    global _quotes_service
    if _quotes_service is None:
        _quotes_service = QuotesService(ttl_seconds=30)
    return _quotes_service

