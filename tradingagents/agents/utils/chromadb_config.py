"""
ChromaDB 统一配置模块
适配 ChromaDB >= 0.4.x / 1.x API
"""
import platform
import chromadb
import logging

_logger = logging.getLogger("agents.utils.chromadb_config")

# 检测 ChromaDB 版本
try:
    CHROMADB_VERSION = chromadb.__version__
    _logger.info(f"📚 ChromaDB 版本: {CHROMADB_VERSION}")
except AttributeError:
    CHROMADB_VERSION = "unknown"


def is_windows_11() -> bool:
    """检测是否为 Windows 11（用于日志记录）"""
    if platform.system() != "Windows":
        return False
    version = platform.version()
    try:
        build_number = int(version.split('.')[2])
        return build_number >= 22000
    except (ValueError, IndexError):
        return False


def get_optimal_chromadb_client():
    """
    获取 ChromaDB 客户端（适配新版 API）

    ChromaDB >= 0.4.x / 1.x 使用简单 API：
    - chromadb.Client() - 内存模式
    - chromadb.PersistentClient(path) - 持久化模式

    Returns:
        chromadb.Client: ChromaDB 客户端实例
    """
    system = platform.system()

    try:
        # 新版 ChromaDB 直接使用 Client() 创建内存模式客户端
        client = chromadb.Client()

        # 记录系统信息（用于调试）
        if system == "Windows":
            _logger.info(f"✅ ChromaDB 初始化成功 (Windows {platform.version()})")
        else:
            _logger.info(f"✅ ChromaDB 初始化成功 ({system})")

        return client

    except Exception as e:
        _logger.error(f"❌ ChromaDB 初始化失败: {e}")
        raise


# 导出配置
__all__ = ['get_optimal_chromadb_client', 'is_windows_11']

