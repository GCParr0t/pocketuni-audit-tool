# -*- coding: utf-8 -*-
# File: Fetch_html_element.py
# Author: GCPAT
# Date: 2023/12/3
# Description: request.get获取etree.Element对象<模块>
# Tool: PyCharm
# Python:3.11.0
import asyncio
import re
import sys
from random import sample

import aiohttp
import requests.exceptions
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from lxml import etree
from requests import get
from requests import post

from Module.SQL_operate import SQL_operate


def login(username: str, password: str) -> bool:
    """
    登录函数; cookie与response.json()写入全局变量.

    :param username: 用户名
    :param password: 密码
    :return: None
    :rtype: NoneType
    """

    url = "https://pocketuni.net/index.php?app=api&mod=Sitelist&act=login"
    rand = ''.join(sample("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", 16))

    header = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "654",
        "Content-Type": f"multipart/form-data; boundary=----WebKitFormBoundary{rand}",
        "DNT": "1",
        "Host": "pocketuni.net",
        "Origin": "https://pc.pocketuni.net",
        "Pragma": "no-cache",
        "Referer": "https://pc.pocketuni.net/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                      " (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.69",
        "sec-ch-ua": '"Chromium";v="118", "Microsoft Edge";v="118", "Not=A?Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "Windows"
    }

    payload = f"""------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="email"

{username}@hhit.com
------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="password"

{password}
------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="type"

pc
------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="usernum"

{username}
------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="sid"


------WebKitFormBoundary{rand}
Content-Disposition: form-data; name="school"

@hhit.com
------WebKitFormBoundary{rand}--"""

    try:
        if str(username)[5:] == "21181":
            response = post(url=url, headers=header, data=payload, timeout=10)
            if response.json()["message"] == "success":
                SQL_operate.set_var("cookie", response.cookies.get_dict())
                SQL_operate.set_var("json", response.json())
                return True
            else:
                return False
        else:
            sys.exit(-1)
    except Exception as e:
        print(e)
        return False


def U(action_tag: str, activity_id: str | int = None, uid: str | int = None, pid: str | int = None, page: str | int = None) -> str:
    """
    生成url.

    :param action_tag: 操作标签
    :param activity_id: 活动id
    :param uid: 用户id
    :param pid: pid
    :param page: 页数
    :return: url
    """
    parameter = {"app": "event", "mod": "Author", "act": action_tag}

    if activity_id:
        parameter["id"] = activity_id

    if uid:
        parameter["mid"] = uid

    if pid:
        parameter["pid"] = pid

    if page:
        parameter["p"] = page

    url = "https://www.pocketuni.net/index.php?" + "&".join([f"{k}={v}" for k, v in parameter.items()])

    return url


def fetch_html_element(url: str):
    """
    获取解析后的html文档对象.

    :param url: url
    :return: html文档对象
    :rtype: etree.HTML
    """
    try:
        source = get(url=url, cookies=SQL_operate.fetch_var("cookie"))
        if source.status_code == 200:
            return etree.HTML(source.text)
        else:
            print("获取失败,正在重试...")
            return fetch_html_element(url)
    except requests.exceptions.ConnectTimeout:
        print("连接超时,正在重试...")
        return fetch_html_element(url)


def page_count(html) -> int:
    """
    统计有多少页.

    :return: 页数
    :rtype: int
    """
    def extract_number(s: str) -> int:
        result = re.findall(r"\d+", s)
        return int(''.join(result))

    try:
        if bool(html.xpath("//*[@class='page']/text()[normalize-space()]")):
            total_page = extract_number(
                html.xpath("//*[@class='page']/text()[normalize-space()]")[0])
            return total_page
        elif bool(html.xpath("//*[@class='page']/a[last()-1]/text()[normalize-space()]")):
            total_page = extract_number(
                html.xpath("//*[@class='page']/a[last()-1]/text()[normalize-space()]")[0])
            return total_page
        elif not bool(html.xpath("//*[@class='page']/text()[normalize-space()]")) and not bool(html.xpath(
                "//*[@class='page']/a[last()-1]/text()[normalize-space()]")):
            total_page = 1
            return total_page
        else:
            print("获取页数失败")
    except Exception:
        print("获取页数失败: " + str(Exception))


