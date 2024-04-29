import atexit
import io
import json
import os
import re
import shutil
import uuid
from base64 import b64decode
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import win32com.client as win32
from PyPDF2 import PdfFileReader
from PyQt5 import QtGui
from PyQt5.QtCore import QPoint, QThread, pyqtSignal, QRegExp
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QImage, QFont, QFontMetrics, QRegExpValidator, QCursor
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QLabel, QApplication, QListWidget, QListWidgetItem, QAbstractItemView, QTextEdit, \
    QTableWidgetItem, QToolTip, QSplitter, QButtonGroup, QRadioButton, QCheckBox, QGridLayout
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QSpacerItem, \
    QSizePolicy
from cryptography.fernet import Fernet
from docx import Document

from Config import random_uuids, path, lock_file_dirs, credentials_file, csv_dir
from Module.Fetch_page_and_cache import AuditProcessingThread, ManagerProcessingThread, DeleteProcessingThread

random_uuid = random_uuids[0]


def set_icon(win: QWidget, ico: str):
    ico_data = b64decode(ico)
    icon = QIcon()
    icon.addPixmap(
        QPixmap.fromImage(
            QImage.fromData(ico_data)),
        QIcon.Normal,
        QIcon.Off)
    win.setWindowIcon(icon)


class AutoClosingMessage(QLabel):
    def __init__(self, parent, message, timeout=1000, wait=10):
        super().__init__(parent)
        QToolTip.setFont(QFont("Times New Roman", 22))  # 提示信息的字体与字号大小
        rect = self.rect()

        if parent:
            tooltip_width = self.get_tooltip_width(message)

            x = int(self.parent().rect().center().x() - tooltip_width / 2)

            QTimer.singleShot(int(wait), lambda: QToolTip.showText(self.mapToGlobal(QPoint(x, rect.top())), message))

            QTimer.singleShot(int(timeout+wait), self.close_message)

            # 将此消息框对象存储为父窗口的一个属性，防止它在 timeout 时间内被垃圾回收
            parent.attribute = self
        else:
            QTimer.singleShot(int(wait), lambda: QToolTip.showText(QCursor.pos(), message))
            QTimer.singleShot(int(timeout + wait), self.close_message)

    @staticmethod
    def get_tooltip_width(msg: str) -> int:
        try:
            label = QLabel()
            label.setText(msg)
            label.setFont(QToolTip.font())
            fm = QFontMetrics(label.font())
            width = fm.width(msg) + 20
            return width
        except Exception as e:
            print(e)

    def close_message(self):
        self.close()


class DoubleClickButton(QPushButton):
    doubleClicked = pyqtSignal()

    def __init__(self, title, parent):
        super().__init__(title, parent)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()


class LoginWindow(QWidget):
    def __init__(self, name='pu审核小助手-江海大科协用; by GCPAT'):
        super().__init__()
        self.activity_window = None
        self.start_login_processing_thread = None
        self.msgBox = None
        self.attribute = None
        self.setWindowTitle(name)

        # 左上角图标
        set_icon(self, login_ico)

        self.text = QLabel('科协pu审核小助手', self)
        font = self.text.font()
        font.setPointSize(15)
        font.setBold(True)
        font.setFamily('微软雅黑')

        palette = self.text.palette()
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("orange"))
        self.text.setPalette(palette)
        self.text.setFont(font)

        self.text.setAlignment(Qt.AlignCenter)

        self.username_label = QLabel('用户名:', self)
        self.password_label = QLabel('密  码:', self)

        self.username_label.setFixedWidth(self.password_label.sizeHint().width())

        self.username_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.username_input.setPlaceholderText('请输入用户名')
        self.password_input.setPlaceholderText('请输入密码')

        reg_ex = QRegExp("[0-9]*")
        input_validator = QRegExpValidator(reg_ex, self.username_input)
        self.username_input.setValidator(input_validator)

        self.username_input.setMaxLength(10)  # 限制为10个字符
        self.password_input.setMaxLength(30)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.remember_checkbox_layout = QHBoxLayout()
        self.remember_checkbox_layout.setAlignment(Qt.AlignRight)
        self.remember_checkbox = QCheckBox('记住我', self)
        self.remember_checkbox_layout.addWidget(self.remember_checkbox)
        self.login_button = QPushButton('登录', self)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(self.username_label, 0, 0)
        self.grid.addWidget(self.password_label, 1, 0)
        self.grid.addWidget(self.username_input, 0, 1)
        self.grid.addWidget(self.password_input, 1, 1)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.text)
        self.layout.addLayout(self.grid)
        self.layout.addLayout(self.remember_checkbox_layout)
        self.layout.addWidget(self.login_button)

        self.login_button.clicked.connect(self.handle_login)
        self.login_button.clicked.connect(lambda: self.login_button.setEnabled(False))

        self.load_credentials()

    class StartLoginProcessingThread(QThread):
        def __init__(self, username, password, parent=None):
            QThread.__init__(self)
            self.activity_window = None
            self.msgBox = None
            self.attribute = None
            self.parent = parent
            self.username = username
            self.password = password
            self.flag = False

        def run(self):
            if Module.Fetch_html_element.login(self.username, self.password):
                Module.Fetch_html_element.fetch_and_storage_ActivityList()
                self.finished.emit()
            else:
                self.msgBox = AutoClosingMessage(self, '账号或密码错误!', 2000)
                self.msgBox.show()
                self.parent.login_button.setEnabled(True)

    def hideEvent(self, a0):
        self.activity_window = ActivityWindow()
        self.activity_window.show()

    def handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        self.msgBox = AutoClosingMessage(self, '正在登陆中', 2000)
        self.msgBox.show()
        if self.remember_checkbox.isChecked():
            self.save_credentials(username, password)
        else:
            self.clear_credentials()
        self.start_login_processing_thread = self.StartLoginProcessingThread(parent=self, username=username, password=password)
        self.start_login_processing_thread.finished.connect(self.hide)
        self.start_login_processing_thread.start()

    @staticmethod
    def save_credentials(username, password):
        # 生成一个用于加密和解密的密钥
        key = Fernet.generate_key()
        cipher_suite = Fernet(key)

        # 加密密码
        encrypted_password = cipher_suite.encrypt(password.encode())

        # 将加密的密码和密钥保存到磁盘
        with open(credentials_file, 'w') as f:
            json.dump({'username': username,
                       'password': encrypted_password.decode(),
                       'key': key.decode()},
                      f)

    def load_credentials(self):
        try:
            if os.path.exists(credentials_file):
                with open(credentials_file, 'r') as f:
                    credentials = json.load(f)
                    cipher_suite = Fernet(credentials['key'].encode())

                    # 解密密码
                    decrypted_password = cipher_suite.decrypt(
                        credentials['password'].encode()).decode()

                    self.username_input.setText(credentials['username'])
                    self.password_input.setText(decrypted_password)
                    self.remember_checkbox.setChecked(True)
        except Exception as e:
            self.msgBox = AutoClosingMessage(self, f'无法加载凭据, 错误: {e}', 5000)
            self.clear_credentials()
            self.remember_checkbox.setChecked(False)

    @staticmethod
    def clear_credentials():
        if os.path.exists(credentials_file):
            os.remove(credentials_file)


