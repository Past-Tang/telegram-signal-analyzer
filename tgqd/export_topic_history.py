import asyncio
from telethon import TelegramClient

# 请替换成你自己的 API ID, API Hash 和电话号码
API_ID = 28326625  # 替换成你的 API ID
API_HASH = 'e91673e90489834a4b26a82bc8fdb8dd'  # 替换成你的 API Hash
PHONE_NUMBER = '+447543202310'  # 替换成你的电话号码

# 会话文件名
SESSION_FILE = 'telegram_session.session'

async def export_topic_history(client, channel_id, topic_id, output_file):
    """
    导出指定频道中特定话题的所有历史消息。
    """
    print(f"\n正在从频道 ID {channel_id} 中导出话题 ID {topic_id} 的历史记录...")
    try:
        # 获取频道实体
        entity = await client.get_entity(channel_id)

        # 首先获取话题的起始消息，以确保我们有一个有效的消息对象
        topic_message = await client.get_messages(entity, ids=topic_id)
        if not topic_message:
            print(f"错误: 无法找到话题的起始消息 (ID: {topic_id})。请确认该话题仍然存在且您有权访问。")
            return
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"--- Chat History for Channel ID: {channel_id}, Topic ID: {topic_id} ---\n\n")
            print("正在获取消息，这可能需要一些时间...")
            message_count = 0
            # 使用获取到的消息对象的 ID 来迭代话题内的消息
            # 这可以避免将整个消息对象传递给底层函数而导致的类型错误
            async for message in client.iter_messages(entity, reply_to=topic_message.id, limit=None):
                
                # 消息发送者信息
                sender = await message.get_sender()
                sender_id = "N/A"
                sender_name = "未知或频道自身"
                if sender:
                    sender_id = sender.id
                    if hasattr(sender, 'username') and sender.username:
                        sender_name = f"@{sender.username}"
                    elif hasattr(sender, 'first_name') and sender.first_name:
                        sender_name = sender.first_name
                        if hasattr(sender, 'last_name') and sender.last_name:
                            sender_name += f" {sender.last_name}"
                    else:
                        sender_name = f"User(ID:{sender.id})"
                
                # 回复信息
                is_reply = message.is_reply
                reply_to_id = message.reply_to.reply_to_msg_id if is_reply else "N/A"
                
                # 媒体信息
                has_media = message.media is not None
                
                # 消息文本
                text = message.text or ""

                # 构建日志条目
                log_entry = (
                    f"--- Message ---\n"
                    f"Message ID: {message.id}\n"
                    f"Timestamp: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Sender ID: {sender_id}\n"
                    f"Sender Name: {sender_name}\n"
                    f"Is Reply: {is_reply}\n"
                    f"Reply to Msg ID: {reply_to_id}\n"
                    f"Has Media: {has_media}\n"
                    f"Content:\n{text}\n\n"
                )
                
                f.write(log_entry)
                message_count += 1
                if message_count % 100 == 0:
                    print(f"已处理 {message_count} 条消息...")

        print(f"\n成功导出 {message_count} 条消息到 {output_file}")
    except ValueError:
        print(f"错误: 无法找到ID为 '{channel_id}' 的实体。请检查ID是否正确，以及您是否是该聊天的一部分。")
    except Exception as e:
        print(f"在导出频道 {channel_id} 的话题 {topic_id} 历史时发生错误: {e}")

async def main():
    """
    主函数，用于连接 Telegram 并执行导出操作。
    """
    # --- 配置 ---
    # 要导出的频道和话题
    CHANNEL_ID = -1002025152200  # K線蹦迪群
    TOPIC_ID = 18125          # K线蹦迪山寨交易策略
    # --- 结束配置 ---

    output_filename = f'channel_{CHANNEL_ID}_topic_{TOPIC_ID}_history.txt'

    # 连接到 Telegram
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH, 
                       connection_retries=10,
                       retry_delay=5)
    
    await client.start(PHONE_NUMBER)
    print("成功连接到 Telegram。")
    
    # 导出指定话题的历史记录
    await export_topic_history(client, CHANNEL_ID, TOPIC_ID, output_filename)
    
    print("\n所有操作完成。")
    #断开连接
    await client.disconnect()

if __name__ == '__main__':
    # 运行主异步函数
    asyncio.run(main()) 