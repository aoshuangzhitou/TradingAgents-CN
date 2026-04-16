#!/usr/bin/env python3
"""
预下载本地 embedding 模型 (bge-base-zh-v1.5)
首次运行需要下载约 400MB 的模型文件
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # 国内镜像
def download_model():
    """下载并初始化 bge-base-zh-v1.5 模型"""
    print("🚀 开始下载本地 embedding 模型...")
    print("📦 模型: BAAI/bge-base-zh-v1.5")
    print("💾 预计大小: ~400MB")
    print("-" * 50)

    try:
        from chromadb.utils import embedding_functions

        print("📥 正在下载模型 (可能需要几分钟)...")

        # 初始化 embedding 函数，这会触发模型下载
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-base-zh-v1.5"
        )

        # 测试生成一个 embedding
        test_text = "这是一个测试文本"
        print(f"🧪 测试生成 embedding...")
        embeddings = embedding_func([test_text])
        embedding = embeddings[0].tolist()

        print("-" * 50)
        print(f"✅ 模型下载成功!")
        print(f"📊 向量维度: {len(embedding)}")
        print(f"🔢 示例向量前5个值: {embedding[:5]}")

        # 显示模型缓存路径
        import torch
        cache_dir = os.path.expanduser("~/.cache/torch/sentence_transformers")
        if os.path.exists(cache_dir):
            print(f"📁 模型缓存路径: {cache_dir}")
            # 计算缓存大小
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(cache_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            print(f"💾 缓存总大小: {total_size / 1024 / 1024:.2f} MB")

        return True

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("💡 请先安装依赖:")
        print("   pip install sentence-transformers chromadb")
        return False

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_model():
    """验证模型是否可用"""
    print("\n" + "=" * 50)
    print("🔍 验证模型可用性...")
    print("=" * 50)

    try:
        from chromadb.utils import embedding_functions

        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-base-zh-v1.5"
        )

        # 测试中文文本
        test_cases = [
            "这是一个测试文本",
            "Apple is a technology company",
            "股票行情分析",
            "Financial market analysis report",
        ]

        print("\n📝 测试不同文本的 embedding:")
        for text in test_cases:
            embeddings = embedding_func([text])
            embedding = embeddings[0].tolist()
            print(f"  '{text[:30]}...' -> 维度: {len(embedding)}, 前3个值: {embedding[:3]}")

        print("\n✅ 模型验证通过!")
        return True

    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 50)
    print("🤖 Embedding 模型下载工具")
    print("=" * 50)
    print()

    # 下载模型
    if download_model():
        # 验证模型
        verify_model()

        print("\n" + "=" * 50)
        print("🎉 全部完成!")
        print("=" * 50)
        print("\n现在你可以在项目中使用本地 embedding:")
        print("  export EMBEDDING_PROVIDER=chroma")
        print()
    else:
        print("\n❌ 下载失败，请检查网络连接和依赖安装")
        sys.exit(1)


if __name__ == "__main__":
    main()
