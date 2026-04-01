import asyncio
import aioimaplib
import email

async def test():
    client = aioimaplib.IMAP4_SSL('imap.qq.com', 993)
    await client.wait_hello_from_server()
    await client.login('3010089043@qq.com', 'jlrwgzpcmijqdfja')
    await client.select('INBOX')
    status, data = await client.search('SINCE 30-Mar-2026')
    if status != 'OK':
        print("Search failed")
        return
    msg_ids = data[0].split()
    for msg_id in msg_ids[:5]:
        msg_id_str = msg_id.decode()
        status, msg_data = await client.fetch(msg_id_str, '(RFC822)')
        if status != 'OK':
            print(f"Fetch failed for {msg_id_str}: {status} {msg_data}")
            continue
        if len(msg_data) >= 2:
            raw_email = msg_data[1]
            msg = email.message_from_bytes(raw_email)
            print(f"Subject: {msg.get('Subject')}")
        else:
            print(f"Unexpected msg_data: {msg_data}")
    await client.logout()

asyncio.run(test())