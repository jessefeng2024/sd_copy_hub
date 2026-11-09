import sys
import os
import datetime
import shutil
import hashlib
import logging
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QLineEdit, QFileDialog, 
                             QProgressBar, QComboBox, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSettings, QRectF
from PyQt5.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient, 
                         QPainterPath, QPen)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 支持主流相机 RAW 与视频格式
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.heic', '.heif', '.raw', '.nef', '.cr2', '.cr3', 
             '.arw', '.dng', '.raf', '.orf', '.pef', '.srw', '.x3f')
VIDEO_EXT = ('.mp4', '.avi', '.mov', '.mxf', '.mts', '.m4v')


class ScanThread(QThread):
    """异步扫描线程：智能聚类并缓存文件列表，过滤 macOS 隐藏文件"""
    scan_done_signal = pyqtSignal(list, list)
    
    def __init__(self, sd_card):
        super().__init__()
        self.sd_card = sd_card

    def run(self):
        if not os.path.exists(self.sd_card):
            self.scan_done_signal.emit([], [])
            return

        cached_files = []
        for root, dirs, files in os.walk(self.sd_card):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.startswith('.'):
                    continue
                if file.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                    full_path = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(full_path)
                        dt = datetime.datetime.fromtimestamp(mtime)
                        cached_files.append((full_path, dt))
                    except Exception:
                        continue
        
        if not cached_files:
            self.scan_done_signal.emit([], [])
            return

        cached_files.sort(key=lambda x: x[1])
        
        groups = []
        current_group = [cached_files[0][1]]
        for i in range(1, len(cached_files)):
            f_time = cached_files[i][1]
            if (f_time - current_group[-1]).total_seconds() <= 7200:
                current_group.append(f_time)
            else:
                groups.append(self.format_group(current_group))
                current_group = [f_time]
        groups.append(self.format_group(current_group))
        
        self.scan_done_signal.emit(groups, cached_files)

    def format_group(self, group):
        start, end = group[0], group[-1]
        if start.date() == end.date():
            return f"{start.strftime('%Y%m%d')}_{start.strftime('%H%M')}-{end.strftime('%H%M')}"
        return f"{start.strftime('%Y%m%d_%H%M')}-{end.strftime('%Y%m%d_%H%M')}"


