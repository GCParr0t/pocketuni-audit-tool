# -*- coding: utf-8 -*-
# File: Action_Module.py
# Author: GCPAT
# Date: 2023/12/30
# Description: 操作接口<模块>
# Tool: PyCharm
# Python: 3.11.0
import os

from requests import post

from Config import csv_dir
from Module.Fetch_html_element import U
from Module.SQL_operate import SQL_operate


# mid: member id = UID
# eventId: event id
# sid: sid (用户在这次活动提交心得生成的sid)
# pid: pid (用户在这次活动中生成的pid)
# aid: activity id


def header(activity_id):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://pocketuni.net",
        "Referer": f"https://pocketuni.net/index.php?app=event&mod=Author&act=member&id={activity_id}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "X-Requested-With": "XMLHttpRequest"
    }
    return headers


##############################
def determine(response) -> bool:
    """
    判断是否成功

    :param response: response
    :return: 判断结果
    :rtype: bool
    """
    if 'json' in response.headers['Content-Type']:
        try:
            if response.json()["status"] == 1:
                return True
            else:
                return False
        except KeyError:
            return False
    else:
        return False


def adminDelMemberAction(
        activity_id: str | int,
        pid: str | int) -> bool:
    """
    删除成员

    :param activity_id: 活动id
    :param pid: pid
    :return: bool
    :rtype: bool
    """
    response = (
        post(
            U("doDeleteMember"),
            data={
                "mid": pid,
                "id": activity_id},
            cookies=SQL_operate.fetch_var("cookie"),
            headers=header(activity_id)
        ))
    return determine(response)


def adminSetSignManagerAction(
        activity_id: str | int,
        uid: str | int) -> bool:
    """
    设置扫码员

    :param activity_id: 活动id
    :param uid: 用户id
    :return: bool
    :rtype: bool
    """
    response = (
        post(
            U("setSignManager"),
            data={
                "mid": uid,
                "id": activity_id},
            cookies=SQL_operate.fetch_var("cookie"),
            headers=header(activity_id)
        ))
    return determine(response)


def adminCancelSignManagerAction(
        activity_id: str | int,
        uid: str | int) -> bool:
    """
    取消扫码员

    :param activity_id: 活动id
    :param uid: 用户id
    :return: bool
    :rtype: bool
    """
    response = (
        post(
            U("cancleSignManager"),
            data={
                "mid": uid,
                "id": activity_id},
            cookies=SQL_operate.fetch_var("cookie"),
            headers=header(activity_id)
        ))
    return determine(response)


###########################


def allowUploadAction(activity_id: str | int, sid: str | int) -> bool:
    """
    通过选手

    :param activity_id: 活动id
    :param sid: pid
    :return:
    """
    act = "通过选手"
    response = (
        post(
            U("doAllowPlayer"),
            data={
                "id": activity_id,
                "pid": sid},
            cookies=SQL_operate.fetch_var("cookie"),
            headers=header(activity_id)
        ))
    return determine(response)


def rejUploadAction(activity_id: str | int, sid: str | int, reason: str) -> bool:
    """
    驳回选手

    :param activity_id: 活动id
    :param sid: pid
    :param reason: 驳回理由
    :return: None
    :rtype: None
    """
    act = "驳回选手"
    if reason:
        response = (
            post(
                U("doDeletePlayer"),
                data={
                    "id": activity_id,
                    "pid": sid,
                    "rej": str(reason),
                    "del": 1},
                cookies=SQL_operate.fetch_var("cookie"),
                headers=header(activity_id)
            ))
        return determine(response)
    else:
        print("驳回理由不能为空")
        return False


###########################


def Audit(
        flag: bool,
        activity_id: str | int,
        sid: str | int,
        reason=None) -> bool:
    """
    审核.

    :param flag: -通过- 或者 -驳回-
    :param activity_id: 活动id
    :param sid: sid
    :param reason: 驳回理由，可选，默认为 "请按要求上传材料"
    :return: bool
    """
    if not reason:
        reason = "请按要求上传材料"
    if flag:
        return allowUploadAction(activity_id, sid)
    elif not flag:
        return rejUploadAction(activity_id, sid, reason)
    else:
        print("审核失败")


def delMember(flag: bool, activity_name: str, activity_id: str | int, today, random_uuid: str) -> None:
    """
    flag: True--删除未签到成员
    flag: False--删除未上传资料成员
    :param today: 日期
    :param random_uuid: 随机防重
    :param flag: 选择
    :param activity_name: 活动名称
    :param activity_id: 活动id
    :return: bool
    """
    member, uid_list, error_list = [], [], []
    file_type = ""
    if flag:
        member = SQL_operate.fetch_unSigned(activity_id)
        file_type = "未签到成员"
    elif not flag:
        member = SQL_operate.de_wight(activity_id)
        file_type = "未上传资料成员"

    for uid, pid in member:
        uid_list.append(uid)
        if not adminDelMemberAction(activity_id, pid):
            uid_list.remove(uid)
            error_list.append(uid)
    name_sn_list = SQL_operate.find_name_sn_by_uid(activity_id, uid_list)
    error_name_sn_list = SQL_operate.find_name_sn_by_uid(activity_id, error_list)

    with open(os.path.join(csv_dir, f"{today}_{activity_name}_{file_type}_({random_uuid}).csv"), "w") as f:
        f.write(f"{activity_name},\n")
        f.write(f"{file_type}：\n")
        f.write(f"姓名, 学号,\n")
        for name, sn in name_sn_list:
            sensitized_name = name[:-1] + '*'
            f.write(f"{sensitized_name}, {sn}\n")

    if error_name_sn_list:
        with open(os.path.join(csv_dir, f"{today}_{activity_name}_删除失败成员_({random_uuid}).csv"), "w") as f:
            f.write(f"{activity_name},\n")
            f.write(f"删除失败成员：\n")
            f.write(f"姓名, 学号,\n")
            for name, sn in error_name_sn_list:
                f.write(f"{name}, {sn}\n")
