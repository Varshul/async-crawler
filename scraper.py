import re
import asyncio
import async_timeout
from timeit import default_timer as timer

import aiohttp
from lxml import html

DOMAIN = 'https://en.wikipedia.org'
REGEX = re.compile(r"^(\/wiki\/[^:#\s]+)(?:$|#)")
Q = asyncio.Queue()
MAX_DEPTH = 1
MAX_RETRIES = 5
MAX_WORKERS = 20

count = 0
cache = set()

async def get(session, url, timeout=10):
    with async_timeout.timeout(timeout):
        async with session.get(url) as response:
            return await response.text()


def extract_urls(html_code):
    tree = html.fromstring(html_code)
    urls_list = map(REGEX.findall, tree.xpath('//a/@href'))
    return {DOMAIN + x[0] for x in urls_list if x != []}


async def worker(loop):
    global count
    async with aiohttp.ClientSession(loop=loop) as session:
        while True:
            depth, url, retries = await Q.get()
            if url == None:
                break
            if url in cache:
                continue

            try:
                html_code = await get(session, url)
            except asyncio.TimeoutError:
                if retries + 1 <= MAX_RETRIES:
                    # print('Timeout on {} retrying...'.format(url))
                    Q.put_nowait((depth, url, retries + 1))
                    continue

            # print('Request sent for {}'.format(url))
            urls = extract_urls(html_code)
            count += 1
            cache.add(url)
            # print('Done : {}'.format(url))

            if depth + 1 <= MAX_DEPTH:
                for url in urls:
                    Q.put_nowait((depth + 1, url, retries))
            elif depth + 1 > MAX_DEPTH and Q.qsize() == 1:
                for _ in range(MAX_WORKERS):
                    Q.put_nowait((None, None, None))


def main():
    Q.put_nowait((0, DOMAIN + '/wiki/Python_(programming_language)', 0))
    loop = asyncio.get_event_loop()
    workers = [worker(loop) for x in range(MAX_WORKERS)]
    loop.run_until_complete(asyncio.wait(workers))
    loop.close()


if __name__ == '__main__':
    start = timer()
    main()
    end = timer()
    print('Time Taken for {} requests : {} sec'.format(count, end - start))
