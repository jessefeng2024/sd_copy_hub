import os
import datetime
import shutil
import hashlib
import logging
from PIL import Image
from PIL.ExifTags import TAGS
import configparser
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QProgressBar, QComboBox, QTextEdit, QMessageBox,
    QCheckBox, QDialog
)
from PyQt5.QtGui import QFont, QPalette, QColor, QFontDatabase
from PyQt5.QtCore import QThread, pyqtSignal, Qt
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

    def __init__(self, image_target, video_target, sd_card, event_name, selected_dates, separate_raw):
        super().__init__()
        self.image_target = image_target
        self.video_target = video_target
        self.sd_card = sd_card
        self.event_name = event_name
        self.selected_dates = selected_dates
        # 新增：接收是否分开存放的参数
        self.separate_raw = separate_raw

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
                                # 仅创建"原图"子目录（移除"选择"目录创建）
                                original_folder = os.path.join(folder_path, '原图')
                                if not os.path.exists(original_folder):
                                    os.makedirs(original_folder)
                                    logging.info(f"Created subfolder: {original_folder}")
                                # 仅勾选时创建RAW/JPG子目录
                                if self.separate_raw:
                                    raw_folder = os.path.join(original_folder, 'RAW')
                                    jpg_folder = os.path.join(original_folder, 'JPG')
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
                    # 新增：根据复选框状态选择目标子文件夹
                    if self.separate_raw:
                        if file_ext in raw_extensions:
                            target_subfolder = os.path.join(folder_path, '原图', 'RAW')
                        else:
                            target_subfolder = os.path.join(folder_path, '原图', 'JPG')
                    else:
                        target_subfolder = os.path.join(folder_path, '原图')  # 不分类时直接存到“原图”
                else:
                    target_subfolder = folder_path
                new_file_path = os.path.join(target_subfolder, new_file_name)
                counter = 1
                while os.path.exists(new_file_path):
                    base_name, ext = os.path.splitext(file)
                    new_file_name = f'{base_name}_{counter}{ext}'
                    new_file_path = os.path.join(target_subfolder, new_file_name)
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

        # 确保进度条达到 100%
        self.progress_signal.emit(100)

        result_msg = f"拷贝完成，生成的文件夹有：{', '.join(created_folders)}"
        self.result_signal.emit(result_msg)


class InstructionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.setGeometry(400, 400, 600, 400)  # 对话框位置和尺寸
        
        # 初始化布局和说明文本
        layout = QVBoxLayout()
        instruction_text = """使用说明：
1. 选择目标目录：分别设置图片和视频的存储路径（默认使用系统图片/视频文件夹）
2. 选择SD卡目录：指定需要拷贝的SD卡根目录
3. 输入活动名称：用于生成带日期的目标文件夹（如20240520_公司活动）
4. 选择日期：点击「获取日期」自动识别SD卡中文件的修改日期，可单选指定日期或选择「全部日期」
5. 高级选项：勾选「RAW和JPG文件分开保存」会在「原图」目录下自动创建RAW/JPG子文件夹
6. 开始拷贝：确认设置后点击按钮开始拷贝，进度条会显示当前拷贝进度
"""
        
        # 使用说明文本框（与原样式保持一致）
        instruction_label = QTextEdit()
        instruction_label.setReadOnly(True)
        instruction_label.setFont(QFont('SF Pro', 11))
        instruction_label.setStyleSheet("""
            QTextEdit {
                background-color: palette(window);
                color: palette(window-text);
                border: 1px solid palette(midlight);
                border-radius: 8px;
                padding: 15px;
                opacity: 0.9;
            }
        """)
        instruction_label.setText(instruction_text)
        layout.addWidget(instruction_label)
        self.setLayout(layout)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 设置窗口标题和大小
        self.setWindowTitle('拷卡助手')
        self.setGeometry(300, 300, 700, 400)  # 调整窗口初始尺寸更紧凑

        # 获取系统默认调色板并自动适配主题（优化字体适配）
        system_palette = QApplication.palette()
        self.setPalette(system_palette)
        # 检查SF Pro字体是否存在（简化字体名称）
        font_db = QFontDatabase()
        # 优先使用SF Pro，其次使用macOS通用字体（Helvetica Neue/Arial）
        preferred_fonts = ['SF Pro', 'Helvetica Neue', 'Arial']
        main_font = None
        for font in preferred_fonts:
            if font in font_db.families():
                main_font = QFont(font, 12)
                break
        if not main_font:
            main_font = QFont()  # 最终回退到系统默认
            logging.warning("系统未找到以下字体: SF Pro, Helvetica Neue, Arial，使用系统默认字体")  # 明确提示检查的字体列表
        QApplication.setFont(main_font)

        # 创建布局（优化：增加主布局边距和控件间距）
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)  # 四边边距20px
        main_layout.setSpacing(15)  # 控件间距15px

        # 通用样式定义（调整输入框高度）
        input_style = """
            QLineEdit {
                border: 1px solid palette(mid);
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 12px;
                color: palette(window-text);
                background-color: palette(window);
            }
            QLineEdit:focus {
                border-color: palette(highlight);
                background-color: palette(window);
            }
        """

        # 新增：定义通用按钮样式
        button_style = """
            QPushButton {
                border: 1px solid palette(mid);
                border-radius: 5px;
                padding: 5px 16px;
                font-size: 12px;
                background-color: palette(base);
                color: palette(window-text);
            }
            QPushButton:hover {
                border-color: palette(highlight);
                background-color: palette(alternate-base);
            }
        """

        # 图片目标目录选择（优化：标签固定宽度+输入框扩展）
        image_layout = QHBoxLayout()
        image_label = QLabel('图片目标目录:')
        image_label.setFixedWidth(100)  # 标签固定宽度对齐
        self.image_input = QLineEdit(image_target_directory)
        self.image_input.setStyleSheet(input_style)
        image_button = QPushButton('选择目录')
        image_button.setStyleSheet(button_style)  # 现在button_style已定义
        image_button.clicked.connect(self.select_image_directory)
        image_layout.addWidget(image_label)
        image_layout.addWidget(self.image_input, 1)  # 输入框占1份空间
        image_layout.addWidget(image_button)

        # 视频目标目录选择（样式与图片目录统一）
        video_layout = QHBoxLayout()
        video_label = QLabel('视频目标目录:')
        video_label.setFixedWidth(100)
        self.video_input = QLineEdit(video_target_directory)
        self.video_input.setStyleSheet(input_style)
        video_button = QPushButton('选择目录')
        video_button.setStyleSheet(button_style)  # 引用已定义的button_style
        video_button.clicked.connect(self.select_video_directory)
        video_layout.addWidget(video_label)
        video_layout.addWidget(self.video_input, 1)
        video_layout.addWidget(video_button)

        # SD 卡目录选择（样式统一）
        sd_layout = QHBoxLayout()
        sd_label = QLabel('SD 卡目录:')
        sd_label.setFixedWidth(100)
        self.sd_input = QLineEdit(sd_card_directory)
        self.sd_input.setStyleSheet(input_style)
        sd_button = QPushButton('选择目录')
        sd_button.setStyleSheet(button_style)  # 引用已定义的button_style
        sd_button.clicked.connect(self.select_sd_directory)
        sd_layout.addWidget(sd_label)
        sd_layout.addWidget(self.sd_input, 1)
        sd_layout.addWidget(sd_button)

        # 活动名称输入（优化：标签对齐+输入框扩展）
        event_layout = QHBoxLayout()
        event_label = QLabel('活动名称:')
        event_label.setFixedWidth(100)
        self.event_input = QLineEdit()
        self.event_input.setStyleSheet(input_style)
        event_layout.addWidget(event_label)
        event_layout.addWidget(self.event_input, 1)

        # 分开存放复选框（最终对齐方案：与其他行标签起始位置完全一致）
        separate_layout = QHBoxLayout()
        # 重置左边距为0（与image_layout/video_layout等子布局保持一致）
        separate_layout.setContentsMargins(0, 0, 0, 0)
        # 标题标签固定宽度100px（与"图片目标目录"等标签宽度一致）
        separate_title = QLabel('高级选项：')
        separate_title.setFont(main_font)
        separate_title.setFixedWidth(100)  # 关键：与其他标签宽度一致
        # 复选框直接跟随标题，不额外添加边距
        self.separate_raw_checkbox = QCheckBox('RAW和JPG文件分开保存')
        self.separate_raw_checkbox.setFont(main_font)
        # 添加顺序：标题+复选框
        separate_layout.addWidget(separate_title)
        separate_layout.addWidget(self.separate_raw_checkbox)

        # 日期选择布局（调整下拉框高度）
        date_layout = QHBoxLayout()  # 新增：初始化日期选择布局
        date_label = QLabel('选择日期:')  # 新增：定义日期标签
        date_label.setFixedWidth(100)  # 标签固定宽度对齐（与其他标签统一）
        self.date_combo = QComboBox()
        self.date_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid palette(mid);
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 12px;
                background-color: palette(base);
                color: palette(window-text);
            }
            QComboBox:focus {
                border-color: palette(highlight);
            }
            QComboBox::drop-down {
                width: 24px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;  /* 移除自定义SVG路径 */
            }
        """)
        # 重置为系统默认样式（自动使用标准下拉箭头）
        self.date_combo.setStyle(QApplication.style())
        date_button = QPushButton('获取日期')
        date_button.setStyleSheet(button_style)
        date_button.clicked.connect(self.get_dates)
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_combo, 1)  # 下拉框占1份空间
        date_layout.addWidget(date_button)

        # 进度条（优化：增加高度+圆角，初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)  # 初始隐藏
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid palette(midlight);
                border-radius: 8px;
                background-color: palette(base);
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: palette(highlight);
                border-radius: 7px;
            }
        """)

        # 结果标签（优化：增加内边距+文字颜色）
        self.result_label = QLabel()
        self.result_label.setFont(QFont('SF Pro', 12))
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("padding: 10px; color: palette(window-text);")

        # 开始拷贝按钮（优化：强调按钮样式，调整尺寸）
        start_button = QPushButton('开始拷贝')
        start_button.setFont(QFont('SF Pro', 13, QFont.Medium))  # 原14px → 13px
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;  /* macOS主题蓝 */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                margin: 10px 0;  /* 原10px 0 → 上下边距减小为5px */
            }
            QPushButton:hover {
                background-color: #0066CC;
            }
        """)
        start_button.clicked.connect(self.start_copying)

        # 使用说明书（提前定义说明文本）
        instruction_text = """使用说明：
