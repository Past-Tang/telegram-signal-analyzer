# -*- coding: utf-8 -*-
"""
配置文件
包含Telegram API、OpenAI API和Gate.io API的配置信息
"""

# Telegram API配置
TELEGRAM_CONFIG = {
    'API_ID': 12345678,  # Replace with your Telegram API ID
    'API_HASH': 'your_api_hash_here',
    'PHONE_NUMBER': '+1234567890',
    'SESSION_FILE': 'telegram.session',
    'TARGET_CHANNEL_IDS': [
        -1001234567890,  # Replace with your target channel ID
    ],

    # 超级群组话题监听配置
    'TARGET_TOPICS': {
        -1001234567890: [12345]  # Replace with your group -> topic mapping
    }
}

# OpenAI API配置
OPENAI_CONFIG = {
    'API_KEY': 'your_openai_api_key_here',
    'BASE_URL': 'https://api.siliconflow.cn/v1',
    'MODEL': 'Qwen/Qwen3-235B-A22B-Instruct-2507'
}

# Gate.io API配置
GATE_CONFIG = {
    'API_KEY': 'your_gate_api_key_here',
    'API_SECRET': 'your_gate_api_secret_here',
    'HOST': 'https://fx-api-testnet.gateio.ws/api/v4',
    'SETTLE': 'usdt',  # 结算货币
    'LEVERAGE': 10,    # 默认杠杆
    'MARGIN_AMOUNT': 50  # 固定保证金金额(USDT)
}

# 交易策略配置
TRADING_CONFIG = {
    'TAKE_PROFIT_MODE': 'first_price',  # 止盈模式: 'first_price' 或 'percentage'
    'TAKE_PROFIT_PERCENTAGE': 2.0,      # 止盈百分比 (当模式为percentage时使用)
    'STOP_LOSS_PERCENTAGE': 1.5         # 止损百分比 (备用，如果信号中没有止损价格)
}

# 其他配置
OTHER_CONFIG = {
    'SIGNALS_FILE': 'trading_signals.json',
    'LOG_FILE': 'telegram_monitor.log'
}
