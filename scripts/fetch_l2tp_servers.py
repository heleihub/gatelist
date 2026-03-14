import aiohttp
import asyncio
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote

# VPN Gate 主页（服务器列表页）
MAIN_URL = "https://www.vpngate.net/en/"

async def fetch_html(session, url, headers=None):
    """获取 HTML 内容"""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    async with session.get(url, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP {resp.status}")
        return await resp.text()

async def fetch_protocols(session, hostname, semaphore):
    """获取单个服务器的协议支持列表"""
    url = f"https://www.vpngate.net/en/entry.aspx?hostname={quote(hostname)}"
    async with semaphore:
        try:
            html = await fetch_html(session, url)
            soup = BeautifulSoup(html, 'html.parser')
            protocols_section = soup.find('h3', string=lambda t: t and 'Supported VPN Protocols' in t)
            if protocols_section:
                next_elem = protocols_section.find_next()
                text_content = next_elem.get_text() if next_elem else ""
                l2tp_support = 'L2TP/IPsec' in text_content
            else:
                l2tp_support = False
            return {"l2tp": l2tp_support}
        except Exception as e:
            return {"l2tp": False, "error": str(e)}

async def main():
    start_time = time.time()
    print("正在从 VPN Gate 主页获取服务器列表...")
    async with aiohttp.ClientSession() as session:
        html = await fetch_html(session, MAIN_URL)
        soup = BeautifulSoup(html, 'html.parser')

        # 找到服务器表格 (id="vg_table")
        table = soup.find('table', {'id': 'vg_table'})
        if not table:
            print("未找到服务器表格，可能页面结构已变")
            return

        rows = table.find('tbody').find_all('tr')
        servers = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 8:  # 至少需要前几个字段
                continue

            # 提取数据（根据实际表格结构调整）
            # 通常顺序：HostName, IP, Score, Ping, Speed, Country, ...
            hostname = cols[0].get_text(strip=True)
            ip = cols[1].get_text(strip=True)
            score = cols[2].get_text(strip=True)
            ping = cols[3].get_text(strip=True)
            speed = cols[4].get_text(strip=True)
            country = cols[5].get_text(strip=True)

            # 清理数字字段（可能包含逗号或单位）
            def clean_num(s):
                s = s.replace(',', '').replace('Mbps', '').replace('ms', '').strip()
                try:
                    return int(s) if s.isdigit() else 0
                except:
                    return 0

            servers.append({
                "hostname": hostname,
                "ip": ip,
                "country": country,
                "ping": clean_num(ping),
                "speed": clean_num(speed),
                "score": clean_num(score),
            })

        print(f"从主页解析到 {len(servers)} 个服务器")

    if not servers:
        print("没有获取到任何服务器，终止运行")
        return

    print(f"开始并发爬取 {len(servers)} 个服务器的详情页...")
    semaphore = asyncio.Semaphore(5)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for s in servers:
            tasks.append(fetch_protocols(session, s["hostname"], semaphore))
        results = await asyncio.gather(*tasks)

    for i, proto in enumerate(results):
        servers[i]["l2tp"] = proto["l2tp"]

    l2tp_servers = [s for s in servers if s.get("l2tp")]
    l2tp_servers.sort(key=lambda x: x["country"])

    print(f"支持 L2TP 的服务器: {len(l2tp_servers)} 个")

    # 写入 JSON
    with open("l2tp-servers.json", "w", encoding="utf-8") as f:
        json.dump(l2tp_servers, f, ensure_ascii=False, indent=2)

    # 生成 Markdown
    with open("l2tp-servers.md", "w", encoding="utf-8") as f:
        f.write("# 🌍 L2TP/IPsec Servers (实时更新)\n\n")
        f.write("更新时间: {}\n\n".format(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())))
        f.write("| HostName | IP | 国家 | Ping (ms) | 速度 (bps) | 评分 |\n")
        f.write("|----------|----|------|-----------|------------|------|\n")
        for s in l2tp_servers:
            f.write(f"| {s['hostname']} | {s['ip']} | {s['country']} | {s['ping']} | {s['speed']} | {s['score']} |\n")

    elapsed = time.time() - start_time
    print(f"完成！耗时 {elapsed:.1f} 秒")

if __name__ == "__main__":
    asyncio.run(main())
