# # changelog:
# # Version 1.8 - 2025-03-18
# ## 功能特性
# - 优化 UI 界面，使其更加美观和现代化。
# - 在 UI 上添加简洁的使用说明书，方便用户了解程序运行方式。
# - 若用户未选择日期，程序会拷贝卡上所有日期的文件。
# - 优化日期选择部分的 UI，采用下拉框形式。
# - 实现从 SD 卡拷贝图片和视频到指定目录，支持用户通过 GUI 指定图片、视频目标目录及 SD 卡目录。
# - 基于拍摄日期或修改时间创建文件夹，完成图片、视频文件重命名。
# - 处理文件名重复场景，通过添加序号避免文件覆盖。
# - 集成哈希校验功能，保障文件拷贝准确性。
# - GUI 界面添加进度条，实时展示拷贝进度并在完成后反馈结果。
# - 增加活动名称输入功能，使拷贝后的文件夹名称包含活动名称。
# - 当 SD 卡目录中没有可用的图片或视频文件时，提醒用户该路径为空。
# - 支持RAW文件和JPG文件分开拷贝到不同文件夹。2025-05-28
# 
# ## 问题修复与优化
# - 修复进度条卡住问题，拷贝完成后反馈最终生成的文件夹名称。
# - 优化结果文字显示，支持自动换行。
# - 解决进度条异常问题。
# - 增加对 `.CR3` 文件的支持。
# - 调整逻辑，放弃读取 EXIF 信息，改用文件修改时间确定日期。
# - 添加详细日志，用于排查 `.CR3` 文件拷贝失败问题。
# - 修复未选择日期直接点击开始拷贝程序无法正常使用的 BUG。
# - 修复macOS深色模式下UI显示问题。2025-05-28

