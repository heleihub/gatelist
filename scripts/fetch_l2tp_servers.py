import aiohttp
import asyncio
import csv
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote

# 官方 CSV API
CSV_URL = "https://www.vpngate.net/api/export/"

async def fetch_text(session, url, encodings=('utf-8', 'shift_jis', 'iso-8859-1')):
    """尝试用多种编码获取响应文本"""
    async with session.get(url) as resp:
        raw = await resp.read()
        for enc in encodings:
            try:
                text = raw.decode(enc)
                return text, enc
            except UnicodeDecodeError:
                continue
        # 如果所有编码都失败，强制用 UTF-8 忽略错误
        return raw.decode('utf-8', errors='ignore'), 'utf-8(ignore)'

async def fetch_protocols(session, hostname, semaphore):
    """获取单个服务器的协议支持列表"""
    url = f"https://www.vpngate.net/en/entry.aspx?hostname={quote(hostname)}"
    async with semaphore:
        try:
            text, enc = await fetch_text(session, url)
            soup = BeautifulSoup(text, 'html.parser')
            # 查找协议部分，通常在一个包含 "Supported VPN Protocols" 的表格中
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
    print("正在从官方 API 获取基础列表...")
    async with aiohttp.ClientSession() as session:
        # 获取 CSV 数据
        csv_text, csv_enc = await fetch_text(session, CSV_URL)
        print(f"CSV 解码编码: {csv_enc}")

        # 跳过前两行注释和标题
        lines = csv_text.strip().split('\n')
        if len(lines) < 3:
            print("数据行数不足，可能 API 返回了错误内容")
            return

        # 使用 csv.reader 解析
        reader = csv.reader(lines[2:])  # 从第三行开始
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
    semaphore = asyncio.Semaphore(5)  # 降低并发数更安全
    async with aiohttp.ClientSession() as session:
        tasks = []
        for s in servers:
            tasks.append(fetch_protocols(session, s["hostname"], semaphore))
        results = await asyncio.gather(*tasks)

    for i, proto in enumerate(results):
        servers[i]["l2tp"] = proto["l2tp"]

    # 筛选支持 L2TP 的服务器
    l2tp_servers = [s for s in servers if s.get("l2tp")]
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
