import asyncio
import aioimaplib

async def test():
    client = aioimaplib.IMAP4_SSL('imap.qq.com', 993)
    await client.wait_hello_from_server()
    await client.login('3010089043@qq.com', 'hxxhnhhnydbkdhcg')
    await client.select('INBOX')
    status, data = await client.fetch('1', '(RFC822)')
    print(f"status: {status}")
    print(f"data: {data}")
    await client.logout()

asyncio.run(test())