def fetch_and_storage_ActivityList() -> None:
    """
    获取活动列表并存储.

    :return: 活动列表的元组
    :rtype: dict[activity_name: activity_url]
    """
    url = "https://pocketuni.net/index.php?app=event&mod=School&act=board&cat=nofinish"
    li_list = []
    activity_list = []
    for page in range(1, page_count(fetch_html_element(url)) + 1):
        li_list.extend(fetch_html_element(url + f"&p={page}").xpath("//div[@class='hd_c_left']/ul/li"))
    for item in li_list:
        activity_list.append((item.xpath(".//*[@class='hd_c_left_title b']/a/text()")[0], item.xpath(".//*[@class='hd_c_left_title b']/a/@href")[0], item.xpath("boolean(.//li[contains(@class, 'i4')])")))

    SQL_operate.set_var("activity_name_and_url_list", activity_list)


def Choose_Activity_AND_Get_URL_and_ID(order: int) -> None:
    """
    获取活动的url和id.

    :param order: 活动编号
    :return: 活动的url
    :rtype: None
    """
    _, activity_url, activity_is_finished = SQL_operate.fetch_var("activity_name_and_url_list")[order - 1]
    activity_id = next((param.split("=")[1] for param in activity_url.split(
        "&") if param.startswith("id=")))
    SQL_operate.set_var("activity_id", activity_id)
    SQL_operate.set_var("activity_is_finished", activity_is_finished)


def fetch_uploadConfig(activity_id: str | int) -> dict[str, str]:
    """
    获取上传配置

    :param activity_id: 活动id
    :return: 部分配置列表
    :rtype: dict
    """
    try:
        html = etree.HTML(get(U("upConfig", activity_id=activity_id),
                          cookies=SQL_operate.fetch_var("cookie")).text)
        return dict(zip(html.xpath("//*[@name='realname']/@value | //*[@name='school']/@value | //*[@name='content']/@value | //*[@name='path']/@value | //*[@class='mouse']/td[1]/input/@value"), [
                    *["文本" for _ in range(3)], "img", *html.xpath("//option[@selected='selected']/text()")]))
    except (requests.exceptions.RequestException, etree.ParserError) as e:
        print(f"获取上传配置失败,错误信息：{e},正在重试...")
        return fetch_uploadConfig(activity_id)


async def fetch_element(url: str):
    """
    获取解析后的html文档对象.

    :param url: url
    :return: html文档对象
    :rtype: etree.HTML
    """
    try:
        async with aiohttp.ClientSession(cookies=SQL_operate.fetch_var("cookie")) as session:
            async with session.get(url=url) as response:
                if response.status == 200:
                    text = await response.text()
                    if text:
                        html = etree.HTML(text)
                        # 检查HTML文档是否包含</html>标签
                        if html.xpath('//html'):
                            return html
                        else:
                            print("HTML文档可能不完整，正在重试...")
                            return await fetch_element(url)
                    else:
                        print("返回为空,正在重试...")
                        return await fetch_element(url)
                else:
                    print("获取失败,正在重试...")
                    return await fetch_html_element(url)
    except aiohttp.ClientError:
        print("连接超时,正在重试...")
        return await fetch_html_element(url)


async def fetch_sid(url: str) -> list[tuple[str, str]]:
    """
    获取uid和sid.

    :param url: url
    :return: list[tuple[uid, sid]]
    :rtype: list[tuple[uid, sid]]
    """
    data = (await fetch_element(url)).xpath("//*[starts-with(@id, 'list_')]/td[2]/text() | //*[@id='checkbox2']/@value")
    return [(data[i + 1], data[i]) for i in range(0, len(data), 2)]