class ActivityWindow(QWidget):
    def __init__(self, name='pu审核小助手-江海大科协用; by GCPAT'):
        super().__init__()
        self.start_manager_processing_thread = None
        self.start_processing_thread = None
        self.activity_name = None
        self.msgBox = None
        self.attribute = None
        self.setWindowTitle(name)

        # 左上角图标
        set_icon(self, select_ico)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.list_widget)

        self.audit_button = QPushButton('点我去审核', self)
        self.sign_manager_button = QPushButton('点我去设置签到员', self)
        self.set_member_button = QPushButton('点我去删除未签到/未交心得成员', self)
        # self.sign_manager_button.hide()
        # self.set_member_button.hide()

        # 设置按钮点击事件处理器
        self.audit_button.clicked.connect(lambda: self.handle_confirm(-1))
        self.sign_manager_button.clicked.connect(lambda: self.handle_confirm(0))
        self.set_member_button.clicked.connect(lambda: self.handle_confirm(1))

        # 创建一个水平布局并添加按钮
        self.all_button_layout = QVBoxLayout()
        self.H_button_layout = QHBoxLayout()
        self.button_layout = QHBoxLayout()
        self.H_button_layout.addWidget(self.audit_button)
        self.H_button_layout.addWidget(self.sign_manager_button)
        self.button_layout.addWidget(self.set_member_button)

        self.all_button_layout.addLayout(self.H_button_layout)

        self.all_button_layout.addItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Minimum))

        self.all_button_layout.addLayout(self.button_layout)

        self.layout.addLayout(self.all_button_layout)

        self.activities = [item[0] for item in SQL_operate.fetch_var("activity_name_and_url_list")]
        for activity in self.activities:
            item = QListWidgetItem(activity)
            self.list_widget.addItem(item)
            item.setSelected(False)

        # 创建一个定时器
        self.timer = QTimer(self)
        # 设置定时器超时时间为5分钟
        self.timer.setInterval(int(5 * 60 * 1000))  # 5 minutes in milliseconds
        # 连接定时器的超时信号到窗口的close槽函数
        self.timer.timeout.connect(self.close)
        # 启动定时器
        self.timer.start()
    ##############################

    def disable_buttons(self):
        # 关闭所有控件
        self.audit_button.setEnabled(False)
        self.sign_manager_button.setEnabled(False)
        self.set_member_button.setEnabled(False)
        self.list_widget.setEnabled(False)

    def open_audit_processing_window(self):
        self.start_processing_thread = self.StartAuditProcessingThread(self, self.activity_name)
        self.start_processing_thread.start()

    class StartAuditProcessingThread(QThread):
        def __init__(self, parent=None, activity_name=None):
            QThread.__init__(self)
            self.parent = parent
            self.activity_name = activity_name
            self.thread = None
            self.audit_window = None

        def run(self):
            # 创建并运行异步任务
            self.thread = AuditProcessingThread()
            self.thread.finished.connect(self.on_thread_finished)
            self.thread.start()

        def on_thread_finished(self):
            self.audit_window = AuditWindow(self.activity_name)
            self.audit_window.auto_reject()
            self.parent.close()
            self.audit_window.show()

    def open_sign_manager_window(self):
        self.start_manager_processing_thread = self.StartManagerProcessingThread(self, self.activity_name)
        self.start_manager_processing_thread.start()

    class StartManagerProcessingThread(QThread):
        def __init__(self, parent=None, activity_name=None):
            QThread.__init__(self)
            self.parent = parent
            self.activity_name = activity_name
            self.thread = None
            self.sign_manager_window = None

        def run(self):
            # 创建并运行异步任务
            self.thread = ManagerProcessingThread()
            self.thread.finished.connect(self.on_thread_finished)
            self.thread.start()

        def on_thread_finished(self):
            self.parent.close()
            self.sign_manager_window = HandleSignManagerWindow(self.activity_name)
            self.sign_manager_window.show()

    def open_delete_window(self):
        self.start_processing_thread = self.StartDeleteProcessingThread(self, self.activity_name)
        self.start_processing_thread.start()

    class StartDeleteProcessingThread(QThread):
        def __init__(self, parent=None, activity_name=None):
            QThread.__init__(self)
            self.parent = parent
            self.activity_name = activity_name
            self.thread = None
            self.delete_window = None

        def run(self):
            # 创建并运行异步任务
            self.thread = DeleteProcessingThread()
            self.thread.finished.connect(self.on_thread_finished)
            self.thread.start()

        def on_thread_finished(self):
            self.delete_window = DeleteWindow(self.activity_name)
            self.parent.close()
            self.delete_window.show()

    def handle_confirm(self, flag):
        current_item = self.list_widget.currentItem()
        if current_item.isSelected():
            self.msgBox = AutoClosingMessage(self, '正在处理中...', 10000)
            index = self.activities.index(current_item.text()) + 1
            Module.Fetch_html_element.Choose_Activity_AND_Get_URL_and_ID(
                index)
            self.activity_name = current_item.text()
            self.disable_buttons()
            if flag == -1:
                self.open_audit_processing_window()
            if flag == 0:
                self.open_sign_manager_window()
            if flag == 1:
                self.open_delete_window()
        else:
            self.msgBox = AutoClosingMessage(self, '请选择一个活动', 2000)
            self.msgBox.show()
            return


