import aiohttp
import asyncio
import json
import time
import csv
from io import StringIO

# VPN Gate API（返回 CSV 格式的服务器列表）
API_URL = "http://www.vpngate.net/api/iphone/"

async def fetch_csv(session):
    """获取 API 返回的 CSV 内容"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    async with session.get(API_URL, headers=headers) as resp:
        if resp.status != 200:
            raise Exception(f"HTTP {resp.status}")
        return await resp.text()

def parse_csv(text):
    """解析 CSV，提取服务器信息"""
    lines = [line for line in text.splitlines() if line and not line.startswith('#')]
    if not lines:
        return []

    reader = csv.reader(lines)
    servers = []
    for row in reader:
        # 根据 API 返回的字段顺序：
        # 0:HostName, 1:IP, 2:Score, 3:Ping, 4:Speed, 5:CountryLong, ...
        if len(row) < 6:
            continue

        def clean_num(s):
            s = s.replace(',', '').strip()
            try:
                return int(s) if s else 0
            except:
                return 0

        servers.append({
            "hostname": row[0].strip(),
            "ip": row[1].strip(),
            "score": clean_num(row[2]),
            "ping": clean_num(row[3]),
            "speed": clean_num(row[4]),
            "country": row[5].strip(),
            "l2tp": True,          # VPN Gate 所有公共服务器都支持 L2TP/IPsec
        })
    return servers

async def main():
    start_time = time.time()
    print("正在从 VPN Gate API 获取服务器列表...")
    async with aiohttp.ClientSession() as session:
        csv_text = await fetch_csv(session)
        servers = parse_csv(csv_text)

    print(f"从 API 解析到 {len(servers)} 个服务器")

    if not servers:
        print("没有获取到任何服务器，终止运行")
        return

    # 按国家排序（与现有逻辑保持一致）
    servers.sort(key=lambda x: x["country"])

    # 写入 JSON
    with open("l2tp-servers.json", "w", encoding="utf-8") as f:
        json.dump(servers, f, ensure_ascii=False, indent=2)

    # 生成 Markdown
    with open("l2tp-servers.md", "w", encoding="utf-8") as f:
        f.write("# 🌍 L2TP/IPsec Servers (实时更新)\n\n")
        f.write("更新时间: {}\n\n".format(time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())))
        f.write("| HostName | IP | 国家 | Ping (ms) | 速度 (bps) | 评分 |\n")
        f.write("|----------|----|------|-----------|------------|------|\n")
        for s in servers:
            f.write(f"| {s['hostname']} | {s['ip']} | {s['country']} | {s['ping']} | {s['speed']} | {s['score']} |\n")

    elapsed = time.time() - start_time
    print(f"完成！耗时 {elapsed:.1f} 秒，共 {len(servers)} 台服务器")

if __name__ == "__main__":
    asyncio.run(main())
