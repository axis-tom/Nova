
import asyncio
from backend.connectors.email.imap_client import IMAPClient

async def test():
    client = IMAPClient(
        host="imap.qq.com",
        port=993,
        username="3010089043@qq.com",
        password="jlrwgzpcmijqdfja",
        use_ssl=True
    )
    await client.connect()
    print("连接成功")
    emails = await client.fetch_unread(limit=5)
    print(f"获取到 {len(emails)} 封邮件")
    for email in emails:
        print(f"主题: {email['subject']} | 发件人: {email['from']}")
    await client.disconnect()
    print("测试完成")

asyncio.run(test())