class HandleSignManagerWindow(QWidget):
    def __init__(self, activity_name, name='科协pu审核小助手-设置扫码员界面'):
        super().__init__()
        self.activity_window = None
        self.checkbox = None
        self.msgBox = None
        self.attribute = None
        self.activity_id = SQL_operate.fetch_var("activity_id")
        self.find_button_shortcut = find_button_shortcut
        self.set_button_shortcut = set_button_shortcut
        self.cancel_button_shortcut = cancel_button_shortcut
        self.activity_name = activity_name
        self.setWindowTitle(name)

        # 左上角图标
        set_icon(self, sign_manager_ico)

        self.layout = QVBoxLayout(self)

        # 创建一个新的 QLabel 用于显示活动名称
        self.activity_name_label = QLabel(self)
        self.layout.addWidget(self.activity_name_label)
        self.activity_name_label.setText(str(self.activity_name) + "-设置扫码员")

        # Create a new QPushButton for returning to the activity selection
        # screen
        self.return_button = QPushButton('返回活动选择界面', self)
        self.return_button.clicked.connect(lambda: previous_level(self))

        # Create a new QHBoxLayout to hold the activity_name_label and the
        # return_button
        self.activity_name_layout = QHBoxLayout()
        self.activity_name_layout.addWidget(self.activity_name_label)
        self.activity_name_layout.addWidget(self.return_button)

        # Add the new layout to the main layout
        self.layout.addLayout(self.activity_name_layout)

        self.table = QTableWidget()

        # 修改表格的属性
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["姓名"])

        # 获取表头对象
        header = self.table.horizontalHeader()

        # 设置最后一列占满剩余空间
        header.setStretchLastSection(True)

        self.layout.addWidget(self.table)

        self.search_layout = QHBoxLayout()
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("输入姓名搜索,可模糊搜索")
        self.search_button = QPushButton(f'搜索', self)
        self.search_button.clicked.connect(
            lambda: self.search(self.activity_id))
        self.search_box.returnPressed.connect(
            lambda: self.search(self.activity_id))
        self.search_layout.addWidget(self.search_box)
        self.search_layout.addWidget(self.search_button)

        self.button_layout = QHBoxLayout()
        self.find_button = QPushButton(
            f'查找已设置扫码员({self.find_button_shortcut})', self)
        self.find_button.setShortcut(self.find_button_shortcut)
        self.find_button.clicked.connect(
            lambda: self.findSignManger(
                self.activity_id))
        self.set_button = QPushButton(
            f'设置扫码员({self.set_button_shortcut})', self)
        self.set_button.setShortcut(self.set_button_shortcut)
        self.set_button.clicked.connect(lambda: self.set(self.activity_id))
        self.cancel_button = QPushButton(
            f'取消扫码员({self.cancel_button_shortcut})', self)
        self.cancel_button.setShortcut(self.cancel_button_shortcut)
        self.cancel_button.clicked.connect(
            lambda: self.cancel(self.activity_id))
        self.button_layout.addWidget(self.find_button)
        self.button_layout.addItem(
            QSpacerItem(
                20,
                20,
                QSizePolicy.Expanding,
                QSizePolicy.Minimum))
        self.button_layout.addWidget(self.set_button)
        self.button_layout.addWidget(self.cancel_button)

        self.layout.addLayout(self.search_layout)
        self.layout.addWidget(self.table)
        self.layout.addLayout(self.button_layout)

        self.setLayout(self.layout)

    def search(self, activity_id):
        # 清空表格
        self.table.setRowCount(0)

        # 获取搜索关键词
        keyword = self.search_box.text()

        # 清除焦点
        self.search_box.clearFocus()

        if keyword == "":
            self.msgBox = AutoClosingMessage(self, '请输入搜索关键词', 2000)
            self.msgBox.show()
            return
        else:
            # 在数据库中进行模糊搜索
            results = SQL_operate.fuzzy_search_signManager(activity_id, keyword)

            # 将搜索结果显示在表格中
            for row_uid, row_data in results.items():
                row_position = self.table.rowCount()
                self.table.insertRow(row_position)
                item = QTableWidgetItem(row_data[0])
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, row_uid)
                if row_data[1]:
                    item.setForeground(QtGui.QBrush(QtGui.QColor("yellow")))
                    item.setBackground(QtGui.QBrush(QtGui.QColor("green")))
                self.table.setItem(row_position, 0, item)

    def findSignManger(self, activity_id):
        # 获取签到管理员的信息
        sign_managers = SQL_operate.fetch_signManager(activity_id)

        # 清空表格
        self.table.setRowCount(0)

        # 将每个签到管理员的名字添加为一个新的行
        for row_name, row_data in sign_managers:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            item = QTableWidgetItem(row_name)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setData(Qt.UserRole, row_data)
            self.table.setItem(row_position, 0, item)

    def set(self, activity_id):
        current_item = self.table.currentItem()
        if current_item is None:
            self.msgBox = AutoClosingMessage(
                self, '请选择后再点击', 2000)
            self.msgBox.show()
            return
        else:
            name = current_item.text()
            uid = current_item.data(Qt.UserRole)
            if Module.Action_Module.adminSetSignManagerAction(
                    activity_id, uid):
                # 更新数据库，设置该用户为签到员
                SQL_operate.update_sign_manager_info(activity_id, uid, True)
                # 修改颜色
                current_item.setForeground(QtGui.QBrush(QtGui.QColor("yellow")))
                current_item.setBackground(QtGui.QBrush(QtGui.QColor("green")))
                # 清除当前选择
                self.table.clearSelection()
                self.table.setCurrentItem(None)
                # 显示消息提示
                self.msgBox = AutoClosingMessage(self, f'{name} 扫码员设置成功', 2000)
                self.msgBox.show()
            else:
                self.msgBox = AutoClosingMessage(self, f'{name} 扫码员设置失败', 2000)
                self.msgBox.show()

    def cancel(self, activity_id):
        current_item = self.table.currentItem()
        if current_item is None:
            self.msgBox = AutoClosingMessage(
                self, '请选择后再点击', 2000)
            self.msgBox.show()
            return
        else:
            name = current_item.text()
            uid = current_item.data(Qt.UserRole)
            if Module.Action_Module.adminCancelSignManagerAction(
                    activity_id, uid):
                # 更新数据库，取消该用户的签到员设置
                SQL_operate.update_sign_manager_info(activity_id, uid, False)
                # 设置颜色
                current_item.setForeground(QtGui.QBrush())
                current_item.setBackground(QtGui.QBrush())
                # 清除当前选择
                self.table.clearSelection()
                self.table.setCurrentItem(None)
                # 显示消息提示
                self.msgBox = AutoClosingMessage(self, f'{name} 扫码员取消成功', 2000)
                self.msgBox.show()
            else:
                self.msgBox = AutoClosingMessage(self, f'{name} 扫码员取消失败', 2000)
                self.msgBox.show()


