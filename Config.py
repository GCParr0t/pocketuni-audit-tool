# -*- coding: utf-8 -*-
# File: 
# Author: GCPAT
# Date: 2023/12/
# Description: 
# Tool: PyCharm
# Python: 3.11.0
import tempfile
import uuid
import os
import glob
import sys
from datetime import datetime
from time import sleep

import psutil
import logging

random_uuid = uuid.uuid4()
random_uuids = [random_uuid]
# 获取系统临时文件夹路径
temp_dir = tempfile.gettempdir()
path = temp_dir+f"\\{random_uuids[0]}"
os.makedirs(path, exist_ok=True)

# credentials文件路径
credentials_dir = f"{temp_dir}\\credentials"
os.makedirs(credentials_dir, exist_ok=True)
credentials_file = f"{temp_dir}\\credentials\\credentials.json"

csv_dir = os.path.abspath(".\\csv名单")
os.makedirs(csv_dir, exist_ok=True)

# 日志文件的路径
log_file_dir = os.path.abspath(".\\Logs")
os.makedirs(log_file_dir, exist_ok=True)
log_file = f"{log_file_dir}\\{datetime.now().strftime('%m月%d日 %H点%M分')}-Audit.log"

# 配置日志
logging.basicConfig(filename=log_file, filemode='a', format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# 使用日志
# logging.debug('这是一条debug级别的日志')
logging.info('这是一条info级别的日志')
logging.warning('这是一条warning级别的日志')
logging.error('这是一条error级别的日志')
logging.critical('这是一条critical级别的日志')

sleep(2)

# 锁文件的路径
lock_file = f"{path}/Pocket uni Audit APP.lock"
lock_files = glob.glob(f"{temp_dir}\\**\\Pocket uni Audit APP.lock", recursive=True)
lock_file_dirs = [os.path.dirname(lock_file) for lock_file in lock_files]


if lock_files:
    for lock_file in lock_files:
        with open(lock_file, 'r') as file:
            pid = int(file.read())
        if psutil.pid_exists(pid):
            # 向日志文件写入信息
            logging.error(f"程序已经在运行: {pid}")
            sys.exit(1)

# 创建或更新锁文件
with open(lock_file, 'w') as file:
    file.write(str(os.getpid()))