import os
import datetime
import shutil
import hashlib
import logging
from PIL import Image
from PIL.ExifTags import TAGS
import configparser
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QProgressBar, QComboBox, QTextEdit, QMessageBox
from PyQt5.QtGui import QFont, QPalette, QColor
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

    def __init__(self, image_target, video_target, sd_card, event_name, selected_dates):
        super().__init__()
        self.image_target = image_target
        self.video_target = video_target
        self.sd_card = sd_card
        self.event_name = event_name
        self.selected_dates = selected_dates

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
        # 单独定义RAW格式扩展名（需要和image_extensions保持一致）
        raw_extensions = ('.raw', '.nef', '.cr2', '.CR3', '.arw', '.dng', '.raf', '.orf', '.pef', '.srw', '.x3f')
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

        if total_files == 0:
            self.result_signal.emit("SD 卡目录中没有可用的图片或视频文件，请检查路径。")
            return

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

            if is_image or is_video:
                try:
                    date_taken = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y%m%d')
                    if self.selected_dates and date_taken not in self.selected_dates:
                        continue
                except Exception as e:
                    logging.error(f"Failed to get modification time for {file}: {e}")
                    continue

                if is_image:
                    target_dir = self.image_target
                    logging.debug(f"File {file} identified as an image.")
                elif is_video:
                    target_dir = self.video_target
                    logging.debug(f"File {file} identified as a video.")

                logging.debug(f"Processing file: {file}")

                # 创建包含活动名称的文件夹
                folder_name = f'{date_taken}_{self.event_name}'
                folder_path = os.path.join(target_dir, folder_name)
                if folder_path not in created_folders:
                    if not os.path.exists(folder_path):
                        try:
                            os.makedirs(folder_path)
                            logging.info(f"Created folder: {folder_path}")
                            if is_image:
                                # 仅为图片文件夹创建“选择”和“原图”子文件夹
                                select_folder = os.path.join(folder_path, '选择')
                                original_folder = os.path.join(folder_path, '原图')
                                # 新增RAW和JPG分类子文件夹
                                raw_folder = os.path.join(original_folder, 'RAW')
                                jpg_folder = os.path.join(original_folder, 'JPG')
                                if not os.path.exists(select_folder):
                                    os.makedirs(select_folder)
                                    logging.info(f"Created subfolder: {select_folder}")
                                if not os.path.exists(original_folder):
                                    os.makedirs(original_folder)
                                    logging.info(f"Created subfolder: {original_folder}")
                                # 创建分类子目录
                                if not os.path.exists(raw_folder):
                                    os.makedirs(raw_folder)
                                    logging.info(f"Created subfolder: {raw_folder}")
                                if not os.path.exists(jpg_folder):
                                    os.makedirs(jpg_folder)
                                    logging.info(f"Created subfolder: {jpg_folder}")
                        except Exception as e:
                            logging.error(f"Failed to create folder {folder_path}: {e}")
                            continue
                    created_folders.add(folder_path)

                # 处理文件名重复情况
                new_file_name = file
                file_ext = os.path.splitext(file)[1].lower()
                # 区分RAW和JPG存储路径
                if is_image:
                    if file_ext in raw_extensions:
                        target_subfolder = os.path.join(folder_path, '原图', 'RAW')
                    else:
                        target_subfolder = os.path.join(folder_path, '原图', 'JPG')
                else:
                    target_subfolder = folder_path
                new_file_path = os.path.join(target_subfolder, new_file_name)
                counter = 1
                while os.path.exists(new_file_path):
                    base_name, ext = os.path.splitext(file)
                    new_file_name = f'{base_name}_{counter}{ext}'
                    new_file_path = os.path.join(target_subfolder, new_file_name)
                    counter += 1

                # 拷贝文件并进行哈希校验（原逻辑不变）
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

        # 确保进度条达到 100%（原逻辑不变）
        self.progress_signal.emit(100)

        result_msg = f"拷贝完成，生成的文件夹有：{', '.join(created_folders)}"
        self.result_signal.emit(result_msg)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 设置窗口标题和大小
        self.setWindowTitle('拷卡并校验')
        self.setGeometry(300, 300, 800, 600)

        # 获取系统默认调色板并自动适配主题
        system_palette = QApplication.palette()
        self.setPalette(system_palette)  # 初始使用系统默认调色板

        # 创建布局
        main_layout = QVBoxLayout()

        # 图片目标目录选择
        image_layout = QHBoxLayout()
        image_label = QLabel('图片目标目录:')
        image_label.setFont(QFont('Arial', 12))
        self.image_input = QLineEdit(image_target_directory)
        self.image_input.setFont(QFont('Arial', 12))
        # 使用系统输入框样式（自动适配深浅模式）
        input_palette = self.image_input.palette()  # 直接使用系统默认输入框调色板
        self.image_input.setPalette(input_palette)
        image_button = QPushButton('选择目录')
        image_button.setFont(QFont('Arial', 12))
        image_button.setStyleSheet("QPushButton { background-color: #05B8CC; color: white; border: none; border-radius: 5px; padding: 5px 10px; }"
                                    "QPushButton:hover { background-color: #0497AB; }")  # 保留自定义按钮颜色
        image_button.clicked.connect(self.select_image_directory)
        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_input)
        image_layout.addWidget(image_button)

        # 视频目标目录选择（样式自动适配）
        video_layout = QHBoxLayout()
        video_label = QLabel('视频目标目录:')
        video_label.setFont(QFont('Arial', 12))
        self.video_input = QLineEdit(video_target_directory)
        self.video_input.setFont(QFont('Arial', 12))
        self.video_input.setPalette(input_palette)  # 复用系统输入框样式
        video_button = QPushButton('选择目录')
        video_button.setFont(QFont('Arial', 12))
        video_button.setStyleSheet("QPushButton { background-color: #05B8CC; color: white; border: none; border-radius: 5px; padding: 5px 10px; }"
                                    "QPushButton:hover { background-color: #0497AB; }")
        video_button.clicked.connect(self.select_video_directory)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_input)
        video_layout.addWidget(video_button)

        # SD 卡目录选择（样式自动适配）
        sd_layout = QHBoxLayout()
        sd_label = QLabel('SD 卡目录:')
        sd_label.setFont(QFont('Arial', 12))
        self.sd_input = QLineEdit(sd_card_directory)
        self.sd_input.setFont(QFont('Arial', 12))
        sd_button = QPushButton('选择目录')
        sd_button.setFont(QFont('Arial', 12))
        sd_button.setStyleSheet("QPushButton { background-color: #05B8CC; color: white; border: none; border-radius: 5px; padding: 5px 10px; }"
                                "QPushButton:hover { background-color: #0497AB; }")
        sd_button.clicked.connect(self.select_sd_directory)
        sd_layout.addWidget(sd_label)
        sd_layout.addWidget(self.sd_input)
        sd_layout.addWidget(sd_button)

        # 活动名称输入（样式自动适配）
        event_layout = QHBoxLayout()
        event_label = QLabel('活动名称:')
        event_label.setFont(QFont('Arial', 12))
        self.event_input = QLineEdit()
        self.event_input.setFont(QFont('Arial', 12))
        self.event_input.setPalette(input_palette)  # 复用系统输入框样式
        event_layout.addWidget(event_label)
        event_layout.addWidget(self.event_input)

        # 日期选择下拉框（使用系统主题样式）
        date_layout = QHBoxLayout()
        date_label = QLabel('选择日期:')
        date_label.setFont(QFont('Arial', 12))
        self.date_combo = QComboBox()
        self.date_combo.setFont(QFont('Arial', 12))
        # 使用系统主题颜色
        self.date_combo.setStyleSheet("QComboBox { color: palette(window-text); background-color: palette(base); }"
                                      "QComboBox QAbstractItemView { color: palette(window-text); background-color: palette(base); }")
        self.date_combo.addItem("全部日期")
        date_button = QPushButton('获取日期')
        date_button.setFont(QFont('Arial', 12))
        date_button.setStyleSheet("QPushButton { background-color: #05B8CC; color: white; border: none; border-radius: 5px; padding: 5px 10px; }"
                                  "QPushButton:hover { background-color: #0497AB; }")
        date_button.clicked.connect(self.get_dates)
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_combo)
        date_layout.addWidget(date_button)

        # 进度条（使用系统主题颜色）
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar { border: 2px solid palette(mid); border-radius: 5px; text-align: center; color: palette(window-text); }"
                                        "QProgressBar::chunk { background-color: palette(highlight); width: 20px; }")

        # 结果显示标签（自动适配文字颜色）
        self.result_label = QLabel()
        self.result_label.setFont(QFont('Arial', 12))
        self.result_label.setWordWrap(True)

        # 开始拷贝按钮（保留自定义颜色）
        start_button = QPushButton('开始拷贝')
        start_button.setFont(QFont('Arial', 14, QFont.Bold))
        start_button.setStyleSheet("QPushButton { background-color: #FFA500; color: white; border: none; border-radius: 5px; padding: 10px 20px; }"
                                   "QPushButton:hover { background-color: #FF8C00; }")
        start_button.clicked.connect(self.start_copying)

        # 使用说明书（自动适配背景和文字颜色）
        instruction_text = """
使用说明：
1. 选择图片目标目录：点击“选择目录”按钮，指定图片拷贝的目标文件夹。
2. 选择视频目标目录：点击“选择目录”按钮，指定视频拷贝的目标文件夹。
3. 选择 SD 卡目录：点击“选择目录”按钮，指定 SD 卡所在的文件夹。
4. 输入活动名称：在输入框中输入本次活动的名称，用于生成文件夹名称。
5. 获取日期：点击“获取日期”按钮，程序将自动获取 SD 卡中文件的日期信息。
6. 选择日期：从下拉框中选择要拷贝的文件日期，若选择“全部日期”，将拷贝所有日期的文件。
7. 开始拷贝：点击“开始拷贝”按钮，程序将开始拷贝文件，并在进度条中显示拷贝进度。
8. 查看结果：拷贝完成后，结果将显示在下方的文本区域。
"""
        instruction_label = QTextEdit()
        instruction_label.setReadOnly(True)
        instruction_label.setFont(QFont('Arial', 10))
        # 使用系统主题颜色
        instruction_label.setStyleSheet("QTextEdit { background-color: palette(base); color: palette(window-text); border: none; padding: 10px; }")
        instruction_label.setText(instruction_text)

        # 添加布局到主布局
        main_layout.addLayout(image_layout)
        main_layout.addLayout(video_layout)
        main_layout.addLayout(sd_layout)
        main_layout.addLayout(event_layout)
        main_layout.addLayout(date_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_label)
        main_layout.addWidget(start_button)
        main_layout.addWidget(instruction_label)

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

    def get_dates(self):
        sd_card = self.sd_input.text()
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
        dates = set()
        for root, dirs, files in os.walk(sd_card):
            for file in files:
                lower_file = file.lower()
                is_image = any(lower_file.endswith(ext.lower()) for ext in image_extensions)
                is_video = any(lower_file.endswith(ext.lower()) for ext in video_extensions)
                if is_image or is_video:
                    file_path = os.path.join(root, file)
                    try:
                        date_taken = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y%m%d')
                        dates.add(date_taken)
                    except Exception as e:
                        logging.error(f"Failed to get modification time for {file}: {e}")
        self.date_combo.clear()
        self.date_combo.addItem("全部日期")
        for date in sorted(dates):
            self.date_combo.addItem(date)

    def start_copying(self):
        image_target = self.image_input.text()
        video_target = self.video_input.text()
        sd_card = self.sd_input.text()
        event_name = self.event_input.text()
        selected_date = self.date_combo.currentText()
        if selected_date == "全部日期":
            selected_dates = []
        else:
            selected_dates = [selected_date]

        self.copy_thread = CopyThread(image_target, video_target, sd_card, event_name, selected_dates)
        self.copy_thread.progress_signal.connect(self.update_progress)
        self.copy_thread.result_signal.connect(self.show_result)
        self.copy_thread.start()

    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def show_result(self, result):
        if "SD 卡目录中没有可用的图片或视频文件" in result:
            QMessageBox.warning(self, "警告", result)
        else:
            self.result_label.setText(result)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
    