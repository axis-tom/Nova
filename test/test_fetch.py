
import email
import asyncio
import aioimaplib
import asyncio
import aioimaplib
from datetime import datetime, timedelta

async def test_since():
    client = aioimaplib.IMAP4_SSL('imap.qq.com', 993)
    await client.wait_hello_from_server()
    await client.login('3010089043@qq.com', 'jlrwgzpcmijqdfja')
    await client.select('INBOX')
    
    # 计算 SINCE 日期
    since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    print(f"Searching with SINCE {since_date}")
    status, data = await client.search(f'(SINCE {since_date})')
    print(f"Status: {status}, data: {data}")
    if status == 'OK':
        msg_ids = data[0].split()
        print(f"Emails since {since_date}: {len(msg_ids)}")
    else:
        print("Search failed")
    
    # 尝试不带 SINCE 搜索所有邮件
    status, data = await client.search('ALL')
    msg_ids = data[0].split()
    print(f"Total emails in INBOX: {len(msg_ids)}")
    if msg_ids:
        # 获取最新邮件的日期
        latest_id = msg_ids[-1]
        status, msg_data = await client.fetch(str(latest_id), '(RFC822)')
        if status == 'OK':
            msg = email.message_from_bytes(msg_data[1])
            print(f"Latest email date: {msg.get('Date')}")

    await client.logout()

asyncio.run(test_since())