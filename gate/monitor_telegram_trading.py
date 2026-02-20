import asyncio
import json
import random
import time
from datetime import datetime
from telethon import TelegramClient, events, errors
from telethon.network.connection import ConnectionTcpAbridged, ConnectionTcpFull
from telethon.tl.functions.updates import GetStateRequest
from openai import OpenAI
from pydantic import BaseModel, ValidationError, model_validator
from typing import List, Optional, Union, Dict, Any, Tuple

# 性能优化模块
try:
    from performance_optimization import (
        apply_system_optimizations,
        PerformanceOptimizer,
        print_optimization_report
    )
    PERFORMANCE_MODULE_AVAILABLE = True
except ImportError:
    PERFORMANCE_MODULE_AVAILABLE = False
    print("⚠️ 性能优化模块不可用，使用默认配置")

# 导入配置
from config import TELEGRAM_CONFIG, OPENAI_CONFIG, OTHER_CONFIG
# 导入交易模块
from gate_trading import execute_trade

# 从test.py复制的交易信号模型
class TradingSignal(BaseModel):
    trading_pair: str
    direction: str
    entry_price: List[Union[str, float]]
    target_price: List[float]
    stop_loss: float

    @model_validator(mode='after')
    def check_prices_logic(self) -> 'TradingSignal':
        """
        验证交易信号中的价格逻辑是否一致。
        - 多单: 目标价应高于入场价，止损价应低于入场价。
        - 空单: 目标价应低于入场价，止损价应高于入场价。
        """
        # 获取一个纯数字的入场价格列表用于比较
        numeric_entry_prices = [p for p in self.entry_price if isinstance(p, (int, float))]
        
        # 如果没有数字价格（例如只有 "现价"），则无法进行逻辑比较，跳过验证
        if not numeric_entry_prices:
            return self

        min_entry = min(numeric_entry_prices)
        max_entry = max(numeric_entry_prices)
        
        min_target = min(self.target_price)
        max_target = max(self.target_price)

        if self.direction == 'long':
            if min_target <= max_entry:
                raise ValueError(f"逻辑冲突 (多单): 最低目标价 {min_target} 必须高于最高入场价 {max_entry}。")
            if self.stop_loss >= min_entry:
                raise ValueError(f"逻辑冲突 (多单): 止损价 {self.stop_loss} 必须低于最低入场价 {min_entry}。")
        
        elif self.direction == 'short':
            if max_target >= min_entry:
                raise ValueError(f"逻辑冲突 (空单): 最高目标价 {max_target} 必须低于最低入场价 {min_entry}。")
            if self.stop_loss <= max_entry:
                raise ValueError(f"逻辑冲突 (空单): 止损价 {self.stop_loss} 必须高于最高入场价 {max_entry}。")
                
        return self

# 设置OpenAI客户端
client = OpenAI(
    api_key=OPENAI_CONFIG['API_KEY'],
    base_url=OPENAI_CONFIG['BASE_URL']
)

