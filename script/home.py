#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import re
import sys
import os

# 配置常量
homeLanAddress = "http://192.168.10.2:4022"
catchupBaseUrl = "http://192.168.10.2:4022"

# EPG源 - 暂时留空，可以后续添加可用的EPG源
totalEPG = "https://epg.112114.xyz/pp.xml"  # 例如："https://example.com/epg.xml,https://example2.com/epg2.xml"

# 本地文件路径 - 使用相对路径
script_dir = os.path.dirname(os.path.abspath(__file__))
local_multicast_file = os.path.join(script_dir, "sctvmulticast.html")

# 分组配置
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
    """
    返回频道名匹配的所有分组
    一个频道可以同时属于多个分组
    """
    categories = []
    
    if isIn(groupCCTV, v):
        categories.append("CCTV")
    if isIn(groupWS, v):
        categories.append("卫视")
    if isIn(group4K, v):
        categories.append("4K")
    if isIn(groupSC, v):
        categories.append("四川")
    
    # 如果没有匹配任何分组，则归类为"其他"
    if not categories:
        categories.append("其他")
    
    return categories

def findIcon(channel_name):
    """
    查找频道图标
    可以根据需要添加图标映射
    """
    return ""

def buildCatchupSource(rtsp_url, original_url):
    """
    构建回看源URL
    从rtsp URL中提取主机地址和路径部分，与catchupBaseUrl拼接
    """
    if not rtsp_url or not rtsp_url.startswith("rtsp://"):
        return ""

    # 从rtsp URL中提取主机地址和路径部分
    url_without_protocol = rtsp_url[7:]  # 移除 "rtsp://"
    path_start = url_without_protocol.find("/")
    if path_start == -1:
        return ""

    rtsp_host = url_without_protocol[:path_start]  # 获取主机地址
    rtsp_path = url_without_protocol[path_start:]  # 获取路径部分

    # 构建完整的回看源URL，使用动态提取的主机地址
    catchup_source = f"{catchupBaseUrl}/rtsp/{rtsp_host}{rtsp_path}?playseek=${{(b)yyyyMMddHHmmss}}-${{(e)yyyyMMddHHmmss}}"

    return catchup_source

def loadLocalMulticastData(file_path):
    """
    从本地HTML文件加载组播数据
    """
    try:
        if not os.path.exists(file_path):
            print(f"❌ 本地文件不存在: {file_path}")
            print(f"当前脚本位置: {script_dir}")
            print(f"查找的文件: {os.path.basename(file_path)}")
            print("请确保sctvmulticast.html文件存在于脚本目录中")
            return None
            
        print(f"正在从本地文件读取数据: {os.path.basename(file_path)}")
        print(f"文件完整路径: {file_path}")
        
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"✅ 使用{encoding}编码成功读取文件")
                break
            except UnicodeDecodeError:
                continue
        else:
            print("❌ 无法用任何已知编码读取文件")
            return None
            
        if not content:
            print("⚠️  本地文件内容为空")
            return None
            
        soup = BeautifulSoup(content, 'lxml')
        
        # 检查是否有有效的频道数据行
        valid_rows = 0
        for tr in soup.find_all('tr'):
            td = tr.find_all('td')
            if len(td) >= 7 and td[0].string and td[0].string != "序号":
                valid_rows += 1
                
        if valid_rows == 0:
            print("⚠️  未找到标准的频道数据行，尝试其他表格结构...")
            
        print(f"成功读取文件，找到 {valid_rows} 条标准频道数据")
        return soup
        
    except Exception as e:
        print(f"❌ 读取本地文件时发生错误: {e}")
        print("请检查文件格式和内容")
        return None

