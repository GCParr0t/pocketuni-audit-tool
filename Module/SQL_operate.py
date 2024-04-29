# -*- coding: utf-8 -*-
# File: SQL_operate.py
# Author: GCPAT
# Date: 2023/11/28
# Description: 全局变量操作<模块>
# Tool: PyCharm
# Python: 3.11.0

import sqlite3
import aiosqlite

from pickle import dumps, loads
from typing import Any

from singleton_decorator import singleton

from Config import path

import inspect


def my_function_name():
    return inspect.getframeinfo(inspect.currentframe().f_back).function


@singleton
class DatabaseManager:
    def __init__(self):
        self.db_path = path + '/temp.db'
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_var (
                name TEXT PRIMARY KEY NOT NULL,
                value BLOB
                );
            ''')
            self.conn.commit()
            cursor.close()
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def creat_activity_db(self, activity_id, *args) -> bool:
        """
        创建活动表.

        :param activity_id: 活动id
        :param args: 参数<dict>
        :return: None
        """
        try:
            cursor = self.conn.cursor()
            query = f'''
                    CREATE TABLE IF NOT EXISTS aid_{str(activity_id)}_upConfig_list (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        upConfig TEXT NOT NULL UNIQUE,
                        Type TEXT NOT NULL
                        );
                        '''
            cursor.execute(query)
            self.conn.commit()
            cursor.close()
            cursor = self.conn.cursor()
            query = f'''
                    CREATE TABLE IF NOT EXISTS aid_{str(activity_id)}_upload_info (
                        UID INTEGER PRIMARY KEY NOT NULL UNIQUE,
                        SID INTEGER NOT NULL UNIQUE
                        );'''
            cursor.execute(query)
            self.conn.commit()
            cursor.close()
            cursor = self.conn.cursor()
            query = f'''
                    CREATE TABLE IF NOT EXISTS aid_{str(activity_id)}_member_info (
                        UID INTEGER PRIMARY KEY NOT NULL UNIQUE,
                        PID INTEGER NOT NULL UNIQUE,
                        NAME TEXT NOT NULL,
                        SID_NUMBER INTEGER NOT NULL UNIQUE,
                        whetherSIGN BOOLEAN NOT NULL,
                        whetherSIGN_MANAGER BOOLEAN NOT NULL
                        );'''
            cursor.execute(query)
            self.conn.commit()
            cursor.close()
            cursor = self.conn.cursor()
            query = f'''
                    CREATE TABLE IF NOT EXISTS aid_{str(activity_id)}_pass_info (
                        UID INTEGER PRIMARY KEY NOT NULL UNIQUE,
                        FOREIGN KEY(UID) REFERENCES aid_{str(activity_id)}_member_info(UID)
                        );'''
            cursor.execute(query)
            self.conn.commit()
            cursor.close()
            cursor = self.conn.cursor()
            query = f'''
                    CREATE TABLE IF NOT EXISTS aid_{str(activity_id)}_audit_info (
                        UID INTEGER PRIMARY KEY NOT NULL UNIQUE,
                        SID INTEGER NOT NULL UNIQUE,
                        ApprovalOrRejection BOOLEAN,
                        Reason TEXT,
                        FOREIGN KEY(UID, SID) REFERENCES aid_{str(activity_id)}_upload_info(UID, SID)
                        );'''
            cursor.execute(query)
            self.conn.commit()
            cursor.close()

            if args:
                cursor = self.conn.cursor()
                for key, value in {'UID': "INTEGER", 'SID': "INTEGER", **args[0]}.items():
                    query = f"INSERT OR REPLACE INTO aid_{str(activity_id)}_upConfig_list (upConfig, Type) VALUES (?, ?)"
                    cursor.execute(query, (str(key), str(value),))
                self.conn.commit()
                cursor.close()
                cursor = self.conn.cursor()
                for raw in list(args[0].keys())[:3]:
                    query = f"ALTER TABLE aid_{str(activity_id)}_upload_info ADD COLUMN {str(raw)} TEXT;"
                    cursor.execute(query)
                self.conn.commit()
                cursor.close()
                cursor = self.conn.cursor()
                for raw in list(args[0].keys())[3:]:
                    query = f'''
                                ALTER TABLE aid_{str(activity_id)}_upload_info ADD COLUMN {str(raw)} BLOB;
                                '''
                    cursor.execute(query)
                self.conn.commit()
                cursor.close()
                return True
            else:
                print("参数为空.")
                return False
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def set_var(self, var_name: str, value: Any) -> bool:
        """
        设置.

        :return: Bool
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO activity_var VALUES (?, ?)", (var_name, dumps(value)))
            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def fetch_var(self, *args) -> Any | list[Any]:
        """
        获取.

        :return: var
        """
        try:
            cursor = self.conn.cursor()
            li = [loads(cursor.execute(f"SELECT value FROM activity_var WHERE name = '{name}'").fetchone()[0]) for
                  name in args]
            cursor.close()
            if len(args) == 1:
                return li[0]
            else:
                return li
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def del_var(self, *args) -> bool:
        """
        删除.

        :return: Bool
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"DELETE FROM activity_var WHERE name IN (?)", (', '.join(args),))
            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    ##########
    # 以下是对活动表的操作

    @staticmethod
    async def write_activity_upload_info(activity_id: str | int, dicts: dict) -> bool:
        """
        保存上传资料到数据库.

        :return: Bool
        """
        db_path = path + '/temp.db'
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.cursor()
                await cursor.execute(f"SELECT upConfig FROM aid_{str(activity_id)}_upConfig_list ORDER BY id")
                config = [i[0] for i in await cursor.fetchall()]

                dic = {k: v for k, v in dicts.items() if k in config}

                await cursor.execute(
                    f"INSERT OR REPLACE INTO aid_{str(activity_id)}_upload_info ({', '.join(dic.keys())}) VALUES ({', '.join('?' * (len(config)))})",
                    (tuple([*[*dic.values()][:5], *[dumps(item) for item in [i for i in dic.values()][5:]]])))
                await db.commit()

                print(f"{[value for index, value in enumerate(dic.values()) if index == 2][0]}写入成功")
                return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    @staticmethod
    async def write_activity_member_info(activity_id: str | int, uid: str | int, pid: str | int, name: str, sn: str | int,
                                         whether_sign: bool, whether_sign_manager: bool) -> bool:
        """
        异步写入活动报名人员信息.

        :return: Bool
        """
        db_path = path + '/temp.db'
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.cursor()
                await cursor.execute(
                    f"INSERT OR REPLACE INTO aid_{str(activity_id)}_member_info (UID, PID, NAME, SID_NUMBER, whetherSIGN, whetherSIGN_MANAGER) VALUES (?, ?, ?, ?, ?, ?)",
                    (uid, pid, name, sn, whether_sign, whether_sign_manager))
                await db.commit()
                await cursor.close()
                print(f"{name}写入成功")
                return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def read_activity_config_list(self, activity_id: str | int) -> list[tuple[str, str]]:
        """
        获取.

        :return: list[tuple[upConfig, Type]]
        """
        try:
            cursor = self.conn.cursor()
            return [i for i in cursor.execute(
                f"SELECT upConfig, Type FROM aid_{str(activity_id)}_upConfig_list ORDER BY id")]
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def fetch_upConfig_list(self, activity_id: str | int) -> list[str]:
        """
        获取配置.

        :return: list[upConfig]
        """
        try:
            cursor = self.conn.cursor()
            return [i[0] for i in cursor.execute(
                f"SELECT upConfig FROM aid_{str(activity_id)}_upConfig_list ORDER BY id").fetchall()]
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def read_activity_upload_info(self, activity_id: str | int,
                                  *uids: str | int | list | tuple | set) -> dict | tuple | bool:
        """
        获取数据库的上传资料.

        :param activity_id: 活动id
        :param uids: 用户id
        :return: dict[UID: [all]]
        """
        try:
            cursor = self.conn.cursor()
            if len(uids) == 1 and not any(isinstance(uid, (list, tuple, set)) for uid in uids):
                return {i[0]: [*i[:5], *[loads(j) for j in i[5:]]] for i in cursor.execute(
                    f"SELECT * FROM aid_{str(activity_id)}_upload_info WHERE UID = {uids[0]}").fetchall()}
            elif len(uids) == 1 and all(isinstance(uid, (list, tuple, set)) for uid in uids):
                return {i[0]: [*[i[:5]], *[loads(j) for j in i[5:]]] for i in cursor.execute(
                    f"SELECT * FROM aid_{str(activity_id)}_upload_info WHERE UID IN {tuple(*uids[0])}").fetchall()}
            elif len(uids) > 1 and all(isinstance(uid, (list, tuple, set)) for uid in uids):
                for uid in uids:
                    return {i[0]: [*[i[:5]], *[loads(j) for j in i[5:]]] for i in cursor.execute(
                        f"SELECT * FROM aid_{str(activity_id)}_upload_info WHERE UID IN {tuple(*uid)}").fetchall()}
            elif not uids:
                column_names = [i[0] for i in self.read_activity_config_list(activity_id)][:3]
                return tuple(i for i in cursor.execute(
                    f"SELECT {', '.join(column_names)} FROM aid_{str(activity_id)}_upload_info").fetchall())
            else:
                print("参数错误, 请输入正确参数.")
                return False
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def fuzzy_search_signManager(self, activity_id: str | int, keyword: str) -> dict[str, list[str]] | bool:
        """
        模糊搜索人员

        :param activity_id: 活动id
        :param keyword: 输入
        :return: dict{UID: [NAME, whetherSIGN_MANAGER]}
        :rtype: dict{str: [str, bool]}
        """
        try:
            cursor = self.conn.cursor()
            query = f"SELECT UID, NAME, whetherSIGN_MANAGER FROM aid_{activity_id}_member_info WHERE NAME LIKE ?"
            results = cursor.execute(query, ('%' + keyword + '%',)).fetchall()
            cursor.close()
            return {item[0]: [item[1], bool(item[2])] for item in results}

        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def update_sign_manager_info(self, activity_id: str | int, uid: str | int, whetherSign_manager: bool) -> bool:
        """
        更新扫码员信息.

        :param activity_id: 活动id
        :param uid: 用户id
        :param whetherSign_manager: 是否为扫码员
        :return: Bool
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"UPDATE aid_{str(activity_id)}_member_info SET whetherSIGN_MANAGER = ? WHERE UID = ?",
                           (whetherSign_manager, uid))
            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def update_audit_info(self, activity_id: str | int, uid: str | int, sid: str | int, flag: bool, reason=None) -> bool:
        """
        更新审核信息.

        :param activity_id: 活动id
        :param uid: 用户id
        :param sid: 上传id
        :param flag: 是否通过
        :param reason: 驳回理由
        :return: Bool
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                f"INSERT OR REPLACE INTO aid_{str(activity_id)}_audit_info (UID, SID, ApprovalOrRejection, Reason) VALUES (?, ?, ?, ?)",
                (uid, sid, flag, reason))
            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def fetch_audit_info(self, activity_id: str | int, flag=False) -> dict[str, list[str]] | list | bool:
        """
        获取所有审核信息.
        姓名, 审核状态在dict[uid][2]中, 驳回理由在dict[uid][3]中

        :param flag: 是否返回全部数据还是仅仅返回已审核的数据, flag=True返回全部数据, flag=False返回已审核的数据
        :param activity_id: 活动id
        :return: dict[UID: [all]] | list | bool
        """
        try:
            cursor = self.conn.cursor()
            if flag:
                return {i[0]: i for i in cursor.execute(f"SELECT * FROM aid_{str(activity_id)}_audit_info").fetchall()}
            elif not flag:
                return cursor.execute(
                    f"SELECT * FROM aid_{str(activity_id)}_audit_info WHERE ApprovalOrRejection IS NOT NULL").fetchall()
            cursor.close()
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def del_pass_upload_info(self, activity_id: str | int, uids: list[str]) -> bool:
        """
        删除审核通过的人员.

        :param activity_id: 活动id
        :param uids: 用户id
        :return: Bool
        """
        uids = tuple(uids)
        try:
            cursor = self.conn.cursor()
            query = f"DELETE FROM aid_{str(activity_id)}_upload_info WHERE UID IN ({','.join(['?']*len(uids))})"
            cursor.execute(query, uids)
            query = f"DELETE FROM aid_{str(activity_id)}_audit_info WHERE UID IN ({','.join(['?']*len(uids))})"
            cursor.execute(query, uids)
            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def sync_data_to_audit_info(self, activity_id):
        """
        同步数据到审核表.

        :param activity_id: 活动id
        :return: None
        """
        try:
            cursor = self.conn.cursor()
            sql = f"""
            INSERT INTO aid_{str(activity_id)}_audit_info (UID, SID)
            SELECT UID, SID FROM aid_{str(activity_id)}_upload_info
            """
            cursor.execute(sql)
            self.conn.commit()
            cursor.close()
            print("数据同步成功")
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def fetch_config_index(self, activity_id: str | int, config="心得") -> list[tuple[int, str]]:
        """
        获取配置序号

        :param activity_id: 活动id
        :param config: 配置名
        :return: (row_num, upConfig)
        """
        try:
            cursor = self.conn.cursor()
            return cursor.execute(
                f"""SELECT row_num - 1 as row_num, upConfig FROM (SELECT id, upConfig, ROW_NUMBER() OVER (ORDER BY id) as row_num FROM aid_{str(activity_id)}_upConfig_list) 
        WHERE upConfig LIKE ?;""", ('%' + config + '%',)).fetchall()
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")

    def fetch_signManager(self, activity_id) -> list[tuple[str, str]] | bool:
        try:
            cursor = self.conn.cursor()
            # 执行SQL查询，找出whetherSIGN_MANAGER为True的人
            query = f"SELECT name, uid FROM aid_{activity_id}_member_info WHERE whetherSIGN_MANAGER = TRUE"
            results = cursor.execute(query).fetchall()
            cursor.close()
            return results
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def fetch_unSigned(self, activity_id: str | int) -> list | bool:
        """
        获取未签到的UID, PID.

        :param activity_id: 活动id
        :return: list[UID, PID]
        """
        try:
            cursor = self.conn.cursor()
            return [i for i in cursor.execute(
                f"SELECT UID, PID FROM aid_{str(activity_id)}_member_info WHERE whetherSIGN = FALSE").fetchall()]
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    async def write_passed_member_info(self, activity_id: str | int, lists: list) -> bool:
        """
        写入通过的人员信息.

        :param activity_id: 活动id
        :param lists: list[UID]
        :return: Bool
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.cursor()
                data_tuples = [(uid,) for uid in lists]
                await cursor.executemany(f"INSERT OR REPLACE INTO aid_{str(activity_id)}_pass_info (UID) VALUES (?)",
                                   data_tuples)
                await db.commit()
                await cursor.close()
                return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def de_wight(self, activity_id: str | int) -> [(int, int)]:
        """
        去重, 获取未上交心得的人.

        :param activity_id: 活动id
        :return: list[(UID,PID)]
        """
        cursor = self.conn.cursor()
        query = f'''
                SELECT aid_{str(activity_id)}_member_info.UID 
                FROM aid_{str(activity_id)}_member_info
                WHERE NOT EXISTS (
                    SELECT 1 
                    FROM aid_{str(activity_id)}_pass_info 
                    WHERE aid_{str(activity_id)}_pass_info.UID = aid_{str(activity_id)}_member_info.UID
                );'''
        results = [item[0] for item in cursor.execute(query).fetchall()]
        query = f'''
                SELECT UID, PID FROM aid_{str(activity_id)}_member_info where UID in ({','.join(['?']*len(results))})
                '''
        uid_pid_pairs = cursor.execute(query, tuple(results)).fetchall()
        return uid_pid_pairs

    def find_name_sn_by_uid(self, activity_id, uid_list):
        """
        通过uid查找名字和学号

        """
        if not isinstance(uid_list, (list, tuple, set)):
            uid_list = [uid_list]
        try:
            cursor = self.conn.cursor()
            query = f"SELECT NAME, SID_NUMBER FROM aid_{activity_id}_member_info WHERE UID IN ({','.join(['?']*len(uid_list))})"
            results = cursor.execute(query, tuple(uid_list)).fetchall()
            return results
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return None

    def clean_id_and_drop_aids(self):
        """
        为返回上一级做准备.

        :return:
        """
        try:
            cursor = self.conn.cursor()
            self.del_var("activity_id")
            self.del_var("all_passed")
            self.del_var("activity_is_finished")
            # 查询所有特定开头的表名
            tables = cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'aid%'").fetchall()

            # 遍历这些表名，对每个表执行DROP TABLE命令
            for table in tables:
                cursor.execute(f"DROP TABLE {table[0]}")

            self.conn.commit()
            cursor.close()
            print("已清空")
            return True
        except sqlite3.Error as e:
            print(f"{my_function_name()}函数出错: {e}")
            return False

    def cls(self):
        if hasattr(self, 'conn'):
            self.conn.close()


SQL_operate = DatabaseManager()