# 从test.py复制的交易信号提取函数，修改为同时返回原始JSON响应和解析后的信号
def extract_trade_signal(text: str) -> Tuple[Optional[TradingSignal], Dict[str, Any]]:
    """
    使用 OpenAI 模型从文本中提取交易信号并用 Pydantic 进行验证。
    成功则返回 TradingSignal 对象和原始JSON，失败则返回 None和原始JSON。
    """
    # 增强的提示，包含处理"现价"的例子
    prompt = f"""
你是一个专业的金融交易信号提取助手。
你的任务是从给定的文本中提取交易信息，并严格按照指定的 JSON 格式输出。

这里有四个例子来指导你：

---
例子 1：范围价格 (可执行指令)
- 输入文本:
"BTC 116000-115500附近多
目標 ；117000-118000附近
止損: 114800附近"
- 输出 JSON:
{{
  "trading_pair": "BTC/USDT",
  "direction": "long",
  "entry_price": [116000, 115500],
  "target_price": [117000, 118000],
  "stop_loss": 114800
}}

---
例子 2：现价 (可执行指令)
- 输入文本:
"ETH ；现价轻仓进-3625附近补仓多
目標 ；3674-—3700
止損:3615附近"
- 输出 JSON:
{{
  "trading_pair": "ETH/USDT",
  "direction": "long",
  "entry_price": ["现价", 3625],
  "target_price": [3674, 3700],
  "stop_loss": 3615
}}

---
例子 3：条件性指令 (非可执行指令，应忽略)
- 输入文本:
"白盤留意117100-117600附近不破區間留意多單"
- 输出 JSON:
{{}}

---
例子 4：缺少明确方向 (非可执行指令，应忽略)
- 输入文本:
"移動到116000-116500附近，目標在117000-118000附近，止損在115300附近"
- 输出 JSON:
{{}}
---

现在，请从以下文本中提取交易信号。只提取可直接执行的明确指令。信号必须包含明确的 '多' 或 '空' 方向。对于市场分析、条件性指令、或不完整的信号，请返回一个空的 JSON 对象 {{}}。
---
文本：
{text}
---
"""
    try:
        response = client.chat.completions.create(
            model=OPENAI_CONFIG['MODEL'],
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON, strictly following the user's specified format."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_response = response.choices[0].message.content
        response_data = json.loads(raw_response)
        
        # 预先检查关键字段是否存在，如果不存在或为空，则认为不是有效信号
        required_keys = ["direction", "entry_price", "target_price", "stop_loss"]
        if not response_data or not all(key in response_data for key in required_keys):
            return None, response_data

        trade_data = TradingSignal.model_validate(response_data)
        return trade_data, response_data

    except ValidationError as e:
        # 直接打印ValidationError的字符串形式，可以更清晰地显示自定义错误
        print(f"  - 数据验证失败: {e}")
        return None, {"error": str(e)}
    except (json.JSONDecodeError, IndexError) as e:
        print(f"  - JSON 解析或响应格式错误: {e}")
        return None, {"error": str(e)}
    except Exception as e:
        print(f"  - 发生未知错误: {e}")
        return None, {"error": str(e)}

# 从配置文件获取Telegram API配置
API_ID = TELEGRAM_CONFIG['API_ID']
API_HASH = TELEGRAM_CONFIG['API_HASH']
PHONE_NUMBER = TELEGRAM_CONFIG['PHONE_NUMBER']
SESSION_FILE = TELEGRAM_CONFIG['SESSION_FILE']
TARGET_CHANNEL_IDS = TELEGRAM_CONFIG['TARGET_CHANNEL_IDS']
TARGET_TOPICS = TELEGRAM_CONFIG.get('TARGET_TOPICS', {})

# 信号历史存储
signal_history = []

class ExponentialBackoff:
    """指数退避重试策略"""
    def __init__(self, base_delay=5, max_delay=300, factor=2):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.attempt = 0

    def delay(self):
        """计算下一次重试的延迟时间，并增加尝试次数"""
        wait = min(self.base_delay * (self.factor ** self.attempt), self.max_delay)
        # 添加随机抖动以避免所有客户端同时重连
        jitter = random.uniform(0.8, 1.2)
        wait = wait * jitter
        self.attempt += 1
        return wait

    def reset(self):
        """重置尝试次数"""
        self.attempt = 0

async def create_telegram_client():
    """创建并返回一个优化的Telegram客户端"""
    # 🚀 高性能连接配置
    client = TelegramClient(
        SESSION_FILE,
        API_ID,
        API_HASH,
        # 连接优化
        connection=ConnectionTcpFull,     # 使用完整TCP连接，更稳定
        connection_retries=5,             # 减少重试次数，加快失败检测
        retry_delay=1,                    # 减少重试延迟
        timeout=10,                       # 减少超时时间，更快响应
        request_retries=3,                # 请求重试次数
        flood_sleep_threshold=60,         # 防洪水攻击阈值
        auto_reconnect=True,              # 自动重连
        sequential_updates=False,         # 🚀 关键：允许并行处理更新
        # 启用更新缓存
        catch_up=True                     # 启用追赶模式，获取离线时的消息
    )
    return client

async def save_signal_to_file(signal_dict):
    """将交易信号异步地保存到JSON文件，避免阻塞事件循环"""
    def _save():
        try:
            # 读取现有信号
            try:
                with open(OTHER_CONFIG['SIGNALS_FILE'], 'r', encoding='utf-8') as f:
                    signals = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                signals = []

            # 添加新信号
            signals.append(signal_dict)

            # 写入文件
            with open(OTHER_CONFIG['SIGNALS_FILE'], 'w', encoding='utf-8') as f:
                json.dump(signals, f, ensure_ascii=False, indent=4)

            print(f"交易信号已保存到 {OTHER_CONFIG['SIGNALS_FILE']}")
        except Exception as e:
            print(f"保存交易信号时出错: {e}")

    await asyncio.to_thread(_save)

async def handle_messages(client, backoff):
    """处理消息并设置事件处理程序"""
    print(f"\n=== 设置消息监听器 ===")
    print(f"目标频道IDs: {TARGET_CHANNEL_IDS}")
    print(f"目标话题配置: {TARGET_TOPICS}")

    # 🚀 高性能消息监听器配置
    target_chats = list(TARGET_CHANNEL_IDS) + list(TARGET_TOPICS.keys())

    @client.on(events.NewMessage(
        chats=target_chats,
        # 优化参数
        incoming=True,              # 只监听传入消息
        outgoing=False,             # 不监听发出消息
        from_users=None,            # 监听所有用户
        forwards=None,              # 包含转发消息
        pattern=None,               # 不使用模式匹配（更快）
        blacklist_chats=False,      # 不使用黑名单
        func=None                   # 不使用额外过滤函数
    ))
    async def handle_new_message(event):
        message = event.message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 检查消息来源
        chat_id = None
        if hasattr(message, 'peer_id'):
            if hasattr(message.peer_id, 'channel_id'):
                chat_id = -int(message.peer_id.channel_id) - 1000000000000
            elif hasattr(message.peer_id, 'chat_id'):
                chat_id = -message.peer_id.chat_id
            elif hasattr(message.peer_id, 'user_id'):
                chat_id = message.peer_id.user_id

        # 检查话题信息（如果是超级群组消息）
        topic_id = None
        if hasattr(message, 'reply_to') and message.reply_to:
            if hasattr(message.reply_to, 'reply_to_msg_id'):
                topic_id = message.reply_to.reply_to_msg_id

        # 快速预过滤：只对目标频道/群组显示调试信息
        if chat_id in TARGET_TOPICS or chat_id in TARGET_CHANNEL_IDS:
            print(f"\n⚡ [快速处理] 目标消息 (ID: {message.id}):")
            print(f"   频道ID: {chat_id} | 话题ID: {topic_id}")
            print(f"   文本预览: {message.text[:30] if message.text else 'None'}...")

        # 🚀 快速过滤：提前退出不相关消息
        # 1. 快速检查是否为目标频道
        is_target_channel = chat_id in TARGET_CHANNEL_IDS

        # 2. 快速检查是否为目标话题
        is_target_topic = False
        if chat_id in TARGET_TOPICS:
            target_topics = TARGET_TOPICS[chat_id]
            is_target_topic = topic_id in target_topics

        # 如果不是目标频道或话题，立即返回
        if not (is_target_channel or is_target_topic):
            return

        # 快速过滤：媒体消息和无文本消息
        if message.media or not message.text:
            return

        # 🚀 创建异步任务处理消息，立即返回继续监听
        print(f"   🚀 处理消息 {message.id}")
        asyncio.create_task(process_message_async(message, chat_id, topic_id, timestamp))

    async def process_message_async(message, chat_id, topic_id, timestamp):
        """异步处理消息的核心逻辑"""
        try:
            text = message.text

            print(f"\n\n{'='*60}")
            print(f"🔄 异步处理消息 (ID: {message.id}, 时间: {timestamp}):")
            print(f"{'='*60}")
            print(f"{text}")
            print(f"{'='*60}")

            # 提取交易信号
            print("正在分析消息...")
            signal, raw_json = await asyncio.to_thread(extract_trade_signal, text)

            # 输出大模型返回的原始JSON数据
            print(f"\n【大模型原始JSON输出】:")
            print(f"{'-'*60}")
            print(json.dumps(raw_json, ensure_ascii=False, indent=2))
            print(f"{'-'*60}")

            if signal:
                signal_dict = signal.model_dump()
                signal_dict['timestamp'] = timestamp
                signal_dict['message_id'] = message.id
                signal_dict['original_text'] = text
                signal_dict['raw_json'] = raw_json  # 保存原始JSON数据
                signal_history.append(signal_dict)

                print(f"\n✅ 检测到交易信号! (消息ID: {message.id})")
                print(f"{'='*60}")
                print(f"交易对: {signal.trading_pair}")
                print(f"方向: {'多' if signal.direction == 'long' else '空'}")
                print(f"入场价: {signal.entry_price}")
                print(f"目标价: {signal.target_price}")
                print(f"止损: {signal.stop_loss}")
                print(f"{'='*60}")

                # 将信号保存到文件
                await save_signal_to_file(signal_dict)

                # 执行交易
                print(f"\n🚀 开始执行交易... (消息ID: {message.id})")
                try:
                    trade_result = await execute_trade(signal_dict)

                    if trade_result.get('success'):
                        print(f"✅ 交易执行成功! (消息ID: {message.id})")
                        print(f"交易对: {trade_result['symbol']}")
                        print(f"方向: {'多' if trade_result['direction'] == 'long' else '空'}")
                        print(f"入场价格: {trade_result['entry_price']}")
                        print(f"仓位大小: {trade_result['position_size']}")
                        print(f"创建订单数: {len(trade_result['orders'])}")

                        # 更新信号字典，添加交易结果
                        signal_dict['trade_result'] = trade_result
                        signal_dict['trade_executed'] = True

                        # 重新保存包含交易结果的信号
                        await save_signal_to_file(signal_dict)

                    else:
                        print(f"❌ 交易执行失败 (消息ID: {message.id}): {trade_result.get('error', '未知错误')}")
                        signal_dict['trade_result'] = trade_result
                        signal_dict['trade_executed'] = False
                        await save_signal_to_file(signal_dict)

                except Exception as e:
                    print(f"❌ 交易执行异常 (消息ID: {message.id}): {e}")
                    signal_dict['trade_result'] = {'success': False, 'error': str(e)}
                    signal_dict['trade_executed'] = False
                    await save_signal_to_file(signal_dict)
            else:
                print(f"\n❌ 未检测到有效交易信号 (消息ID: {message.id})。")

        except Exception as e:
            print(f"❌ 异步处理消息时出错 (消息ID: {message.id}): {e}")
            import traceback
            traceback.print_exc()

    # 重置退避计时器，因为连接成功了
    backoff.reset()
    
    # 每60秒发送一个保活ping和状态检查
    async def keep_alive():
        ping_count = 0
        while True:
            try:
                await asyncio.sleep(30)  # 30秒
                # 使用 GetStateRequest 作为更可靠的 ping
                await client(GetStateRequest())
                ping_count += 1
                if ping_count % 2 == 0:  # 每60秒显示一次状态
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 监听状态正常，等待消息...")
            except Exception as e:
                print(f"保活ping失败: {e}")
                # 不中断循环，继续尝试

    # 启动保活任务
    keep_alive_task = asyncio.create_task(keep_alive())
    
    try:
        # 等待直到断开连接
        await client.run_until_disconnected()
    except Exception as e:
        print(f"运行时发生错误: {e}")
    finally:
        # 取消保活任务
        keep_alive_task.cancel()
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass

async def main():
    """主函数，连接到Telegram并开始监听消息"""
    print("🚀 正在启动高性能Telegram监听程序...")

    # 应用系统级优化
    if PERFORMANCE_MODULE_AVAILABLE:
        apply_system_optimizations()
        print_optimization_report()

    # 创建性能监控器
    performance_monitor = PerformanceOptimizer() if PERFORMANCE_MODULE_AVAILABLE else None

    backoff = ExponentialBackoff()
    max_retries = 20
    retry_count = 0
    
    while retry_count < max_retries:
        client = None
        try:
            # 创建新的客户端
            client = await create_telegram_client()
            
            # 连接到Telegram
            await client.start(PHONE_NUMBER)
            print("成功连接到Telegram！")
            print(f"开始监听频道IDs: {TARGET_CHANNEL_IDS}")
            print(f"开始监听话题配置: {TARGET_TOPICS}")

            # 获取用户信息进行验证
            me = await client.get_me()
            print(f"当前登录用户: {me.first_name} (@{me.username})")

            # 验证所有频道信息
            print("\n=== 验证频道访问权限 ===")
            for channel_id in TARGET_CHANNEL_IDS:
                try:
                    entity = await client.get_entity(channel_id)
                    print(f"✅ 频道 (ID: {channel_id}): {entity.title}")
                except Exception as e:
                    print(f"❌ 无法访问频道 (ID: {channel_id}): {e}")

            # 验证所有超级群组信息
            print("\n=== 验证超级群组访问权限 ===")
            for group_id, topic_ids in TARGET_TOPICS.items():
                try:
                    entity = await client.get_entity(group_id)
                    print(f"✅ 超级群组 (ID: {group_id}): {entity.title}")
                    print(f"   监听话题IDs: {topic_ids}")
                except Exception as e:
                    print(f"❌ 无法访问超级群组 (ID: {group_id}): {e}")
            
            # 处理消息
            await handle_messages(client, backoff)
            
        except errors.FloodWaitError as e:
            print(f"⚠️ 触发Telegram限流，需要等待 {e.seconds} 秒")
            # 遇到限流时，等待指定的时间
            await asyncio.sleep(e.seconds + 5)  # 多等5秒以确保安全
        except errors.NetworkError as e:
            delay = backoff.delay()
            retry_count += 1
            print(f"⚠️ 网络错误: {e}. 重试 ({retry_count}/{max_retries}) 将在 {delay:.1f} 秒后进行...")
            await asyncio.sleep(delay)
        except errors.ServerError as e:
            delay = backoff.delay()
            retry_count += 1
            print(f"⚠️ 服务器错误: {e}. 重试 ({retry_count}/{max_retries}) 将在 {delay:.1f} 秒后进行...")
            await asyncio.sleep(delay)
        except errors.SessionPasswordNeededError:
            print("⚠️ 需要会话密码，请考虑重新认证")
            break
        except errors.PhoneNumberBannedError:
            print("❌ 电话号码已被封禁")
            break
        except Exception as e:
            delay = backoff.delay()
            retry_count += 1
            print(f"⚠️ 未知错误: {e}. 重试 ({retry_count}/{max_retries}) 将在 {delay:.1f} 秒后进行...")
            await asyncio.sleep(delay)
        finally:
            # 安全关闭客户端
            if client and client.is_connected():
                await client.disconnect()
                print("客户端已断开连接")
    
    if retry_count >= max_retries:
        print("达到最大重试次数，程序退出")

if __name__ == '__main__':
    # 设置日志记录
    import logging
    logging.basicConfig(
        format='[%(levelname)s %(asctime)s] %(name)s: %(message)s',
        level=logging.WARNING,
        handlers=[
            logging.FileHandler(OTHER_CONFIG['LOG_FILE']),
            logging.StreamHandler()
        ]
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断") 