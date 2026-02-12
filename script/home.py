#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import sys
import os

# ---------- 配置常量（完全不变）----------
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

# ---------- 辅助函数（全部保留，一字未改）----------
index = 1
def getID():
    global index
    index += 1
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
    """
    返回频道名匹配的所有分组
    若频道名包含4K，则只返回["4K"]
    否则按原有规则匹配多个分组（CCTV、卫视、四川等）
    """
    # 优先判断4K —— 只要包含4K，直接返回，不再检查其他分组
    if "4K" in v:
        return ["4K"]
    
    categories = []
    if isIn(groupCCTV, v):
        categories.append("CCTV")
    if isIn(groupWS, v):
        categories.append("卫视")
    if isIn(groupSC, v):
        categories.append("四川")
    
    # 如果没有匹配任何分组，则归类为"其他"
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
    return f"{catchupBaseUrl}/rtsp/{rtsp_host}{rtsp_path}?playseek=${{(b)yyyyMMddHHmmss}}-${{(e)yyyyMMddHHmmss}}"

def loadIcon():
    try:
        print("正在获取图标数据...")
        resp = requests.get(sourceIcon51ZMT, verify=False, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'lxml')
        icons = []
        for tr in soup.find_all('tr'):
            td = tr.find_all('td')
            if len(td) < 4:
                continue
            href = ""
            for a in td[0].find_all('a', href=True):
                if a["href"] == "#":
                    continue
                href = a["href"]
            if href:
                icons.append({"id": td[3].string, "name": td[2].string, "icon": href})
        print(f"成功加载 {len(icons)} 个图标")
        return icons
    except Exception as e:
        print(f"⚠️ 图标加载失败: {e}，将使用默认图标")
        return []

def generateM3U8(file):
    try:
        print(f"正在生成 M3U8: {file}")
        with open(file, "w", encoding='utf-8') as f:
            name = '成都电信IPTV - ' + datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            f.write(f'#EXTM3U name="{name}" url-tvg="{totalEPG}"\n')
            
            # 添加 GitHub Raw 播放地址（如果在 Actions 中）
            repo = os.environ.get("GITHUB_REPOSITORY")
            ref = os.environ.get("GITHUB_REF_NAME")
            if repo and ref:
                raw_url = f"https://raw.githubusercontent.com/{repo}/{ref}/home/iptv.m3u8"
                f.write(f'# 在线播放地址（可直接在播放器打开）: {raw_url}\n')
            f.write('\n')
            
            total = 0
            for group, channels in m.items():
                for ch in channels:
                    if "dup" in ch:
                        continue
                    catchup = buildCatchupSource(ch["rtsp_url"], ch["address"])
                    line1 = (f'#EXTINF:-1 tvg-logo="{ch["icon"]}" tvg-id="{ch["id"]}" '
                             f'tvg-name="{ch["name"]}" group-title="{group}" '
                             f'catchup="default" catchup-source="{catchup}",{ch["name"]}\n')
                    line2 = f'{homeLanAddress}/rtp/{ch["address"]}?FCC=182.139.234.40:8027\n'
                    f.write(line1)
                    f.write(line2)
                    total += 1
        print(f"✅ M3U8 生成成功，共 {total} 个频道")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        sys.exit(1)

def generateHome():
    generateM3U8("./home/iptv.m3u8")

# ---------- 🚀 最终稳定版 main() ----------
def main():
    # 1. 加载图标（非必须）
    icons = loadIcon()

    # 2. 从 API 获取频道数据（适配您提供的真实结构）
    api_url = "https://epg.51zmt.top:8001/multicast/api/channels/1/"
    headers = {
        "Referer": "https://epg.51zmt.top:8001/multicast/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        print(f"正在请求 API: {api_url}")
        session = requests.Session()
        # 先访问首页获取 Cookie
        session.get("https://epg.51zmt.top:8001/multicast/", verify=False, timeout=30)
        resp = session.get(api_url, headers=headers, verify=False, timeout=30)
        resp.raise_for_status()

        # 解析 JSON
        data = resp.json()
        
        # 检查响应状态
        if not data.get("success"):
            print(f"❌ API 返回失败状态: {data}")
            sys.exit(1)
        
        # 提取频道列表（关键！）
        channels_data = data.get("channels", [])
        if not isinstance(channels_data, list):
            print("❌ channels 字段不是列表")
            sys.exit(1)
            
        print(f"✅ API 请求成功，获取到 {len(channels_data)} 个频道")
        print(f"📺 数据来源: {data.get('source', {}).get('name', '未知')}")
        
    except Exception as e:
        print(f"❌ API 请求/解析失败: {e}")
        sys.exit(1)

    # 3. 将 API 数据转换为内部结构 m
    global m
    m = {}

    for item in channels_data:
        # ---------- 字段映射（完全适配您看到的API）----------
        name = item.get("channel_name", "").strip()
        address = item.get("multicast_address", "")  # 直接使用组播地址
        rtsp_url = item.get("replay_url", "")
        channel_id = str(item.get("index", ""))  # 使用 index 作为 tvg-id
        # ----------------------------------------------------

        # 过滤无用频道
        if not name or isIn(listUnused, name):
            continue

        # 清理名称（与原逻辑一致）
        name = name.replace('超高清', '').replace('高清', '').replace('-', '').strip()

        # 获取分组与图标
        groups = filterCategory(name)
        icon = findIcon(icons, name)

        # 构造频道信息对象
        channel_info = {
            "id": channel_id,
            "name": name,
            "address": address,
            "rtsp_url": rtsp_url,
            "ct": True,
            "icon": icon
        }

        # 添加到所有匹配的分组
        for group in groups:
            if group not in m:
                m[group] = []
            m[group].append(channel_info)

    # 4. 验证数据并生成 M3U8
    total_channels = sum(len(ch) for ch in m.values())
    if total_channels == 0:
        print("❌ 未获取到任何有效频道，终止")
        sys.exit(1)

    print(f"✅ 数据处理完成，共 {total_channels} 个频道，分组: {list(m.keys())}")
    for g, chs in m.items():
        print(f"   - {g}: {len(chs)} 个频道")

    generateHome()

if __name__ == "__main__":
    try:
        main()
        print("✅ 脚本执行成功")
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ 严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