class AuditWindow(QWidget):
    def __init__(self, activity_name, name='科协pu审核小助手-审核界面'):
        super().__init__()
        self.old_item = None
        self.delete_unsigned_button = None
        self.void = None
        self.last_button_clicked = None
        self.activity_window = None
        self.msgBox = None
        self.attribute = None
        self.activity_name = activity_name
        # 按钮的快捷映射
        self.previous_button_shortcut = previous_button_shortcut
        self.accept_button_shortcut = accept_button_shortcut
        self.reject_button_shortcut = reject_button_shortcut
        self.next_button_shortcut = next_button_shortcut
        self.activity_id = SQL_operate.fetch_var("activity_id")
        self.setWindowTitle(name)

        # 左上角图标
        set_icon(self, audit_ico)

        self.layout = QVBoxLayout(self)

        # 创建一个新的 QLabel 用于显示活动名称
        self.activity_name_label = QLabel(self)
        self.layout.addWidget(self.activity_name_label)
        self.activity_name_label.setText(str(self.activity_name) + "-审核界面")

        # 创建一个新的 QPushButton 用于返回活动选择界面
        self.return_button = QPushButton('返回活动选择界面(注意! 会丢失所有未提交的内容!)', self)
        self.return_button.clicked.connect(lambda: previous_level(self))

        # 创建一个新的 QHBoxLayout 用于放置活动名称标签和返回按钮, 将活动名称标签和返回按钮添加到新的布局中
        self.activity_name_layout = QHBoxLayout()
        self.activity_name_layout.addWidget(self.activity_name_label)
        self.activity_name_layout.addWidget(self.return_button)

        # 创建外部水平 QSplitter 对象
        self.splitter = QSplitter(Qt.Horizontal)
        # 创建内部水平 QSplitter 对象
        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        # 创建一个新的垂直 QSplitter 对象
        self.vertical_splitter = QSplitter(Qt.Vertical)

        # 将 middle_widget 和 right_widget 添加到水平的 QSplitter 中
        self.middle_widget = QWidget(self.horizontal_splitter)
        self.right_widget = QWidget(self.horizontal_splitter)

        # 将 horizontal_splitter 和 bottom_widget 添加到垂直的 QSplitter 中
        self.horizontal_splitter.setParent(self.vertical_splitter)
        self.bottom_widget = QWidget(self.vertical_splitter)

        # 将 vertical_splitter 添加到外部水平 QSplitter 中
        self.left_widget = QWidget(self.splitter)
        self.vertical_splitter.setParent(self.splitter)

        # 设置 QSplitter 的子部件的大小
        self.splitter.setSizes([1, 4])
        # 设置 QSplitter 的子部件的大小
        self.vertical_splitter.setSizes([4, 1])

        # 将新的布局添加到主布局中
        self.layout.addLayout(self.activity_name_layout)
        self.layout.addWidget(self.splitter)
        ##############################
        # 以下是设置四个区的代码

        # 为 self.left_widget 添加一个 QVBoxLayout
        self.left_layout = QVBoxLayout(self.left_widget)

        # 创建一个新的 QPushButton 对象
        self.submit_button = DoubleClickButton("(双击)提交审核", self.left_widget)

        # 创建一个新的 QListWidget
        self.list_widget = QListWidget(self)

        # 将按钮加入到布局中
        self.left_layout.addWidget(self.submit_button)

        # 添加空白
        self.left_layout.addItem(QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # 将列表部件添加到 left_widget_layout 中
        self.left_layout.addWidget(self.list_widget)

        # 将 left_layout 设置为 self.left_widget 的布局
        self.left_widget.setLayout(self.left_layout)
        
        self.row_changed = False  # 添加新的属性
        self.list_widget.currentRowChanged.connect(self.handle_row_changed)
        self.list_widget.currentRowChanged.connect(lambda _: self.adjustSize)
        #######################################
        # 为 self.middle_widget 添加一个 QVBoxLayout
        self.middle_layout = QVBoxLayout(self.middle_widget)
        self.text_middle_wordage = QLabel(self.middle_widget)
        self.text_middle_wordage.setWordWrap(True)
        # 设置text_middle_wordage的字体
        font = self.text_middle_wordage.font()
        font.setPointSize(20)  # 设置字号
        font.setBold(True)  # 设置字体为粗体
        self.text_middle_wordage.setFont(font)
        # 创建一个按钮组与QLineEdit
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(False)
        self.default_reject_reasons = [
            "本人照片请不要随便截个帅照就交！没有电子照吗？",
            "心得不要交你的帅照!交心得!",
            "交网图/动漫图是啥意思?以为审核不看是吧?",
            "这交的什么照片心得?和这次活动沾边吗?以为审核不看是吧?",
            "本人照片和你活动照片里的人是同一个人?以为审核不看是吧?",
            "活动照片和活动心得你愣是一个没交对!乱交!以为审核不看是吧?",
            "心得不要交乱七八糟的格式! 尽量交docx格式!"
                                      ]

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("请输入更多的驳回理由,同时可以通过快捷键选择选项一并提交")
        self.line_edit.returnPressed.connect(self.reject_and_move_forward)
        ########################################

        # 为 self.right_widget 添加一个 QVBoxLayout
        self.right_layout = QVBoxLayout(self.right_widget)

        ########################################

        config_list = SQL_operate.read_activity_config_list(self.activity_id)
        self.middle_config_list, self.right_config_list = [item[0] for item in config_list[2:6]], [item[0] for item in config_list[6:]]

        self.widget_list = []

        ########################################
        # 创建按钮
        self.previous_button = QPushButton(
            f"上一个({self.previous_button_shortcut})",
            self.bottom_widget)
        self.accept_button = QPushButton(
            f"通过({self.accept_button_shortcut})",
            self.bottom_widget)
        self.reject_button = QPushButton(
            f"驳回({self.reject_button_shortcut})",
            self.bottom_widget)
        self.next_button = QPushButton(
            f"下一个({self.next_button_shortcut})",
            self.bottom_widget)

        # 设置按钮的快捷键
        self.previous_button.setShortcut(f"{self.previous_button_shortcut}")
        self.accept_button.setShortcut(f"{self.accept_button_shortcut}")
        self.reject_button.setShortcut(f"{self.reject_button_shortcut}")
        self.next_button.setShortcut(f"{self.next_button_shortcut}")

        # 创建一个新的 QHBoxLayout 对象
        bottom_layout = QHBoxLayout(self.bottom_widget)

        # 将按钮添加到布局中
        bottom_layout.addWidget(self.previous_button)
        bottom_layout.addWidget(self.accept_button)
        bottom_layout.addWidget(self.reject_button)
        bottom_layout.addWidget(self.next_button)

        # 将布局设置为 self.bottom_widget 的布局
        self.bottom_widget.setLayout(bottom_layout)

        # 将 self.bottom_widget 添加到 self.vertical_splitter 中
        self.vertical_splitter.addWidget(self.bottom_widget)

        self.previous_button.clicked.connect(self.move_pointer_backward)
        self.accept_button.clicked.connect(self.accept_and_move_forward)
        self.reject_button.clicked.connect(self.reject_and_move_forward)
        self.next_button.clicked.connect(self.move_pointer_forward)
        self.submit_button.doubleClicked.connect(self.submit_and_alignment)

        self.setLayout(self.layout)

        self.pointer = 0
        self.data_list = SQL_operate.read_activity_upload_info(self.activity_id)

    def auto_reject(self):
        flag = False
        for uid, sid, _ in self.data_list:
            error_list = []
            for config in self.right_config_list:
                _, _, wordage, error_reason = self.load_data(uid, config)
                if error_reason is not None:
                    error_list.append(" 你提交的" + config + "发生错误: " + error_reason)
                if wordage is not None and wordage < 200:
                    flag = True
            if flag:
                reason = "驳回原因: 心得字数不足200字, 且" + "; ".join(error_list)
                SQL_operate.update_audit_info(self.activity_id, uid, sid, False, reason)
                flag = False
        self.update_list_widget()
        if not self.data_list:
            self.load_info(None)

    def load_info(self, uid):
        if uid is not None:
            self.text_middle_wordage.clear()
            # 清除button_group的选择
            for button in self.button_group.buttons():
                # 从布局中移除按钮
                self.middle_layout.removeWidget(button)
            # 清除驳回原因文本框的内容
            self.line_edit.clear()
            # 清除焦点
            self.line_edit.clearFocus()
            # 清空 self.widget_list
            for widget in self.widget_list:
                # 从布局中移除widget
                self.middle_layout.removeWidget(widget)
                self.right_layout.removeWidget(widget)
                del widget
            self.widget_list.clear()

            # 初始化驳回原因列表
            error_list = []
            # 从数据库获取数据,并自适应加载内容
            ########################################
            # 自适应加载中部内容
            # 设置字数统计的字体
            text_list = []
            for config in self.middle_config_list:
                info = self.load_data(uid, config)
                file_type, file_data, _, error_reason = info
                if file_type == 0 or file_type == 7:
                    self.load_content(file_type, file_data, self.middle_widget, self.middle_layout)
                else:
                    text_list.append((config, info))

                if error_reason is not None:
                    error_list.append(" 你提交的" + config + "发生错误: " + error_reason)
            for config, info in text_list:
                self.load_content(info[0], config + ": " + info[1], self.middle_widget, self.middle_layout)

            self.middle_layout.addWidget(self.text_middle_wordage)

            for index, reason in enumerate(self.default_reject_reasons):
                # 为每个原因创建一个新的QWidget作为容器部件和QHBoxLayout
                container_widget = QWidget()
                h_box = QHBoxLayout(container_widget)  # 将container_widget作为h_box的父部件

                radio_button = QRadioButton(reason)
                radio_button.setShortcut(QKeySequence(default_keyshortcuts[index]))
                self.button_group.addButton(radio_button)

                h_box.addWidget(radio_button)

                # 创建用于显示括号的 QLabel
                bracket_label = QLabel("(")
                # 创建用于显示加粗文本的 QLabel
                bold_text_label = QLabel(default_keyshortcuts[index])
                bold_text_label.setFont(QFont("", 10, QFont.Bold))  # 设置字体加粗
                bold_text_label.setStyleSheet("color: orange")    # 设置字体为橙色

                # 创建用于显示闭合括号的 QLabel
                closing_bracket_label = QLabel(")")

                # 创建一个 QWidget 作为容器，并设置水平布局
                inner_container_widget = QWidget()
                horizontal_layout = QHBoxLayout(inner_container_widget)
                horizontal_layout.addWidget(bracket_label)
                horizontal_layout.addWidget(bold_text_label)
                horizontal_layout.addWidget(closing_bracket_label)
                horizontal_layout.setContentsMargins(0, 0, 0, 0)  # 移除布局边距，确保括号和文本紧挨在一起
                horizontal_layout.setSpacing(0)  # 移除标签之间的间距

                # 设置容器部件的对齐方式为右对齐和垂直居中
                horizontal_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                h_box.addWidget(inner_container_widget)

                self.middle_layout.addWidget(container_widget)

                self.widget_list.append(radio_button)
                self.widget_list.append(bracket_label)
                self.widget_list.append(bold_text_label)
                self.widget_list.append(closing_bracket_label)
                self.widget_list.append(inner_container_widget)
                self.widget_list.append(container_widget)

            self.middle_layout.addWidget(self.line_edit)

            self.middle_widget.setLayout(self.middle_layout)
            self.right_widget.setLayout(self.right_layout)
            ########################################
            # 自适应加载右侧内容
            for config in self.right_config_list:
                file_type, file_data, wordage, error_reason = self.load_data(uid, config)
                self.load_content(file_type, file_data, self.right_widget, self.right_layout)

                if error_reason is not None:
                    error_list.append(" 你提交的" + config + "发生错误: " + error_reason)

                if "心得" in config:
                    palette = self.text_middle_wordage.palette()
                    if wordage is not None:
                        self.text_middle_wordage.setText("心得字数统计: " + str(wordage) + "字")
                        if wordage < 200:
                            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('red'))  # 如果wordage小于200则标红
                        else:
                            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('green'))  # 如果wordage大于等于200则标绿
                    else:
                        self.text_middle_wordage.setText("文件不是.doc/.docx类型, 无法统计心得字数")
                        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#FFA500'))  # 如果无法统计心得字数，则设置字体颜色为橙色
                    self.text_middle_wordage.setPalette(palette)

            # 将error_list添加到list_widget的隐藏属性中
            self.list_widget.setProperty("error_list", error_list)

            self.adjustSize()
        else:
            # 清空所有控件
            self.splitter.deleteLater()
            self.horizontal_splitter.deleteLater()
            self.vertical_splitter.deleteLater()
            # 放置一个新的 QLabel 用于显示“没有待审核的内容”
            self.void = QLabel(self)
            font = self.void.font()
            font.setPointSize(30)
            font.setBold(True)
            self.void.setFont(font)
            self.void.setText('没有待审核的内容')
            self.void.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(self.void)
            # 设置窗口大小不可更改
            self.setFixedSize(self.size())

    def move_pointer_backward(self):
        if not self.row_changed:
            self.previous_button.setEnabled(False)
            if self.pointer > 0:
                self.pointer -= 1
                self.list_widget.setCurrentRow(self.pointer)
            self.previous_button.setEnabled(True)
            self.last_button_clicked = 'previous'  # 更新最后一次点击的按钮

    def move_pointer_forward(self):
        if not self.row_changed:
            self.next_button.setEnabled(False)
            if self.pointer < len(self.data_list) - 1:
                self.pointer += 1
                self.list_widget.setCurrentRow(self.pointer)
            self.next_button.setEnabled(True)
            self.last_button_clicked = 'next'  # 更新最后一次点击的按钮

    def accept_and_move_forward(self):
        if not self.row_changed:
            self.accept_button.setEnabled(False)
            uid, sid, name = self.data_list[self.pointer]
            # 写入数据库
            if SQL_operate.update_audit_info(self.activity_id, uid, sid, True):
                self.msgBox = AutoClosingMessage(self, f"{name} 已添加至待通过队列!", 1000)
                self.msgBox.show()
                # 移动指针
                if self.pointer < len(self.data_list) - 1:
                    self.pointer += 1
                    self.list_widget.setCurrentRow(self.pointer)
                else:
                    self.list_widget.setCurrentRow(self.pointer)
                    self.update_list_widget()
            else:
                self.msgBox = AutoClosingMessage(self, f"{name} 添加至待通过队列失败!", 1000)
                self.msgBox.show()
            self.accept_button.setEnabled(True)
            self.last_button_clicked = 'accept'  # 更新最后一次点击的按钮

    def reject_and_move_forward(self):
        if not self.row_changed:
            self.reject_button.setEnabled(False)
            # 按钮, 文本框, 隐藏属性
            checked_list = [button.text() for button in self.button_group.buttons() if button.isChecked()]
            if self.line_edit.text():
                reject_reason = "驳回原因: " + self.line_edit.text() + "; " + "; ".join(checked_list) + "; ".join(self.list_widget.property("error_list"))
            else:
                reject_reason = "驳回原因: " + "; ".join(checked_list) + "; ".join(self.list_widget.property("error_list"))
            uid, sid, name = self.data_list[self.pointer]
            # 写入数据库
            if SQL_operate.update_audit_info(
                    self.activity_id, uid, sid, False, reject_reason):
                self.msgBox = AutoClosingMessage(self, f"{name} 已添加至待驳回队列!", 1000)
                self.msgBox.show()
                # 移动指针
                if self.pointer < len(self.data_list) - 1:
                    self.pointer += 1
                    self.list_widget.setCurrentRow(self.pointer)
                else:
                    self.list_widget.setCurrentRow(self.pointer)
                    self.update_list_widget()
            else:
                self.msgBox = AutoClosingMessage(self, f"{name} 添加至待驳回队列失败!", 1000)
                self.msgBox.show()
            self.reject_button.setEnabled(True)
            self.last_button_clicked = 'reject'  # 更新最后一次点击的按钮

    def handle_row_changed(self, current_row):
        if not self.row_changed:
            self.row_changed = True  # 当列表的当前行改变时，将self.row_changed设置为True
            # 获取当前行的QListWidgetItem
            if self.old_item is not None:
                self.old_item.setBackground(QtGui.QBrush())
            self.old_item = item = self.list_widget.item(current_row)
            if item is not None:
                # 从项目中获取UID和SID
                uid, sid = item.data(Qt.UserRole)
                # 更新指针位置
                self.pointer = current_row
                # 加载信息
                self.load_info(uid)
                self.update_buttons()
                self.update_list_widget()
                item.setBackground(QtGui.QBrush(QtGui.QColor("#87CEFA")))
            self.row_changed = False  # 在处理完列表行改变事件后，将self.row_changed设置回False

    def submit_and_alignment(self):
        self.submit_button.setEnabled(False)
        audit_info = SQL_operate.fetch_audit_info(self.activity_id, False)
        approved_uid_list = []
        approved_name_list = []
        rejected_uid_and_reason_list = []
        rejected_name_sn_reason_list = []
        for uid, sid, approval_or_rejection, reason in audit_info:
            if approval_or_rejection == 1:
                if Module.Action_Module.Audit(True, self.activity_id, sid):
                    approved_uid_list.append(uid)
                else:
                    self.msgBox = AutoClosingMessage(
                        self, f"{SQL_operate.find_name_sn_by_uid(self.activity_id, uid)[0][0]} 通过失败! 检查是否有人在审核! 请返回上一级菜单并重新下载!",
                        2000)
                    self.msgBox.show()
            elif approval_or_rejection == 0:
                if Module.Action_Module.Audit(False, self.activity_id, sid, reason):
                    rejected_uid_and_reason_list.append((uid, reason,))
                else:
                    self.msgBox = AutoClosingMessage(
                        self, f"{SQL_operate.find_name_sn_by_uid(self.activity_id, uid)[0][0]} 驳回失败! 检查是否有人在审核! 请返回上一级菜单并重新下载!",
                        2000)
                    self.msgBox.show()
        if approved_uid_list:
            for uid in approved_uid_list:
                approved_name_list.append(SQL_operate.find_name_sn_by_uid(self.activity_id, uid)[0][0])
            self.msgBox = AutoClosingMessage(
                self, f"{', '.join(approved_name_list)} 通过成功!", 2500)
            self.msgBox.show()
        if rejected_uid_and_reason_list:
            for uid, reason in rejected_uid_and_reason_list:
                rejected_name_sn_reason_list.append((*SQL_operate.find_name_sn_by_uid(self.activity_id, uid)[0], reason,))
            with open(os.path.join(os.path.abspath(csv_dir), f'{datetime.now().strftime("%m月%d日")}-{self.activity_name}-驳回名单_({str(uuid.uuid4())[:3]}).csv'), 'w') as f:
                f.write(f"{self.activity_name},\n")
                f.write('驳回名单,\n')
                f.write('姓名, 学号, 驳回原因,\n')
                # 遍历列表，将每个元素作为一个单独行写入csv文件
                for name, sn, reason in rejected_name_sn_reason_list:
                    # 确保name非空
                    if name:
                        sensitized_name = name[:-1] + '*'
                        f.write(f'{sensitized_name}, {sn}, {reason},\n')
                    else:
                        # 如果name为空，可以决定如何处理，例如写入原始空字符串或者一个占位符
                        f.write(f'(姓名为空), {sn}, {reason},\n')
            self.msgBox = AutoClosingMessage(
                self,
                f"{', '.join([item[0] for item in rejected_name_sn_reason_list])} 驳回成功! 驳回名单已存放至本目录下 驳回名单 中!",
                2500, 2500)
            self.msgBox.show()
        if not approved_uid_list and not rejected_uid_and_reason_list:
            self.msgBox = AutoClosingMessage(self, "没有需要提交的内容!", 2000)
            self.msgBox.show()
        passed_uid_list = approved_uid_list + [item[0] for item in rejected_uid_and_reason_list]
        SQL_operate.del_pass_upload_info(self.activity_id, passed_uid_list)
        self.data_list = ()
        self.data_list = SQL_operate.read_activity_upload_info(self.activity_id)
        self.pointer = 0
        self.list_widget.clear()
        self.submit_button.setEnabled(True)
        if not self.data_list:
            self.load_info(None)

    def load_content(self, data_type, data, target_widget, target_layout):
        """
        生成控件并加载文件数据
        """
        if data_type == -1 or data_type == -2 or data_type == -3:  # 未知文件类型
            # 判断文本长度, 如果超过16个字符就使用QTextEdit
            if len(data) >= 16:
                widget = QTextEdit(target_widget)
                widget.setReadOnly(True)
                widget.setPlainText(data)

                self.widget_list.append(widget)
                target_layout.addWidget(widget)
            else:
                widget = QLineEdit(target_widget)
                widget.setReadOnly(True)
                widget.setText(data)

                self.widget_list.append(widget)
                target_layout.addWidget(widget)
        elif data_type == 0:  # 图片
            widget = QLabel(target_widget)
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            original_size = pixmap.size()
            original_width = original_size.width()
            original_height = original_size.height()

            # 判断图片是横向还是纵向
            if original_width > original_height:
                # 横向图片，宽度设置为500像素
                scaled_pixmap = pixmap.scaledToWidth(500)
            else:
                # 纵向图片，宽度设置为200像素
                scaled_pixmap = pixmap.scaledToWidth(300)

            size = scaled_pixmap.size()
            widget.resize(size.width(), size.height())
            widget.setPixmap(scaled_pixmap)

            self.widget_list.append(widget)
            target_layout.addWidget(widget)
        elif data_type == 1:  # 文档
            widget = QTextEdit(target_widget)
            widget.setReadOnly(True)
            widget.setPlainText(data)

            self.widget_list.append(widget)
            target_layout.addWidget(widget)

        elif data_type == 6:  # 文字信息
            widget = QLabel(target_widget)
            widget.setText(data)
            widget.setWordWrap(True)
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            widget.setFont(font)

            self.widget_list.append(widget)
            target_layout.addWidget(widget)

        elif data_type == 7:  # 包含tuple[file_type, data, None, None]的列表
            for item in data:
                self.load_content(item[0], item[1], target_widget, target_layout)

    def load_data(self, uid, config, data=None):
        """
        file_type定义:
        -3: 文件下载错误或文件为空,需要将错误原因导入驳回列表
        -2:无法读取.doc/.docx文件,需要将错误原因导入驳回列表
        -1: 未知文件类型,交的乱七八糟,踢了
         0: 图片
         1: doc/docx文档
         2: pdf文件

         6: 文字信息
         7: 包含tuple[file_type, data, None]的列表

        :returns: 文件类型, 数据(或是包含数据的list), 字数, 驳回原因
        """
        if uid and config:
            file_row_num = SQL_operate.fetch_config_index(self.activity_id, config)[-1][0]
            data = [
                *
                SQL_operate.read_activity_upload_info(
                    self.activity_id,
                    uid).values()][0][file_row_num]
            # 读取文件
            if isinstance(data, str):
                return 6, data, None, None
            elif isinstance(data, list):
                # 如果数据是列表，遍历列表并加载每个元素
                data_list = []
                for item in data:
                    data_list.append(self.load_data(uid=None, config=None, data=item))
                return 7, data_list, None, None
            else:
                return self.load_data(uid=None, config=None, data=data)
        # 如果文件非空
        elif not uid and not config and data:
            # 如果是.docx文件
            if data.startswith(b'PK\x03\x04'):  # .docx文件的魔数
                try:
                    doc = Document(io.BytesIO(data))
                    paragraphs = doc.paragraphs
                    text = '\n'.join([paragraph.text for paragraph in paragraphs])
                    # 统计字符数
                    count = 0
                    for paragraph in paragraphs:
                        text_re = re.sub(r'[^\w\s]', '', paragraph.text)  # 移除标点符号
                        count += len(re.findall(r'\w', text_re))  # 统计字符
                        count -= len(re.findall(r'[A-Za-z]{2}', text))  # 两个英文字母视作一个字符
                    return 1, text, count, None
                except Exception as e:
                    return -2, f"无法读取.docx文件: {e}", None, f" 无法读取.docx文件: {e}"
            # 如果是.doc文件
            elif data.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'):  # .doc文件的魔数
                try:
                    temp_path = self.temp_file_handle(data, 'doc')

                    # 使用pywin32库读取.doc文件
                    word = win32.gencache.EnsureDispatch('Word.Application')
                    doc = word.Documents.Open(temp_path)
                    text = doc.Content.Text
                    doc.Close()
                    word.Quit()

                    count = self.count_wordage_and_del_temp_file(text, temp_path)
                    return 1, text, count, None
                except Exception as e:
                    return -2, f"无法读取.doc文件: {e}", None, f" (建议提交docx文件)无法读取.doc文件: {e}"
            # 如果是pdf文件
            elif data.startswith(b'%PDF-'):
                try:
                    temp_path = self.temp_file_handle(data, 'pdf')

                    # 使用PdfFileReader库读取pdf文件
                    pdf, text = PdfFileReader(temp_path), ''
                    for page in pdf.pages:
                        text += page.extract_text()

                    count = self.count_wordage_and_del_temp_file(text, temp_path)
                    return 1, text, count, None
                except Exception as e:
                    return -2, f"无法读取.pdf文件: {e}", None, f" 无法读取.pdf文件: {e}"
            # 如果文件是图片类型的
            elif data.startswith(b'\xFF\xD8\xFF') or data.startswith(
                    b'\x89\x50\x4E\x47') or data.startswith(b'\x47\x49\x46\x38') or data.startswith(b'\x42\x4D'):
                return 0, data, None, None
            else:
                return -1, "未知文件类型, 无法加载, 请手动查看", None, " 未知文件类型, 请提交JPEG/PNG/GIF/BMP类型图片, doc/docx/pdf文档"
        elif not uid and not config and not data:
            return -3, "文件下载错误或文件为空, 无法加载, 请手动查看", None, " 文件下载错误或文件为空, 请重新提交"

    @staticmethod
    def temp_file_handle(data, suffix):
        temp = NamedTemporaryFile(delete=False, suffix=f'.{suffix}', dir=path)
        temp_path = temp.name
        temp.write(data)
        temp.close()
        return temp_path

    @staticmethod
    def count_wordage_and_del_temp_file(text, temp_path):
        text_re = re.sub(r'[^\w\s]', '', text)  # 移除标点符号
        count = len(re.findall(r'\w', text_re))  # 统计字符
        count -= len(re.findall(r'[A-Za-z]{2}', text_re))  # 两个英文字母视作一个字符

        # 安全删除文件
        file_path = Path(temp_path)
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
        return count

    def update_buttons(self):
        # 当指针处于list头时隐藏“上一个”按钮
        self.previous_button.setVisible(self.pointer != 0)
        # 当指针在list尾时隐藏"下一个"按钮
        end_of_list = self.pointer == len(self.data_list) - 1
        self.next_button.setVisible(not end_of_list)

    def update_list_widget(self):
        if self.data_list:
            # 从数据库获取新的数据
            new_data = SQL_operate.fetch_audit_info(self.activity_id, True)

            # 检查列表是否已经有数据
            if self.list_widget.count() > 0:
                # 更新数据
                for i in range(self.list_widget.count()):
                    item = self.list_widget.item(i)
                    uid, sid = item.data(Qt.UserRole)
                    approval_status = new_data[uid][2]  # 获取ApprovalOrRejection字段
                    if approval_status == 1:
                        item.setForeground(QtGui.QBrush(QtGui.QColor("yellow")))
                        item.setBackground(QtGui.QBrush(QtGui.QColor("green")))
                    elif approval_status == 0:
                        item.setForeground(QtGui.QBrush(QtGui.QColor("white")))
                        item.setBackground(QtGui.QBrush(QtGui.QColor("red")))
                    elif approval_status is None:
                        item.setForeground(Qt.black)
            else:
                # 填充数据
                for uid, sid, NAME in self.data_list:
                    item = QListWidgetItem(NAME)
                    item.setData(Qt.UserRole, (uid, sid))
                    approval_status = new_data[uid][2]  # 获取ApprovalOrRejection字段
                    if approval_status == 1:
                        item.setForeground(QtGui.QBrush(QtGui.QColor("yellow")))
                        item.setBackground(QtGui.QBrush(QtGui.QColor("green")))
                    elif approval_status == 0:
                        item.setForeground(QtGui.QBrush(QtGui.QColor("yellow")))
                        item.setBackground(QtGui.QBrush(QtGui.QColor("green")))
                    elif approval_status is None:
                        pass
                    self.list_widget.addItem(item)
            # 高亮指针所指向的行
            self.list_widget.setCurrentRow(self.pointer)