def generateM3U8(file):
    """
    生成M3U8文件，包含异常处理
    """
    try:
        # 确保home目录存在
        home_dir = os.path.dirname(file)
        if home_dir and not os.path.exists(home_dir):
            os.makedirs(home_dir)
            print(f"已创建目录: {home_dir}")
            
        print(f"正在生成M3U8文件: {file}")
        with open(file, "w", encoding='utf-8') as f:
            name = '成都电信IPTV - ' + datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # 如果有EPG源，则添加到M3U8头部
            if totalEPG and totalEPG.strip():
                title = f'#EXTM3U name="{name}" url-tvg="{totalEPG}"\n\n'
            else:
                title = f'#EXTM3U name="{name}"\n\n'
                
            f.write(title)

            total_written = 0
            for k, v in m.items():
                for c in v:
                    if "dup" in c:
                        continue

                    # 构建回看源URL
                    catchup_source = buildCatchupSource(c["rtsp_url"], c["address"])

                    # 生成M3U8条目
                    line = (f'#EXTINF:-1 tvg-logo="{c["icon"]}" tvg-id="{c["id"]}" '
                           f'tvg-name="{c["name"]}" group-title="{k}" ')
                    
                    # 如果有回看源，则添加catchup参数
                    if catchup_source:
                        line += f'catchup="default" catchup-source="{catchup_source}",{c["name"]}\n'
                    else:
                        line += f'{c["name"]}\n'
                        
                    line2 = f'{homeLanAddress}/rtp/{c["address"]}?FCC=182.139.234.40:8027\n'

                    f.write(line)
                    f.write(line2)
                    total_written += 1

        print(f"✅ M3U8文件生成成功，共写入 {total_written} 个频道")
        print(f"文件位置: {os.path.abspath(file)}")
        
    except IOError as e:
        print(f"❌ 文件写入失败: {e}")
        print("请检查文件路径和写入权限")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成M3U8文件时发生未知错误: {e}")
        sys.exit(1)

def generateHome():
    # 确保home目录存在（相对于脚本所在目录的上一级）
    home_dir = os.path.join(os.path.dirname(script_dir), "home")
    if not os.path.exists(home_dir):
        os.makedirs(home_dir)
    generateM3U8(os.path.join(home_dir, "iptv.m3u8"))

def main():
    # 从本地文件获取成都组播数据
    soup = loadLocalMulticastData(local_multicast_file)
    
    if soup is None:
        print("❌ 无法读取本地组播数据，程序退出")
        sys.exit(1)

    global m
    m = {}

    processed_channels = 0
    skipped_channels = 0
    
    for tr in soup.find_all(name='tr'):
        td = tr.find_all(name='td')
        
        # 确保有足够的列并且不是表头
        if len(td) < 3 or (td[0].string and "序号" in td[0].string):
            continue
            
        # 获取频道信息
        channel_name = td[1].string if len(td) > 1 and td[1].string else None
        channel_address = td[2].string if len(td) > 2 and td[2].string else None
        
        if not channel_name or not channel_address:
            skipped_channels += 1
            continue
            
        # 过滤不需要的频道
        if isIn(listUnused, channel_name):
            skipped_channels += 1
            continue

        # 设置ID
        if len(td) > 0 and td[0].string and td[0].string.isdigit():
            try:
                setID(int(td[0].string))
            except ValueError:
                pass

        # 清理频道名称
        name = channel_name
        name = name.replace('超高清', '').replace('高清', '').replace('-', '').strip()

        groups = filterCategory(name)
        icon = findIcon(name)

        # 提取rtsp URL
        rtsp_url = td[6].string if len(td) > 6 and td[6].string else ""

        # 创建频道信息对象
        channel_info = {
            "id": td[0].string if len(td) > 0 and td[0].string else str(getID()),
            "name": name,
            "address": channel_address,
            "rtsp_url": rtsp_url,
            "ct": True,
            "icon": icon
        }

        # 将频道添加到所有匹配的分组中
        for group in groups:
            if group not in m:
                m[group] = []
            m[group].append(channel_info)
            
        processed_channels += 1

    # 验证是否有足够的频道数据
    total_channels = sum(len(channels) for channels in m.values())
    if total_channels == 0:
        print("❌ 未获取到任何频道数据，无法生成M3U8文件")
        print(f"已处理: {processed_channels} 个频道，跳过: {skipped_channels} 个频道")
        sys.exit(1)
    
    print(f"✅ 数据处理完成，共获取到 {total_channels} 个频道，分布在 {len(m)} 个分组中")
    print(f"已处理: {processed_channels} 个频道，跳过: {skipped_channels} 个频道")
    
    for group, channels in sorted(m.items()):
        print(f"   - {group}: {len(channels)} 个频道")

    generateHome()

if __name__ == "__main__":
    try:
        print("=" * 50)
        print("成都IPTV M3U8生成器 - 本地模式")
        print("=" * 50)
        print(f"脚本目录: {script_dir}")
        print(f"数据文件: {local_multicast_file}")
        print(f"EPG源: {totalEPG if totalEPG else '无'}")
        print("=" * 50)
        main()
        print("✅ 脚本执行成功完成")
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ 脚本执行过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)