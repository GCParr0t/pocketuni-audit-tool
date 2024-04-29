# -*- coding: utf-8 -*-
# File: Fetch_page_and_cache.py
# Author: GCPAT
# Date: 2023/12/3
# Description: 爬取页面并缓存后n页<模块>
# Tool: PyCharm
# Python:3.11.0
import asyncio

from PyQt5.QtCore import QThread

from Module.Fetch_html_element import fetch_html_element, U, page_count, fetch_element, fetch_sid, fetch_showPlayer, \
    worker
from Module.Fetch_html_element import fetch_uploadConfig
from Module.SQL_operate import SQL_operate


class ManagerProcessingThread(QThread):
    def __init__(self):
        super().__init__()

    def run(self):
        activity_id = SQL_operate.fetch_var("activity_id")

        while SQL_operate.creat_activity_db(activity_id, fetch_uploadConfig(activity_id)):
            asyncio.run(fetch_member_info_write_SQL(activity_id))


class AuditProcessingThread(QThread):
    def __init__(self):
        super().__init__()

    def run(self):
        activity_id = SQL_operate.fetch_var("activity_id")

        while SQL_operate.creat_activity_db(activity_id, fetch_uploadConfig(activity_id)):
            asyncio.run(fetch_member_info_write_SQL(activity_id))
            asyncio.run(fetch_upload_write_SQL(activity_id))
            SQL_operate.sync_data_to_audit_info(activity_id)


class DeleteProcessingThread(QThread):
    def __init__(self):
        super().__init__()

    def run(self):
        activity_id = SQL_operate.fetch_var("activity_id")

        while SQL_operate.creat_activity_db(activity_id, fetch_uploadConfig(activity_id)):
            asyncio.run(fetch_member_info_write_SQL(activity_id))
            asyncio.run(fetch_upload_write_SQL(activity_id))
            asyncio.run(fetch_passed_member_info_write_SQL(activity_id))

################################
    # 选手界面->提交id->命名为sid
    # uid, pid 用于设置管理员
    # aid, sid 用于查看选手信息


async def fetch_member_info_write_SQL(activity_id: str | int) -> None:
    """
    获取成员信息并写数据到数据库

    :param activity_id: 活动id
    :return: None
    :rtype: None
    """

    async def fetch_page_info(page: int):
        html = await fetch_element(U("member", activity_id=activity_id, page=page))
        li_list = html.xpath("//*[@class='member_tr2']")
        for li in li_list:
            if li.xpath("boolean(./td[12]/a[2]/text())"):
                ids = li.xpath("./td[12]/a[2]/@href")[0]
                uid, pid = ids.split("','")[0].split("'")[-1], ids.split("','")[2].split("'")[0]
                whether_sign_manger = True if '取消签到员' == li.xpath("./td[12]/a[2]/text()")[0] else False
                name = li.xpath("./td[3]/text()")[0]
                sn = li.xpath("./td[9]/text()")[0]
                whether_sign = li.xpath("boolean(./td[6]/text())")
                print(f"fetch_page_info, 正在获取{name}的信息...")

                while not await SQL_operate.write_activity_member_info(activity_id, uid, pid, name, sn, whether_sign, whether_sign_manger):
                    print("写入数据库失败，正在重试...")
                    await asyncio.sleep(1.2)
        print(f"第{page}页的成员信息获取完成")

    tasks = [fetch_page_info(page) for page in
             range(1, page_count(fetch_html_element(U("member", activity_id=activity_id))) + 1)]
    await asyncio.gather(*tasks)
    print("完成获取成员信息")


async def fetch_upload_write_SQL(activity_id: str | int) -> bool:
    """
    获取上传资料并写数据到数据库

    :param activity_id: 活动id
    :return: None
    :rtype: None
    """
    uid_sid_pairs, tasks, tasks_, results = [], [], [], []
    cookies = SQL_operate.fetch_var("cookie")
    for page in range(1, page_count(fetch_html_element(U("playerUpload", activity_id=activity_id))) + 1):
        print(f"正在获取第{page}页的uid和sid...")
        task = asyncio.create_task(fetch_sid(U("playerUpload", activity_id=activity_id, page=page)))
        uid_sid_pairs.append(task)
    done, _ = await asyncio.wait(uid_sid_pairs, return_when=asyncio.ALL_COMPLETED)
    uid_sid_pairs = [item for future in done for item in future.result()]
    if uid_sid_pairs:
        for uid, sid in uid_sid_pairs:
            print(f"获取上传资料并写数据到数据库, 正在获取文件类型:  uid: {uid};sid:{sid},")
            task = asyncio.create_task(fetch_showPlayer(activity_id, uid, sid, cookies))
            tasks.append(task)
        done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        results = [future.result() for future in done]
        for result in results:
            print(f"获取上传资料并写数据到数据库, 正在获取文件:  uid: {result['UID']};sid:{result['SID']},")
            task = asyncio.create_task(worker(result, activity_id, cookies))
            tasks_.append(task)
        _, _ = await asyncio.wait(tasks_, return_when=asyncio.ALL_COMPLETED)
        print("下载完成")
        SQL_operate.set_var("all_passed", False)
        return True
    else:
        print("没有文件可下载")
        SQL_operate.set_var("all_passed", True)
        return False


async def fetch_passed_member_info_write_SQL(activity_id: str | int) -> None:
    """
    获取通过审核的成员信息并写数据到数据库

    :param activity_id: 活动id
    :return: None
    :rtype: None
    """
    tasks = []
    for page in range(1, page_count(fetch_html_element(U("player", activity_id=activity_id))) + 1):
        task = asyncio.create_task(fetch_element(U("player", activity_id=activity_id, page=page)))
        tasks.append(task)
    done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    htmls = [future.result() for future in done]
    uids = [uid for html in htmls for uid in html.xpath("//*[starts-with(@id, 'list_')]/td[6]/text()")]
    await SQL_operate.write_passed_member_info(activity_id, uids)