class DeleteWindow(QWidget):
    def __init__(self, activity_name, name='科协pu审核小助手-删除界面'):
        super().__init__()
        self.activity_window = None
        self.msgBox = None
        self.attribute = None
        self.activity_name = activity_name
        self.activity_id = SQL_operate.fetch_var("activity_id")
        self.setWindowTitle(name)

        # 左上角图标
        set_icon(self, del_ico)

        self.layout = QVBoxLayout(self)

        # 创建一个新的 QLabel 用于显示活动名称
        self.activity_name_label = QLabel(self)
        self.activity_name_label.setText(str(self.activity_name) + "-删除界面")
        # 创建一个新的 QPushButton 用于返回活动选择界面
        self.return_button = QPushButton('返回活动选择界面', self)
        self.return_button.clicked.connect(lambda: previous_level(self))

        # 创建一个新的 QHBoxLayout 用于放置活动名称标签和返回按钮, 将活动名称标签和返回按钮添加到新的布局中
        self.activity_name_layout = QHBoxLayout()
        self.activity_name_layout.addWidget(self.activity_name_label)
        self.activity_name_layout.addWidget(self.return_button)

        self.layout.addLayout(self.activity_name_layout)

        self.delVbox = QVBoxLayout()
        # 添加空白
        self.delVbox.addItem(QSpacerItem(10, 30, QSizePolicy.Minimum, QSizePolicy.Minimum))

        self.delete_unsigned_button = QPushButton('删除未签到成员', self)
        self.delete_unsigned_button.clicked.connect(
            lambda: Module.Action_Module.delMember(True, self.activity_name, self.activity_id, datetime.now().strftime("%m月%d日"), str(uuid.uuid4())[:3]))
        self.delete_unsigned_button.clicked.connect(lambda: self.delete_unsigned_button.setEnabled(False))
        self.delVbox.addWidget(self.delete_unsigned_button)

        all_passed = SQL_operate.fetch_var("all_passed")
        activity_is_finished = SQL_operate.fetch_var("activity_is_finished")
        if all_passed and activity_is_finished:
            self.delVbox.addItem(QSpacerItem(10, 20, QSizePolicy.Minimum, QSizePolicy.Minimum))

            self.delete_un_upload_member_button = QPushButton('删除未提交心得成员', self)
            self.delete_un_upload_member_button.clicked.connect(
                lambda: Module.Action_Module.delMember(False, self.activity_name, self.activity_id, datetime.now().strftime("%m月%d日"), str(uuid.uuid4())[:3]))
            self.delete_un_upload_member_button.clicked.connect(lambda: self.delete_un_upload_member_button.setEnabled(False))
            self.delVbox.addWidget(self.delete_un_upload_member_button)

        self.layout.addLayout(self.delVbox)