async def fetch_showPlayer(activity_id: str | int, uid: str | int, sid: str | int, cookies) -> dict[str, str]:
    """
    显示选手信息

    :param cookies: cookies
    :param activity_id: 活动id
    :param uid: uid
    :param sid: sid
    :return: 选手信息
    :rtype: dict
    """
    async with ClientSession(cookies=cookies) as session:
        async with session.post(U("showPlayer", activity_id=activity_id, pid=sid), data={"id": activity_id, "pid": sid}) as response:
            try:
                text = await response.text()
                if text:
                    config_list = SQL_operate.fetch_upConfig_list(activity_id)
                    # 创建一个BeautifulSoup对象
                    soup = BeautifulSoup(text, 'html.parser')

                    # 找到所有的<center>标签
                    decompose_tags = soup.find_all(['center', 'script'])
                    for tag in decompose_tags:
                        tag.decompose()

                    # 找到特定的<div>标签
                    specific_div = soup.find('div')

                    # 删除特定的<div>标签，但保留其内部的内容
                    if specific_div:
                        specific_div.unwrap()

                    # 将处理后的HTML内容转换为字符串
                    html_str = str(soup)

                    # 使用<br />标签将字符串分割
                    split_content = [content.replace('\n', '') for content in html_str.split('<br/>') if
                                     content.strip()]

                    # 初始化字典来存储提取的数据
                    data = {}

                    # 遍历处理过的列表
                    for content in split_content:
                        # 使用BeautifulSoup解析内容
                        soup = BeautifulSoup(content, 'html.parser')

                        # 找到所有的<strong>标签
                        strong_tags = soup.find_all('strong')

                        # 遍历所有的<strong>标签
                        for tag in strong_tags:
                            # 获取<strong>标签中的内容，并去除冒号
                            key = tag.get_text().replace('：', '')

                            # 获取<strong>标签后的内容
                            values = tag.next_siblings

                            # 初始化一个列表来存储所有的内容
                            all_content = []

                            # 初始化一个列表来存储<p>标签的文本内容
                            p_content = []

                            # 遍历所有的兄弟标签和字符串
                            for value in values:
                                # 如果内容是一个标签（例如<a>或<img>），则获取其'href'或'src'属性
                                if hasattr(value, 'attrs'):
                                    if 'href' in value.attrs:
                                        # 分割链接并取第一部分
                                        content = value['href'].split('?imageView2/0/w/100/h/125')[0]
                                        if content != '+':
                                            all_content.append(content)
                                    elif 'src' in value.attrs:
                                        # 分割链接并取第一部分
                                        content = value['src'].split('?imageView2/0/w/100/h/125')[0]
                                        if content != '+':
                                            all_content.append(content)
                                    elif value.name == 'p':
                                        # 如果内容是一个<p>标签，获取其文本内容
                                        p_content.append(value.text.strip())
                                else:
                                    # 否则，获取其文本内容
                                    content = value.strip()
                                    if content and content != '+':
                                        all_content.append(content)

                            # 如果p_content列表中有内容，使用'\n'将其连接起来并添加到all_content列表中
                            if p_content:
                                all_content.append('\n'.join(p_content))

                            # 如果只有一个值，直接添加到字典中，否则添加列表
                            if len(all_content) == 1:
                                data[key] = all_content[0]
                            else:
                                data[key] = all_content

                    return {"UID": uid, "SID": sid, **{k: v for k, v in data.items() if k in config_list}}
                else:
                    print("获取选手信息失败,正在重试...")
                    return await fetch_showPlayer(activity_id, uid, sid, cookies)
            except aiohttp.ClientError as e:
                print(f"获取选手信息失败，错误信息：{e}，正在重试...")
                return await fetch_showPlayer(activity_id, uid, sid, cookies)


async def worker(result, activity_id, cookies):
    for key, value in list(result.items())[5:]:
        if isinstance(value, str):
            result[key] = await download(value, cookies)
        elif isinstance(value, list):
            result[key] = [await download(item, cookies) for item in value]
    while not await SQL_operate.write_activity_upload_info(activity_id, result):
        print("写入数据库失败，正在重试...")
        await asyncio.sleep(1.2)


async def download(url: str, cookies: dict) -> bytes:
    """
    下载资源.

    :param cookies:
    :param url: url
    :return: bytes
    """
    try:
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url=url) as resp:
                if resp.status == 200:
                    data = await resp.read()  # 读取数据
                    file_size = resp.content_length  # 获取文件大小
                    print(f"文件大小: {file_size}")
                    actual_size = len(data)  # 获取实际下载的数据大小

                    if actual_size == file_size:  # 如果实际下载的数据大小等于文件大小
                        return data
                    else:
                        print("下载失败，实际下载的数据大小与文件大小不符，正在重试...")
                        return await download(url, cookies)
                else:
                    print("下载失败，正在重试...")
                    return await download(url, cookies)
    except Exception as e:
        print(f"下载出错，错误信息：{e}，正在重试...")
        return await download(url, cookies)
