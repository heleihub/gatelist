import aiohttp
import asyncio
import csv
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote

# 官方 CSV API
CSV_URL = "https://www.vpngate.net/api/export/"

async def fetch_protocols(session, hostname, semaphore):
    """获取单个服务器的协议支持列表"""
    url = f"https://www.vpngate.net/en/entry.aspx?hostname={quote(hostname)}"
    async with semaphore:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return {"l2tp": False, "error": f"HTTP {resp.status}"}
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                # 查找协议部分，通常在一个包含 "Supported VPN Protocols" 的表格中
                protocols_section = soup.find('h3', string=lambda t: t and 'Supported VPN Protocols' in t)
                if protocols_section:
                    # 协议列表通常在其后的 <ul> 或 <p> 中
                    next_elem = protocols_section.find_next()
                    text = next_elem.get_text() if next_elem else ""
                    l2tp_support = 'L2TP/IPsec' in text
                else:
                    l2tp_support = False
                return {"l2tp": l2tp_support}
        except Exception as e:
            return {"l2tp": False, "error": str(e)}

async def main():
    start_time = time.time()
    print("正在从官方 API 获取基础列表...")
    async with aiohttp.ClientSession() as session:
        async with session.get(CSV_URL) as resp:
            text = await resp.text()
            lines = text.strip().split('\n')[2:]  # 跳过前两行
            reader = csv.reader(lines)
            servers = []
            for row in reader:
                if len(row) < 15:
                    continue
                hostname = row[0].strip('"')
                ip = row[1].strip('"')
                country = row[5].strip('"')
                ping = row[3].strip('"')
                speed = row[4].strip('"')
                score = row[2].strip('"')
                servers.append({
                    "hostname": hostname,
                    "ip": ip,
                    "country": country,
                    "ping": int(ping) if ping.isdigit() else 999,
                    "speed": int(speed) if speed.isdigit() else 0,
                    "score": int(score) if score.isdigit() else 0,
                })

    print(f"共获取 {len(servers)} 个服务器，开始并发爬取详情页...")
    semaphore = asyncio.Semaphore(10)  # 控制并发数
    async with aiohttp.ClientSession() as session:
        tasks = []
        for s in servers:
            tasks.append(fetch_protocols(session, s["hostname"], semaphore))
        results = await asyncio.gather(*tasks)

    for i, proto in enumerate(results):
        servers[i]["l2tp"] = proto["l2tp"]

    # 筛选支持 L2TP 的服务器
    l2tp_servers = [s for s in servers if s["l2tp"]]
    l2tp_servers.sort(key=lambda x: x["country"])

    print(f"支持 L2TP 的服务器: {len(l2tp_servers)} 个")

    # 写入 JSON 文件
    with open("l2tp-servers.json", "w", encoding="utf-8") as f:
        json.dump(l2tp_servers, f, ensure_ascii=False, indent=2)

    # 生成 Markdown 表格
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
