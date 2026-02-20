#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VQASynth 项目 Hugging Face 模型下载脚本
使用镜像站加速下载

运行前请确保安装：
pip install huggingface_hub
"""

import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置Hugging Face镜像站
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# logger.info("已设置 HF_ENDPOINT=https://hf-mirror.com")

# VQASynth项目需要的Hugging Face模型列表
MODELS_TO_DOWNLOAD = [
    {
        "repo_id": "facebook/VGGT-1B",
        "description": "VGGT 场景融合模型",
        "local_dir": None  # 使用默认缓存目录
    },
    {
        "repo_id": "facebook/sam2-hiera-small", 
        "description": "SAM2 分割模型",
        "local_dir": None
    },
    {
        "repo_id": "microsoft/Florence-2-base",
        "description": "Florence-2 图像描述模型", 
        "local_dir": None
    },
    {
        "repo_id": "cyan2k/molmo-7B-O-bnb-4bit",
        "description": "Molmo 视觉语言模型 (4bit量化版)",
        "local_dir": None
    }
]

def download_model(repo_id, description, local_dir=None):
    """下载单个模型"""
    try:
        logger.info(f"开始下载: {description} ({repo_id})")
        
        if local_dir:
            # 下载到指定目录
            path = snapshot_download(
                repo_id=repo_id,
                local_dir=local_dir,
                local_dir_use_symlinks=False,  # 不使用符号链接，直接复制文件
                resume_download=True  # 支持断点续传
            )
            logger.info(f"✅ {description} 下载完成，保存到: {path}")
        else:
            # 下载到默认缓存目录
            path = snapshot_download(
                repo_id=repo_id,
                resume_download=True
            )
            logger.info(f"✅ {description} 下载完成，保存到缓存目录: {path}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ {description} 下载失败: {str(e)}")
        return False



def main():
    """主函数"""
    logger.info("🚀 开始下载 VQASynth 项目所需的 Hugging Face 模型")
    logger.info("=" * 60)
    

    
    # 显示要下载的模型列表
    logger.info("📋 待下载模型列表:")
    for i, model in enumerate(MODELS_TO_DOWNLOAD, 1):
        logger.info(f"  {i}. {model['description']} ({model['repo_id']})")
    
    logger.info("=" * 60)
    
    # 下载模型
    success_count = 0
    total_count = len(MODELS_TO_DOWNLOAD)
    
    for model in MODELS_TO_DOWNLOAD:
        if download_model(
            repo_id=model["repo_id"],
            description=model["description"],
            local_dir=model["local_dir"]
        ):
            success_count += 1
        
        logger.info("-" * 40)
    
    # 下载总结
    logger.info("=" * 60)
    logger.info(f"📊 下载完成统计:")
    logger.info(f"  成功: {success_count}/{total_count}")
    logger.info(f"  失败: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        logger.info("🎉 所有模型下载完成！")
    else:
        logger.warning("⚠️  部分模型下载失败，请检查网络连接后重新运行")
    
    # 显示缓存目录位置
    cache_dir = os.path.expanduser("~/.cache/huggingface")
    logger.info(f"💾 模型缓存目录: {cache_dir}")

def download_specific_model(repo_id):
    """下载指定的模型（用于单独下载某个模型）"""
    model_info = next((m for m in MODELS_TO_DOWNLOAD if m["repo_id"] == repo_id), None)
    
    if model_info:
        return download_model(
            repo_id=model_info["repo_id"],
            description=model_info["description"],
            local_dir=model_info["local_dir"]
        )
    else:
        logger.error(f"未找到模型: {repo_id}")
        return False

if __name__ == "__main__":
    # 检查是否安装了必要的包
    try:
        import huggingface_hub
        logger.info(f"huggingface_hub 版本: {huggingface_hub.__version__}")
    except ImportError:
        logger.error("❌ 请先安装 huggingface_hub: pip install huggingface_hub")
        sys.exit(1)
    
    # 支持命令行参数下载指定模型
    if len(sys.argv) > 1:
        repo_id = sys.argv[1]
        logger.info(f"下载指定模型: {repo_id}")
        success = download_specific_model(repo_id)
        sys.exit(0 if success else 1)
    else:
        # 下载所有模型
        main() 