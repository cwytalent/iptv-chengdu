#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re
import sys

# ---------- 新增：Selenium 动态解析支持（仅当静态页面无表格时启用）----------
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    # 不立即报错，仅在需要时提示

def fetch_page_with_selenium(url, timeout=30):
    """使用 Selenium 获取动态渲染后的完整页面 HTML"""
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium 未安装，无法获取动态页面。请执行: pip install selenium webdriver-manager")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")               # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    try:
        # 自动下载/使用 chromedriver（GitHub Actions 中也可手动指定路径）
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        html = driver.page_source
        driver.quit()
        return html
    except Exception as e:
        raise RuntimeError(f"Selenium 获取页面失败: {e}")

# ---------- 以下为原有配置与函数，完全不变 ----------
sourceIcon51ZMT = "https://epg.51zmt.top:8001"
sourceChengduMulticast = "https://epg.51zmt.top:8001/multicast/"
homeLanAddress = "http://192.168.10.2:4022"
catchupBaseUrl = "http://192.168.10.2:4022"
totalEPG = "https://epg.51zmt.top:8001/e.xml,https://epg.112114.xyz/pp.xml"

groupCCTV = ["CCTV", "CETV", "CGTN"]
groupWS = ["卫视"]
groupSC = ["SCTV", "四川", "CDTV", "熊猫", "峨眉", "成都"]
group4K = ["4K"]
listUnused = ["单音轨", "画中画", "热门", "直播室", "爱", "92"]

index = 1
def getID():
    global index
    index = index + 1
    return index - 1

def setID(i):
    global index
    if i > index:
        index = i + 1
    return index

def isIn(items, v):
    for item in items:
        if item in v:
            return True
    return False

def filterCategory(v):
    categories = []
    if isIn(groupCCTV, v):
        categories.append("CCTV")
    if isIn(groupWS, v):
        categories.append("卫视")
    if isIn(group4K, v):
        categories.append("4K")
    if isIn(groupSC, v):
        categories.append("四川")
    if not categories:
        categories.append("其他")
    return categories

def findIcon(m, id):
    for v in m:
        if v["name"] == id:
            return urljoin(sourceIcon51ZMT, v["icon"])
    return ""

def buildCatchupSource(rtsp_url, original_url):
    if not rtsp_url or not rtsp_url.startswith("rtsp://"):
        return ""
    url_without_protocol = rtsp_url[7:]
    path_start = url_without_protocol.find("/")
    if path_start == -1:
        return ""
    rtsp_host = url_without_protocol[:path_start]
    rtsp_path = url_without_protocol[path_start:]
    catchup_source = f"{catchupBaseUrl}/rtsp/{rtsp_host}{rtsp_path}?playseek=${{(b)yyyyMMddHHmmss}}-${{(e)yyyyMMddHHmmss}}"
    return catchup_source

def loadIcon():
    try:
        print(f"正在获取图标数据: {sourceIcon51ZMT}")
        response = requests.get(sourceIcon51ZMT, verify=False, timeout=30)
        response.raise_for_status()
        if not response.content:
            print("⚠️  图标数据为空，将使用默认图标")
            return []
        res = response.content
        soup = BeautifulSoup(res, 'lxml')
        m = []
        for tr in soup.find_all('tr'):
            td = tr.find_all('td')
            if len(td) < 4:
                continue
            href = ""
            for a in td[0].find_all('a', href=True):
                if a["href"] == "#":
                    continue
                href = a["href"]
            if href != "":
                m.append({"id": td[3].string, "name": td[2].string, "icon": href})
        print(f"成功加载 {len(m)} 个图标")
        return m
    except Exception as e:
        print(f"⚠️  图标数据获取失败: {e}，将继续使用默认图标")
        return []

def generateM3U8(file):
    try:
        print(f"正在生成M3U8文件: {file}")
        with open(file, "w", encoding='utf-8') as f:
            name = '成都电信IPTV - ' + datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            title = f'#EXTM3U name="{name}" url-tvg="{totalEPG}"\n\n'
            f.write(title)
            total_written = 0
            for k, v in m.items():
                for c in v:
                    if "dup" in c:
                        continue
                    catchup_source = buildCatchupSource(c["rtsp_url"], c["address"])
                    line = (f'#EXTINF:-1 tvg-logo="{c["icon"]}" tvg-id="{c["id"]}" '
                           f'tvg-name="{c["name"]}" group-title="{k}" '
                           f'catchup="default" catchup-source="{catchup_source}",{c["name"]}\n')
                    line2 = f'{homeLanAddress}/rtp/{c["address"]}?FCC=182.139.234.40:8027\n'
                    f.write(line)
                    f.write(line2)
                    total_written += 1
        print(f"✅ M3U8文件生成成功，共写入 {total_written} 个频道")
    except Exception as e:
        print(f"❌ 生成M3U8文件失败: {e}")
        sys.exit(1)

