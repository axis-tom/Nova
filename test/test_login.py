import asyncio
import aioimaplib

async def test():
    client = aioimaplib.IMAP4_SSL('imap.qq.com', 993)
    await client.wait_hello_from_server()
    res = await client.login('3010089043@qq.com', 'jlrwgzpcmijqdfja')
    print(res)

asyncio.run(test())