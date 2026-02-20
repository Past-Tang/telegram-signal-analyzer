import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.functions.channels import GetFullChannelRequest
import datetime

# 请替换成你自己的 API ID, API Hash 和电话号码
API_ID = 28326625  # 替换成你的 API ID
API_HASH = 'e91673e90489834a4b26a82bc8fdb8dd'  # 替换成你的 API Hash
PHONE_NUMBER = '+447543202310'  # 替换成你的电话号码

# 会话文件名
SESSION_FILE = 'telegram_session.session'

async def main():
    """
    主函数，用于连接 Telegram，并打印所有加入的群组和频道及其话题。
    """
    # 连接到 Telegram
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH, 
                       connection_retries=10,
                       retry_delay=5)
    
    await client.start(PHONE_NUMBER)

    print("成功连接到 Telegram。")

    print("\n正在获取您加入的群组和频道列表...")
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            print(f"- {dialog.name} (ID: {dialog.id})")
            
            # 获取频道/群组的详细信息
            if dialog.is_channel:
                try:
                    # 获取频道的完整信息
                    full_channel = await client(GetFullChannelRequest(dialog.entity))
                    
                    # 打印频道详细信息
                    print(f"  类型: {'超级群组' if dialog.entity.megagroup else '广播频道'}")
                    
                    if dialog.entity.username:
                        print(f"  用户名: @{dialog.entity.username}")
                        print(f"  链接: https://t.me/{dialog.entity.username}")
                    
                    if hasattr(full_channel.chats[0], 'about') and full_channel.chats[0].about:
                        print(f"  描述: {full_channel.chats[0].about}")
                    
                    if hasattr(full_channel.full_chat, 'participants_count'):
                        print(f"  成员数: {full_channel.full_chat.participants_count}")
                    
                    # 打印创建时间（如果可用）
                    if hasattr(dialog.entity, 'date'):
                        date_str = dialog.entity.date.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  创建时间: {date_str}")
                    
                    # 打印是否是公开频道
                    print(f"  是否公开: {'是' if dialog.entity.username else '否'}")
                    
                    # 打印未读消息数
                    if dialog.unread_count > 0:
                        print(f"  未读消息: {dialog.unread_count}")
                    
                    # 检查这是否是一个开启了话题功能的频道 (论坛)
                    if hasattr(dialog.entity, 'forum') and dialog.entity.forum:
                        try:
                            # 获取该频道下的所有话题
                            topics_result = await client(GetForumTopicsRequest(
                                channel=dialog.entity,
                                offset_date=0,
                                offset_id=0,
                                offset_topic=0,
                                limit=100  # Assume a channel won't have more than 100 topics
                            ))
                            if topics_result.topics:
                                print("  话题列表:")
                                for topic in topics_result.topics:
                                    print(f"    - {topic.title} (Topic ID: {topic.id})")
                        except Exception as e:
                            print(f"    - 获取话题信息时出错: {e}")
                except Exception as e:
                    print(f"  获取频道详细信息时出错: {e}")
            elif dialog.is_group:
                # 群组信息显示
                try:
                    print(f"  类型: 普通群组")
                    if hasattr(dialog.entity, 'participants_count'):
                        print(f"  成员数: {dialog.entity.participants_count}")
                    if dialog.unread_count > 0:
                        print(f"  未读消息: {dialog.unread_count}")
                except Exception as e:
                    print(f"  获取群组详细信息时出错: {e}")

    print("\n所有操作完成。")

    #断开连接
    await client.disconnect()

if __name__ == '__main__':
    # 运行主异步函数
    asyncio.run(main()) 