def generateHome():
    generateM3U8("./home/iptv.m3u8")

def main():
    # 加载图标数据
    mIcons = loadIcon()

    # ---------- 修改点：智能获取成都组播数据（静态 + 动态降级）----------
    page_html = None
    use_selenium = False
    soup = None

    # 第一步：尝试静态请求
    try:
        print(f"正在获取成都组播数据（静态请求）: {sourceChengduMulticast}")
        response = requests.get(sourceChengduMulticast, verify=False, timeout=30)
        response.raise_for_status()
        page_html = response.content
    except Exception as e:
        print(f"⚠️  静态请求失败: {e}，将尝试动态渲染")
        use_selenium = True

    # 第二步：若静态请求成功，检查是否包含表格
    if page_html and not use_selenium:
        soup = BeautifulSoup(page_html, 'lxml')
        tables = soup.find_all('table')
        if tables:
            print("✅ 静态页面包含表格，直接使用静态数据")
        else:
            print("⚠️  静态页面无表格，尝试动态渲染...")
            use_selenium = True

    # 第三步：需要动态渲染
    if use_selenium:
        if not SELENIUM_AVAILABLE:
            print("❌ 必须使用 Selenium 但未安装。请在环境中安装: pip install selenium webdriver-manager")
            print("ERROR: Selenium required but not installed")
            sys.exit(1)
        try:
            print(f"正在使用 Selenium 获取动态页面: {sourceChengduMulticast}")
            dynamic_html = fetch_page_with_selenium(sourceChengduMulticast)
            soup = BeautifulSoup(dynamic_html, 'lxml')
            # 再次验证表格是否存在
            if not soup.find_all('table'):
                print("❌ 动态页面仍然没有表格，数据源可能已彻底变更")
                print("ERROR: No table found even after dynamic rendering")
                sys.exit(1)
            print("✅ 动态渲染成功，开始解析表格")
        except Exception as e:
            print(f"❌ 动态渲染失败: {e}")
            print("ERROR: Failed to fetch dynamic content")
            sys.exit(1)

    # ---------- 以下为原有表格解析逻辑，完全不变 ----------
    # 验证有效数据行数
    valid_rows = 0
    for tr in soup.find_all('tr'):
        td = tr.find_all('td')
        if len(td) >= 7 and td[0].string != "序号":
            valid_rows += 1
    if valid_rows == 0:
        print("❌ 未找到有效的频道数据")
        sys.exit(1)
    print(f"成功获取到 {valid_rows} 条频道数据")

    global m
    m = {}

    for tr in soup.find_all(name='tr'):
        td = tr.find_all(name='td')
        if len(td) < 7 or td[0].string == "序号":
            continue

        name = td[1].string
        if isIn(listUnused, name):
            continue

        setID(int(td[0].string))

        name = name.replace('超高清', '').replace('高清', '').replace('-', '').strip()
        groups = filterCategory(name)
        icon = findIcon(mIcons, name)
        rtsp_url = td[6].string if td[6].string else ""

        channel_info = {
            "id": td[0].string,
            "name": name,
            "address": td[2].string,
            "rtsp_url": rtsp_url,
            "ct": True,
            "icon": icon
        }

        for group in groups:
            if group not in m:
                m[group] = []
            m[group].append(channel_info)

    total_channels = sum(len(channels) for channels in m.values())
    if total_channels == 0:
        print("❌ 未获取到任何频道数据，无法生成M3U8文件")
        sys.exit(1)

    print(f"✅ 数据处理完成，共获取到 {total_channels} 个频道，分布在 {len(m)} 个分组中")
    for group, channels in m.items():
        print(f"   - {group}: {len(channels)} 个频道")

    generateHome()

if __name__ == "__main__":
    try:
        main()
        print("✅ 脚本执行成功完成")
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ 脚本执行过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
