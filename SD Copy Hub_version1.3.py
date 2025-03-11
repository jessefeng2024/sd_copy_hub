
import os
import datetime
import shutil
import hashlib
import logging
from PIL import Image
from PIL.ExifTags import TAGS
import configparser
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QProgressBar
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QThread, pyqtSignal

# 配置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 获取用户图片和视频文件夹路径
def get_user_pictures_folder():
    if os.name == 'nt':  # Windows 系统
        return os.path.join(os.environ['USERPROFILE'], 'Pictures')
    elif os.name == 'posix':  # macOS 或 Linux 系统
        return os.path.join(str(Path.home()), 'Pictures')
    return None

def get_user_videos_folder():
    if os.name == 'nt':  # Windows 系统
        return os.path.join(os.environ['USERPROFILE'], 'Videos')
    elif os.name == 'posix':  # macOS 或 Linux 系统
        return os.path.join(str(Path.home()), 'Movies')
    return None

# 获取默认路径
image_target_directory = config.get('Paths', 'image_target_directory', fallback=get_user_pictures_folder())
video_target_directory = config.get('Paths', 'video_target_directory', fallback=get_user_videos_folder())
sd_card_directory = config.get('Paths', 'sd_card_directory', fallback='/Volumes/Untitled')

class CopyThread(QThread):
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(str)

    def __init__(self, image_target, video_target, sd_card, event_name):
        super().__init__()
        self.image_target = image_target
        self.video_target = video_target
        self.sd_card = sd_card
        self.event_name = event_name

    def run(self):
        # 定义图片文件的扩展名，包含更多 RAW 格式
        image_extensions = (
            '.jpg', '.jpeg', '.png', '.raw', '.nef', '.cr2', '.CR3',
            '.arw',  # 索尼 RAW 格式
            '.dng',  # 通用 RAW 格式
            '.raf',  # 富士 RAW 格式
            '.orf',  # 奥林巴斯 RAW 格式
            '.pef',  # 宾得 RAW 格式
            '.srw',  # 三星 RAW 格式
            '.x3f'   # 适马 RAW 格式
        )
        video_extensions = ('.mp4', '.avi', '.mov')

        all_files = []
        for root, dirs, files in os.walk(self.sd_card):
            logging.debug(f"Processing directory: {root}")
            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
                # 增加调试信息，输出每个文件的扩展名
                file_ext = os.path.splitext(file)[1].lower()
                logging.debug(f"Found file: {file}, extension: {file_ext}")

        total_files = len(all_files)
        copied_files = 0
        created_folders = set()

        for file_path in all_files:
            file = os.path.basename(file_path)
            lower_file = file.lower()
            is_image = False
            is_video = False
            for ext in image_extensions:
                if lower_file.endswith(ext.lower()):
                    is_image = True
                    break
            for ext in video_extensions:
                if lower_file.endswith(ext.lower()):
                    is_video = True
                    break

            if is_image:
                target_dir = self.image_target
                logging.debug(f"File {file} identified as an image.")
            elif is_video:
                target_dir = self.video_target
                logging.debug(f"File {file} identified as a video.")
            else:
                logging.debug(f"File {file} is neither an image nor a video, skipping. Extensions checked: {image_extensions + video_extensions}")
                continue

            logging.debug(f"Processing file: {file}")

            # 获取文件的修改时间
            try:
                date_taken = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y%m%d')
            except Exception as e:
                logging.error(f"Failed to get modification time for {file}: {e}")
                continue

            # 创建包含活动名称的文件夹
            folder_name = f'{date_taken}_{self.event_name}'
            folder_path = os.path.join(target_dir, folder_name)
            if folder_path not in created_folders:
                if not os.path.exists(folder_path):
                    try:
                        os.makedirs(folder_path)
                        logging.info(f"Created folder: {folder_path}")
                    except Exception as e:
                        logging.error(f"Failed to create folder {folder_path}: {e}")
                        continue
                created_folders.add(folder_path)

            # 处理文件名重复情况
            new_file_name = file
            new_file_path = os.path.join(folder_path, new_file_name)
            counter = 1
            while os.path.exists(new_file_path):
                base_name, ext = os.path.splitext(file)
                new_file_name = f'{base_name}_{counter}{ext}'
                new_file_path = os.path.join(folder_path, new_file_name)
                counter += 1

            # 拷贝文件并进行哈希校验
            try:
                logging.info(f"Copying {file} to {new_file_path}")
                shutil.copy2(file_path, new_file_path)
                with open(file_path, 'rb') as f1, open(new_file_path, 'rb') as f2:
                    hash1 = hashlib.sha256(f1.read()).hexdigest()
                    hash2 = hashlib.sha256(f2.read()).hexdigest()
                    if hash1 != hash2:
                        logging.error(f'哈希校验失败: {file}')
                    else:
                        logging.info(f'成功拷贝: {file}')
            except Exception as e:
                logging.error(f'拷贝文件时出错: {file}, 错误信息: {e}')

            copied_files += 1
            progress = int((copied_files / total_files) * 100)
            self.progress_signal.emit(progress)

        result_msg = f"拷贝完成，生成的文件夹有：{', '.join(created_folders)}"
        self.result_signal.emit(result_msg)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 设置窗口标题和大小
        self.setWindowTitle('拷卡并校验')
        self.setGeometry(300, 300, 600, 400)

        # 创建布局
        main_layout = QVBoxLayout()

        # 图片目标目录选择
        image_layout = QHBoxLayout()
        image_label = QLabel('图片目标目录:')
        self.image_input = QLineEdit(image_target_directory)
        image_button = QPushButton('选择目录')
        image_button.clicked.connect(self.select_image_directory)
        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_input)
        image_layout.addWidget(image_button)

        # 视频目标目录选择
        video_layout = QHBoxLayout()
        video_label = QLabel('视频目标目录:')
        self.video_input = QLineEdit(video_target_directory)
        video_button = QPushButton('选择目录')
        video_button.clicked.connect(self.select_video_directory)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_input)
        video_layout.addWidget(video_button)

        # SD 卡目录选择
        sd_layout = QHBoxLayout()
        sd_label = QLabel('SD 卡目录:')
        self.sd_input = QLineEdit(sd_card_directory)
        sd_button = QPushButton('选择目录')
        sd_button.clicked.connect(self.select_sd_directory)
        sd_layout.addWidget(sd_label)
        sd_layout.addWidget(self.sd_input)
        sd_layout.addWidget(sd_button)

        # 活动名称输入
        event_layout = QHBoxLayout()
        event_label = QLabel('活动名称:')
        self.event_input = QLineEdit()
        event_layout.addWidget(event_label)
        event_layout.addWidget(self.event_input)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        # 结果显示标签，设置自动换行
        self.result_label = QLabel()
        self.result_label.setFont(QFont('Arial', 12))
        self.result_label.setWordWrap(True)

        # 开始拷贝按钮
        start_button = QPushButton('开始拷贝')
        start_button.clicked.connect(self.start_copying)

        # 添加布局到主布局
        main_layout.addLayout(image_layout)
        main_layout.addLayout(video_layout)
        main_layout.addLayout(sd_layout)
        main_layout.addLayout(event_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_label)
        main_layout.addWidget(start_button)

        self.setLayout(main_layout)

    def select_image_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择图片目标目录')
        if directory:
            self.image_input.setText(directory)

    def select_video_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择视频目标目录')
        if directory:
            self.video_input.setText(directory)

    def select_sd_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择 SD 卡目录')
        if directory:
            self.sd_input.setText(directory)

    def start_copying(self):
        image_target = self.image_input.text()
        video_target = self.video_input.text()
        sd_card = self.sd_input.text()
        event_name = self.event_input.text()

        self.copy_thread = CopyThread(image_target, video_target, sd_card, event_name)
        self.copy_thread.progress_signal.connect(self.update_progress)
        self.copy_thread.result_signal.connect(self.show_result)
        self.copy_thread.start()

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def show_result(self, result):
        self.result_label.setText(result)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
    