class CopyThread(QThread):
    """安全高速拷贝线程：边拷边算 Hash + 防重复拷贝 + 视频自动重命名"""
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)

    def __init__(self, image_target, video_target, sd_card, event_name, selected_date, file_type, cached_files=None):
        super().__init__()
        self.image_target = image_target
        self.video_target = video_target
        self.sd_card = sd_card
        self.event_name = event_name.strip()
        self.selected_date = selected_date
        self.file_type = file_type
        self.cached_files = cached_files or []

    def copy_and_verify(self, src, dst):
        src_hash = hashlib.sha256()
        buf_size = 1024 * 1024  # 1MB Buffer
        
        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            while chunk := fsrc.read(buf_size):
                src_hash.update(chunk)
                fdst.write(chunk)
        shutil.copystat(src, dst)

        dst_hash = hashlib.sha256()
        with open(dst, 'rb') as fdst:
            while chunk := fdst.read(buf_size):
                dst_hash.update(chunk)

        return src_hash.hexdigest() == dst_hash.hexdigest()

    def parse_date_range(self, dr_str):
        parts = dr_str.strip().split('-')
        s_str = parts[0]
        e_str = s_str[:9] + parts[1] if len(parts[1]) == 4 else parts[1]
        start_dt = datetime.datetime.strptime(s_str, '%Y%m%d_%H%M')
        end_dt = datetime.datetime.strptime(e_str, '%Y%m%d_%H%M') + datetime.timedelta(minutes=1)
        return start_dt, end_dt, start_dt.strftime('%Y%m%d')

    def run(self):
        if not self.cached_files:
            self.status_signal.emit("正在读取 SD 卡文件列表...")
            for root, dirs, files in os.walk(self.sd_card):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if f.startswith('.'):
                        continue
                    if f.lower().endswith(IMAGE_EXT + VIDEO_EXT):
                        full_path = os.path.join(root, f)
                        try:
                            dt = datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
                            self.cached_files.append((full_path, dt))
                        except Exception:
                            continue

        time_filter = None
        session_date_prefix = None
        if self.selected_date and self.selected_date != "全部日期":
            try:
                start_dt, end_dt, session_date_prefix = self.parse_date_range(self.selected_date)
                time_filter = (start_dt, end_dt)
            except Exception as e:
                logging.error(f"解析日期区间失败: {e}")

        final_list = []
        for f_path, f_time in self.cached_files:
            l_f = f_path.lower()
            is_img, is_vid = l_f.endswith(IMAGE_EXT), l_f.endswith(VIDEO_EXT)
            
            if (self.file_type == "仅图片" and not is_img) or \
               (self.file_type == "仅视频" and not is_vid) or \
               (not is_img and not is_vid):
                continue

            if time_filter:
                if not (time_filter[0] <= f_time < time_filter[1]):
                    continue

            final_list.append((f_path, f_time, is_img, is_vid))

        if not final_list:
            self.finished_signal.emit("提示：所选场次或过滤条件下没有找到文件")
            self.progress_signal.emit(100)
            return

        total = len(final_list)
        copied_count = 0
        skipped_count = 0
        failed_count = 0

        for idx, (f_path, f_time, is_img, is_vid) in enumerate(final_list, 1):
            filename = os.path.basename(f_path)
            self.status_signal.emit(f"正在导入 ({idx}/{total}): {filename}")
            
            try:
                base = self.image_target if is_img else self.video_target
                date_str = session_date_prefix if session_date_prefix else f_time.strftime('%Y%m%d')
                event_suffix = f"_{self.event_name}" if self.event_name else ""
                f_folder = f"{date_str}{event_suffix}"
                dest_dir = os.path.join(base, f_folder)
                
                sub_dir = os.path.join(dest_dir, '原图') if is_img else dest_dir
                os.makedirs(sub_dir, exist_ok=True)
                if is_img:
                    os.makedirs(os.path.join(dest_dir, '选择'), exist_ok=True)

                if is_vid:
                    ext = os.path.splitext(f_path)[1]
                    new_name = f"vid_{f_time.strftime('%Y%m%d%H%M%S')}{ext}"
                else:
                    new_name = filename

                dest_path = os.path.join(sub_dir, new_name)
                
                already_copied = False
                count = 1
                while os.path.exists(dest_path):
                    if os.path.getsize(f_path) == os.path.getsize(dest_path):
                        already_copied = True
                        break
                    n, e = os.path.splitext(new_name)
                    dest_path = os.path.join(sub_dir, f"{n}_{count}{e}")
                    count += 1

                if already_copied:
                    skipped_count += 1
                else:
                    if self.copy_and_verify(f_path, dest_path):
                        copied_count += 1
                    else:
                        os.remove(dest_path)
                        failed_count += 1
                        logging.error(f"文件校验失败，已删除: {dest_path}")

            except Exception as e:
                failed_count += 1
                logging.error(f"处理文件 {f_path} 出错: {e}")

            self.progress_signal.emit(int((idx / total) * 100))

        summary_parts = [f"成功导入 {copied_count} 个"]
        if skipped_count > 0:
            summary_parts.append(f"跳过已存在 {skipped_count} 个")
        if failed_count > 0:
            summary_parts.append(f"失败 {failed_count} 个")
        self.finished_signal.emit("✨ 任务完成：" + "，".join(summary_parts))