def previous_level(parent):
    SQL_operate.clean_id_and_drop_aids()
    parent.close()
    parent.activity_window = ActivityWindow()
    parent.activity_window.show()


def delete_temp() -> None:
    """
    删除临时文件

    :return:
    """
    SQL_operate.cls()
    if os.path.exists(path):
        shutil.rmtree(path)
    for lock_file_dir in lock_file_dirs:
        if os.path.exists(lock_file_dir):
            shutil.rmtree(lock_file_dir)


if __name__ == '__main__':
    # 创建按钮的快捷映射
    # 扫码员设置界面
    find_button_shortcut = 'F'
    set_button_shortcut = 'S'
    cancel_button_shortcut = 'Z'
    # 审核界面
    previous_button_shortcut = 'A'
    accept_button_shortcut = 'S'
    reject_button_shortcut = 'D'
    next_button_shortcut = 'F'
    default_keyshortcuts = ["Z", "X", "C", "V", "B", "N", "M"]
    # 在这里导入 Module
    from Module.SQL_operate import SQL_operate
    import Module

    login_ico = de_wight_ico = del_ico = Module.Icon_module.login_ico
    select_ico = Module.Icon_module.select_ico
    processing_ico = Module.Icon_module.process_ico
    audit_ico = sign_manager_ico = Module.Icon_module.audit_ico

    app = QApplication([])
    window = LoginWindow()
    window.show()
    atexit.register(delete_temp)
    app.exec_()