1. 选择目标目录：分别设置图片和视频的存储路径（默认使用系统图片/视频文件夹）
2. 选择SD卡目录：指定需要拷贝的SD卡根目录
3. 输入活动名称：用于生成带日期的目标文件夹（如20240520_公司活动）
4. 选择日期：点击「获取日期」自动识别SD卡中文件的修改日期，可单选指定日期或选择「全部日期」
5. 高级选项：勾选「RAW和JPG文件分开保存」会在「原图」目录下自动创建RAW/JPG子文件夹
6. 开始拷贝：确认设置后点击按钮开始拷贝，进度条会显示当前拷贝进度
"""

        # 使用说明书（主题自适应背景，合并重复定义）
        instruction_label = QTextEdit()
        instruction_label.setReadOnly(True)
        instruction_label.setFont(QFont('SF Pro', 11))
        instruction_label.setStyleSheet("""
            QTextEdit {
                background-color: palette(window);  /* 系统主窗口背景色（浅色主题为白/深色为深灰） */
                color: palette(window-text);  /* 系统文字色（与背景自动对比） */
                border: 1px solid palette(midlight);  /* 系统浅中间色，增强边界 */
                border-radius: 8px;
                padding: 15px;
                opacity: 0.9;  /* 半透明效果 */
            }
        """)
        instruction_label.setText(instruction_text)  # instruction_text 已提前定义

        # 添加所有控件到主布局（顺序优化）
        main_layout.addLayout(image_layout)
        main_layout.addLayout(video_layout)
        main_layout.addLayout(sd_layout)
        main_layout.addLayout(event_layout)
        main_layout.addLayout(separate_layout)
        main_layout.addLayout(date_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_label)
        main_layout.addWidget(start_button, 0, Qt.AlignCenter)  # 按钮居中

        # 添加使用说明入口按钮（放置在开始拷贝按钮下方）
        instruction_button = QPushButton('使用说明')
        instruction_button.setStyleSheet(button_style)  # 使用已定义的通用按钮样式
        instruction_button.clicked.connect(self.show_instruction_dialog)
        main_layout.addWidget(instruction_button, 0, Qt.AlignRight)  # 按钮右对齐

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
        # 显示进度条
        self.progress_bar.setVisible(True)
        # 清空上次结果
        self.result_label.setText("")
        
        # 获取用户输入参数
        image_target = self.image_input.text()
        video_target = self.video_input.text()
        sd_card = self.sd_input.text()
        event_name = self.event_input.text()
        selected_dates = [self.date_combo.currentText()] if self.date_combo.currentText() != "全部日期" else []
        separate_raw = self.separate_raw_checkbox.isChecked()
    
        # 校验输入（补充基础校验逻辑）
        if not image_target or not video_target or not sd_card:
            QMessageBox.warning(self, "错误", "请至少选择图片目标目录、视频目标目录和SD卡目录")
            return
    
        # 启动拷贝线程
        self.copy_thread = CopyThread(image_target, video_target, sd_card, event_name, selected_dates, separate_raw)
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

    def show_instruction_dialog(self):
        """显示使用说明对话框"""
        dialog = InstructionDialog(self)
        dialog.exec_()  # 模态显示对话框（阻塞主窗口）

if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()


class DirectorySelector(QWidget):
    """目录选择组件（独立封装）"""
    def __init__(self, label_text, default_path):
        super().__init__()
        self.label = QLabel(label_text)
        self.label.setFixedWidth(100)
        self.input = QLineEdit(default_path)
        self.input.setStyleSheet(input_style)  # 复用全局输入框样式
        self.button = QPushButton('选择目录')
        self.button.setStyleSheet(button_style)  # 复用全局按钮样式
        
        layout = QHBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def get_path(self):
        return self.input.text()

    def initUI(self):
        # 使用封装后的目录选择组件
        self.image_selector = DirectorySelector('图片目标目录:', image_target_directory)
        self.video_selector = DirectorySelector('视频目标目录:', video_target_directory)
        self.sd_selector = DirectorySelector('SD 卡目录:', sd_card_directory)

        # 连接按钮点击事件
        self.image_selector.button.clicked.connect(self.select_image_directory)
        self.video_selector.button.clicked.connect(self.select_video_directory)
        self.sd_selector.button.clicked.connect(self.select_sd_directory)

        # 将组件添加到主布局
        main_layout.addWidget(self.image_selector)
        main_layout.addWidget(self.video_selector)
        main_layout.addWidget(self.sd_selector)

        # 主题选择布局
        theme_layout = QHBoxLayout()
        theme_label = QLabel('选择主题:')
        theme_label.setFixedWidth(100)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['系统默认', '深色主题', '浅色主题'])
        self.theme_combo.setStyleSheet(input_style)  # 复用输入框样式
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo, 1)
        main_layout.addLayout(theme_layout)

    def change_theme(self, index):
        """根据选择切换主题"""
        palette = QPalette()
        if index == 1:  # 深色主题
            dark_color = QColor(53, 53, 53)
            palette.setColor(QPalette.Window, dark_color)
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, dark_color)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, dark_color)
            palette.setColor(QPalette.ButtonText, Qt.white)
        elif index == 2:  # 浅色主题
            light_color = QColor(240, 240, 240)
            palette.setColor(QPalette.Window, light_color)
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, light_color)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, light_color)
            palette.setColor(QPalette.ButtonText, Qt.black)
        else:  # 系统默认
            palette = QApplication.palette()
        self.setPalette(palette)  # 应用全局调色板

    def initUI(self):
        # 使用封装后的目录选择组件
        self.image_selector = DirectorySelector('图片目标目录:', image_target_directory)
        self.video_selector = DirectorySelector('视频目标目录:', video_target_directory)
        self.sd_selector = DirectorySelector('SD 卡目录:', sd_card_directory)

        # 连接按钮点击事件
        self.image_selector.button.clicked.connect(self.select_image_directory)
        self.video_selector.button.clicked.connect(self.select_video_directory)
        self.sd_selector.button.clicked.connect(self.select_sd_directory)

        # 将组件添加到主布局
        main_layout.addWidget(self.image_selector)
        main_layout.addWidget(self.video_selector)
        main_layout.addWidget(self.sd_selector)

        # 主题选择布局
        theme_layout = QHBoxLayout()
        theme_label = QLabel('选择主题:')
        theme_label.setFixedWidth(100)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['系统默认', '深色主题', '浅色主题'])
        self.theme_combo.setStyleSheet(input_style)  # 复用输入框样式
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo, 1)
        main_layout.addLayout(theme_layout)

    def change_theme(self, index):
        """根据选择切换主题"""
        palette = QPalette()
        if index == 1:  # 深色主题
            dark_color = QColor(53, 53, 53)
            palette.setColor(QPalette.Window, dark_color)
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, dark_color)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, dark_color)
            palette.setColor(QPalette.ButtonText, Qt.white)
        elif index == 2:  # 浅色主题
            light_color = QColor(240, 240, 240)
            palette.setColor(QPalette.Window, light_color)
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, light_color)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, light_color)
            palette.setColor(QPalette.ButtonText, Qt.black)
        else:  # 系统默认
            palette = QApplication.palette()
        self.setPalette(palette)  # 应用全局调色板
    