class GlassCard(QFrame):
    """自定义毛玻璃卡片：无离屏副作用的自绘阴影 + 半透明磨砂层 + 高光折射边框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 预留底部阴影绘制空间
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -4.0)

        # 1. 绘制柔和底部投影（替代容易引发布局挤压的 QGraphicsDropShadowEffect）
        shadow_rect = rect.translated(0, 3.0)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, 14, 14)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 70))

        # 2. 玻璃主体填充
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg_grad.setColorAt(0.0, QColor(255, 255, 255, 26))
        bg_grad.setColorAt(0.5, QColor(255, 255, 255, 14))
        bg_grad.setColorAt(1.0, QColor(255, 255, 255, 8))
        painter.fillPath(path, bg_grad)

        # 3. 玻璃边缘高光折射
        border_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        border_grad.setColorAt(0.0, QColor(255, 255, 255, 110))
        border_grad.setColorAt(0.4, QColor(255, 255, 255, 30))
        border_grad.setColorAt(1.0, QColor(255, 255, 255, 12))
        
        pen = QPen(border_grad, 1.2)
        painter.setPen(pen)
        painter.drawPath(path)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("FengC_Work", "SDCopyHub")
        self.cached_files = []
        self.initUI()

    def paintEvent(self, event):
        """绘制深空暗夜底色与流光弥散极光背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        base_grad = QLinearGradient(0, 0, w, h)
        base_grad.setColorAt(0.0, QColor(11, 15, 27))
        base_grad.setColorAt(0.5, QColor(18, 23, 40))
        base_grad.setColorAt(1.0, QColor(10, 12, 22))
        painter.fillRect(self.rect(), base_grad)

        orb1 = QRadialGradient(w * 0.15, h * 0.18, w * 0.55)
        orb1.setColorAt(0.0, QColor(0, 210, 255, 75))
        orb1.setColorAt(0.5, QColor(0, 140, 255, 25))
        orb1.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), orb1)

        orb2 = QRadialGradient(w * 0.88, h * 0.82, w * 0.6)
        orb2.setColorAt(0.0, QColor(140, 60, 255, 80))
        orb2.setColorAt(0.5, QColor(90, 30, 200, 30))
        orb2.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), orb2)

        orb3 = QRadialGradient(w * 0.65, h * 0.38, w * 0.4)
        orb3.setColorAt(0.0, QColor(255, 50, 160, 45))
        orb3.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), orb3)

    def create_divider(self):
        div = QFrame()
        div.setObjectName("glassDivider")
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        return div

    def initUI(self):
        self.setWindowTitle('SD Copy Hub · Glass Edition')
        self.setMinimumSize(860, 620)
        
        # 样式表：使用水平 padding，垂直方向由 FixedHeight 保证文字完全居中不裁切
        self.setStyleSheet("""
            QWidget {
                font-family: 'PingFang SC', -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
                color: #F8FAFC;
                font-size: 13px;
            }
            QLabel {
                background: transparent;
                color: #E2E8F0;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 800;
                color: #FFFFFF;
            }
            QLabel#badgeLabel {
                font-size: 11px;
                font-weight: 700;
                color: #38BDF8;
                background-color: rgba(56, 189, 248, 25);
                border: 1px solid rgba(56, 189, 248, 80);
                border-radius: 9px;
                padding: 3px 10px;
            }
            QLabel#subtitleLabel {
                font-size: 12px;
                color: #94A3B8;
                font-weight: 400;
            }
            QLabel#sectionHeader {
                font-size: 12px;
                font-weight: 600;
                color: #94A3B8;
                padding-left: 4px;
                letter-spacing: 0.6px;
            }
            QFrame#glassDivider {
                background-color: rgba(255, 255, 255, 18);
                border: none;
            }
            /* 输入框：取消垂直 padding 防止挤压字体，仅保留左右内边距 */
            QLineEdit {
                padding: 0px 12px;
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 8px;
                background-color: rgba(15, 23, 42, 120);
                color: #FFFFFF;
                font-size: 13px;
                selection-background-color: #00A8FF;
            }
            QLineEdit:hover {
                border: 1px solid rgba(255, 255, 255, 70);
                background-color: rgba(15, 23, 42, 150);
            }
            QLineEdit:focus {
                border: 1.5px solid #38BDF8;
                background-color: rgba(15, 23, 42, 190);
            }
            /* 次级按钮：取消垂直 padding，依靠固定高度居中文字 */
            QPushButton {
                background-color: rgba(255, 255, 255, 22);
                color: #F8FAFC;
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 8px;
                padding: 0px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 40);
                border-color: rgba(255, 255, 255, 90);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 15);
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 8);
                color: rgba(255, 255, 255, 65);
                border-color: rgba(255, 255, 255, 15);
            }
            /* 智能识别按钮 */
            QPushButton#scanBtn {
                background-color: rgba(56, 189, 248, 30);
                color: #7DD3FC;
                border: 1px solid rgba(56, 189, 248, 95);
            }
            QPushButton#scanBtn:hover {
                background-color: rgba(56, 189, 248, 60);
                color: #FFFFFF;
                border-color: #38BDF8;
            }
            /* 底部流光主按钮 */
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #00C6FF, stop:0.5 #0072FF, stop:1 #6366F1);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 75);
                border-radius: 10px;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QPushButton#primaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #38BDF8, stop:0.5 #2563EB, stop:1 #818CF8);
                border: 1px solid rgba(255, 255, 255, 140);
            }
            QPushButton#primaryBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #0284C7, stop:1 #4F46E5);
            }
            QPushButton#primaryBtn:disabled {
                background: rgba(255, 255, 255, 15);
                color: rgba(255, 255, 255, 70);
                border: 1px solid rgba(255, 255, 255, 20);
            }
            /* 下拉框 */
            QComboBox {
                padding: 0px 12px;
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 8px;
                background-color: rgba(15, 23, 42, 120);
                color: #FFFFFF;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: rgba(255, 255, 255, 70);
                background-color: rgba(15, 23, 42, 150);
            }
            QComboBox:focus {
                border: 1.5px solid #38BDF8;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid rgba(255, 255, 255, 45);
                selection-background-color: #0284C7;
                padding: 4px;
                outline: none;
            }
            /* 进度条 */
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 5px;
                background-color: rgba(15, 23, 42, 140);
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #00F2FE, stop:0.5 #4FACFE, stop:1 #A855F7);
                border-radius: 4px;
            }
            QLabel#statusLabel {
                color: #94A3B8;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#percentLabel {
                color: #38BDF8;
                font-size: 13px;
                font-weight: 700;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(34, 28, 34, 28)
        main_layout.setSpacing(12)

        # ==================== 1. 顶部标题区 ====================
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        
        title_row = QHBoxLayout()
        title_lbl = QLabel("SD Copy Hub")
        title_lbl.setObjectName("titleLabel")
        badge_lbl = QLabel("AERO GLASS v2.2")
        badge_lbl.setObjectName("badgeLabel")
        title_row.addWidget(title_lbl)
        title_row.addSpacing(10)
        title_row.addWidget(badge_lbl)
        title_row.addStretch()

        sub_lbl = QLabel("智能场次时间聚类 · 视频自动重命名 · SHA-256 高速流式校验")
        sub_lbl.setObjectName("subtitleLabel")
        
        header_layout.addLayout(title_row)
        header_layout.addWidget(sub_lbl)
        main_layout.addLayout(header_layout)

        main_layout.addSpacing(6)

        # 读取历史配置
        last_img_path = self.settings.value("img_path", str(Path.home() / "Pictures"))
        last_vid_path = self.settings.value("vid_path", str(Path.home() / "Movies"))
        last_sd_path = self.settings.value("sd_path", "/Volumes/Untitled")

        # ==================== 2. 第一张毛玻璃卡片：存储与路径设置 ====================
        lbl_sec1 = QLabel("STORAGE & PATHS · 存储路径配置")
        lbl_sec1.setObjectName("sectionHeader")
        main_layout.addWidget(lbl_sec1)

        path_card = GlassCard()
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(22, 18, 22, 20)
        path_layout.setSpacing(12)

        # 第一行：SD卡根目录
        sd_row = QHBoxLayout()
        sd_row.setSpacing(14)
        lbl_sd = QLabel("SD 卡根目录")
        lbl_sd.setFixedWidth(85)
        self.sd_input = QLineEdit(last_sd_path)
        self.sd_input.setFixedHeight(38)
        self.sd_input.textChanged.connect(self.on_sd_path_changed)
        self.btn_sd = QPushButton("选择存储卡")
        self.btn_sd.setFixedSize(112, 38)
        self.btn_sd.setCursor(Qt.PointingHandCursor)
        self.btn_sd.clicked.connect(self.select_sd_dir)
        sd_row.addWidget(lbl_sd)
        sd_row.addWidget(self.sd_input, 1)
        sd_row.addWidget(self.btn_sd)
        path_layout.addLayout(sd_row)

        path_layout.addWidget(self.create_divider())

        # 第二行：照片归档库
        img_row = QHBoxLayout()
        img_row.setSpacing(14)
        lbl_img = QLabel("照片归档库")
        lbl_img.setFixedWidth(85)
        self.img_input = QLineEdit(last_img_path)
        self.img_input.setFixedHeight(38)
        self.btn_img = QPushButton("浏览目录")
        self.btn_img.setFixedSize(112, 38)
        self.btn_img.setCursor(Qt.PointingHandCursor)
        self.btn_img.clicked.connect(self.select_img_dir)
        img_row.addWidget(lbl_img)
        img_row.addWidget(self.img_input, 1)
        img_row.addWidget(self.btn_img)
        path_layout.addLayout(img_row)

        # 第三行：视频归档库
        vid_row = QHBoxLayout()
        vid_row.setSpacing(14)
        lbl_vid = QLabel("视频归档库")
        lbl_vid.setFixedWidth(85)
        self.vid_input = QLineEdit(last_vid_path)
        self.vid_input.setFixedHeight(38)
        self.btn_vid = QPushButton("浏览目录")
        self.btn_vid.setFixedSize(112, 38)
        self.btn_vid.setCursor(Qt.PointingHandCursor)
        self.btn_vid.clicked.connect(self.select_vid_dir)
        vid_row.addWidget(lbl_vid)
        vid_row.addWidget(self.vid_input, 1)
        vid_row.addWidget(self.btn_vid)
        path_layout.addLayout(vid_row)

        main_layout.addWidget(path_card)

        main_layout.addSpacing(6)

        # ==================== 3. 第二张毛玻璃卡片：场次与归档规则 ====================
        lbl_sec2 = QLabel("SESSION & RULES · 拍摄场次与过滤")
        lbl_sec2.setObjectName("sectionHeader")
        main_layout.addWidget(lbl_sec2)

        rule_card = GlassCard()
        rule_layout = QVBoxLayout(rule_card)
        rule_layout.setContentsMargins(22, 18, 22, 20)
        rule_layout.setSpacing(12)

        # 第一行：活动名称
        event_row = QHBoxLayout()
        event_row.setSpacing(14)
        lbl_event = QLabel("活动后缀名")
        lbl_event.setFixedWidth(85)
        self.event_input = QLineEdit()
        self.event_input.setFixedHeight(38)
        self.event_input.setPlaceholderText("选填，自动拼接到日期文件夹后（如：公园外拍、人像写真）")
        event_row.addWidget(lbl_event)
        event_row.addWidget(self.event_input, 1)
        rule_layout.addLayout(event_row)

        rule_layout.addWidget(self.create_divider())

        # 第二行：拍摄场次与文件类型
        filter_row = QHBoxLayout()
        filter_row.setSpacing(14)
        lbl_session = QLabel("拍摄时间段")
        lbl_session.setFixedWidth(85)
        
        self.date_combo = QComboBox()
        self.date_combo.setFixedHeight(38)
        self.date_combo.addItem("全部日期")
        
        self.btn_scan = QPushButton("⚡ 智能识别场次")
        self.btn_scan.setObjectName("scanBtn")
        self.btn_scan.setFixedSize(136, 38)
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self.scan_sd)

        lbl_filter = QLabel("媒体过滤")
        lbl_filter.setFixedWidth(60)
        self.type_combo = QComboBox()
        self.type_combo.setFixedHeight(38)
        self.type_combo.addItems(["全部文件", "仅图片", "仅视频"])

        filter_row.addWidget(lbl_session)
        filter_row.addWidget(self.date_combo, 2)
        filter_row.addWidget(self.btn_scan)
        filter_row.addSpacing(12)
        filter_row.addWidget(lbl_filter)
        filter_row.addWidget(self.type_combo, 1)
        rule_layout.addLayout(filter_row)

        main_layout.addWidget(rule_card)

        # ==================== 4. 底部状态与执行区 ====================
        main_layout.addStretch(1)

        status_box = QVBoxLayout()
        status_box.setSpacing(8)
        
        status_text_row = QHBoxLayout()
        self.status_label = QLabel("准备就绪，等待导入指令")
        self.status_label.setObjectName("statusLabel")
        self.percent_label = QLabel("")
        self.percent_label.setObjectName("percentLabel")
        status_text_row.addWidget(self.status_label)
        status_text_row.addStretch()
        status_text_row.addWidget(self.percent_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)

        status_box.addLayout(status_text_row)
        status_box.addWidget(self.progress_bar)
        main_layout.addLayout(status_box)

        main_layout.addSpacing(6)

        self.start_btn = QPushButton("开始安全导入")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setFixedHeight(48)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_task)
        main_layout.addWidget(self.start_btn)

        self.setLayout(main_layout)

    def on_sd_path_changed(self):
        self.cached_files = []
        self.date_combo.clear()
        self.date_combo.addItem("全部日期")

    def select_img_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择图片保存目录", self.img_input.text())
        if directory:
            self.img_input.setText(directory)
            self.settings.setValue("img_path", directory)

    def select_vid_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择视频保存目录", self.vid_input.text())
        if directory:
            self.vid_input.setText(directory)
            self.settings.setValue("vid_path", directory)

    def select_sd_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择 SD 卡根目录", self.sd_input.text())
        if directory:
            self.sd_input.setText(directory)
            self.settings.setValue("sd_path", directory)
            self.scan_sd()

    def set_ui_locked(self, locked: bool):
        self.start_btn.setEnabled(not locked)
        self.btn_scan.setEnabled(not locked)
        self.btn_sd.setEnabled(not locked)
        self.btn_img.setEnabled(not locked)
        self.btn_vid.setEnabled(not locked)
        self.date_combo.setEnabled(not locked)
        self.type_combo.setEnabled(not locked)

    def scan_sd(self):
        sd_path = self.sd_input.text().strip()
        if not os.path.exists(sd_path):
            self.status_label.setText("⚠️ SD 卡路径不存在，请检查存储卡是否已挂载")
            return

        self.set_ui_locked(True)
        self.status_label.setText("🔍 正在扫描 SD 卡并聚类拍摄场次...")
        self.progress_bar.setRange(0, 0)
        
        self.scan_thread = ScanThread(sd_path)
        self.scan_thread.scan_done_signal.connect(self.on_scan_done)
        self.scan_thread.start()

    def on_scan_done(self, groups, cached_files):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.set_ui_locked(False)

        self.cached_files = cached_files
        self.date_combo.clear()
        self.date_combo.addItem("全部日期")
        self.date_combo.addItems(groups)
        
        if groups:
            self.status_label.setText(f"✅ 识别完成：共发现 {len(groups)} 个拍摄场次（总计 {len(cached_files)} 个媒体文件）")
        else:
            self.status_label.setText("提示：未在 SD 卡中发现支持的图片或视频文件")

    def on_progress_update(self, val):
        self.progress_bar.setValue(val)
        self.percent_label.setText(f"{val}%")

    def on_copy_finished(self, msg):
        self.set_ui_locked(False)
        self.status_label.setText(msg)

    def start_task(self):
        sd_path = self.sd_input.text().strip()
        if not os.path.exists(sd_path):
            self.status_label.setText("⚠️ 找不到 SD 卡路径，请确认存储卡已插入")
            return

        self.settings.setValue("img_path", self.img_input.text())
        self.settings.setValue("vid_path", self.vid_input.text())
        self.settings.setValue("sd_path", sd_path)

        self.set_ui_locked(True)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("🚀 正在初始化高速导入引擎...")

        self.copy_thread = CopyThread(
            self.img_input.text().strip(),
            self.vid_input.text().strip(),
            sd_path,
            self.event_input.text(),
            self.date_combo.currentText(),
            self.type_combo.currentText(),
            self.cached_files
        )
        self.copy_thread.progress_signal.connect(self.on_progress_update)
        self.copy_thread.status_signal.connect(self.status_label.setText)
        self.copy_thread.finished_signal.connect(self.on_copy_finished)
        self.copy_thread.start()


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec_())
