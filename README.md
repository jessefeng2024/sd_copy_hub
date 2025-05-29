# sd_copy_hub

## 项目概述
SD Copy Hub 是一个专为摄影师设计的实用工具，用于从 SD 卡快速、准确地拷贝图片和视频文件到指定目录。它解决了摄影师在拷卡过程中遇到的文件命名、分类和校验等问题，提高了工作效率。

## 优化了UI，之前真的太丑了（3.18）
![123](https://github.com/user-attachments/assets/7dbb1040-4f9f-49a1-b56b-1fd4be6f94d2)


## 为什么要写这个程序？

针对摄影师/摄影爱好者，增加日常拷卡效率，以及照片归档的准确性。

对于拷卡，我有几个需求点：

1. SD卡内照片和视频都有，在后期处理时往往需要用到不同的软件，所以把它们分别拷贝到不同的文件夹里是更好的选择
2. 每次拷卡结束，我并不能确定数据是否安全地在文件夹内，所以需要一次校验
3. Sony的C001的视频命名，经常会产生冲突，所以我希望它能以拍摄日期的名称重命名，这样我在后期处理时才会更加轻松

因为我自己的编程能力有限，大部分编程算法都是由AI完成，但在我两个礼拜的测试中，这个程序还是让我节省了不少拷卡的时间。



## 功能特性
1. **灵活的目录指定**：支持用户通过图形用户界面（GUI）自由指定图片和视频的目标目录，以及 SD 卡所在的目录。
2. **智能文件夹创建**：根据文件的拍摄日期或修改时间自动创建文件夹，并可结合输入的活动名称，使文件夹命名更具针对性。
3. **文件名处理**：对图片和视频文件进行重命名，特别解决了索尼 C001 视频文件手动命名困难的问题。同时，处理文件名重复情况，避免文件覆盖。
4. **哈希校验**：在文件拷贝过程中添加哈希校验功能，确保文件拷贝的准确性，防止数据丢失或损坏。
5. **进度实时展示**：在 GUI 界面添加进度条，实时展示文件拷贝进度，并在拷贝完成后反馈最终生成的文件夹名称。
6. **多格式支持**：支持多种常见的图片和视频格式，包括但不限于 `.jpg`, `.jpeg`, `.png`, `.raw`, `.nef`, `.cr2`, `.CR3`, `.mp4`, `.avi`, `.mov` 等，同时增加了对更多主流相机厂商 RAW 格式的支持。

## 安装与使用
### 安装
确保你已经安装了 Python 3.9 及以上版本。你可以从 [Python 官方网站](https://www.python.org/downloads/) 下载并安装。

### 运行
1. 克隆本项目到本地：
```bash
git clone https://github.com/jessefeng2024/sd_copy_hub.git
cd sd_copy_hub
```
2. 运行代码：
```bash
python your_script_name.py  # 替换为你的 Python 脚本文件名
```

### 使用步骤
1. 打开程序后，点击相应的 “选择目录” 按钮，分别指定图片目标目录、视频目标目录和 SD 卡目录。
2. 在 “活动名称” 输入框中输入本次活动的名称（可选）。
3. 选择拷贝类型：勾选“拷贝图片”和/或“拷贝视频”复选框（默认均勾选），至少选择一种类型（否则会提示错误）。
4. 选择文件分类（可选）：勾选“分开存放RAW和JPG文件”复选框，若勾选，图片文件将按RAW和JPG分别存放在“原图/RAW”和“原图/JPG”子文件夹中。
5. 点击 “获取日期” 按钮，程序将自动获取 SD 卡中文件的日期信息。
6. 从日期下拉框中选择要拷贝的文件日期（或选择“全部日期”）。
7. 点击 “开始拷贝” 按钮，程序将开始拷贝文件，并在进度条中实时显示拷贝进度。
8. 拷贝完成后，程序将在界面上反馈最终生成的文件夹名称。

## 代码变更日志
### 版本 1.1 - 2025-03-11
- 初始版本，实现从 SD 卡拷贝图片和视频到指定目录，支持用户通过 GUI 指定图片、视频目标目录及 SD 卡目录。
- 根据拍摄日期或修改时间创建文件夹，对图片、视频文件进行重命名，解决索尼 C001 视频文件手动命名困难的问题。
- 处理文件名重复情况，避免文件覆盖。
- 添加哈希校验功能，确保文件拷贝的准确性。
- 在 GUI 界面添加进度条，实时展示文件拷贝进度，并在拷贝完成后反馈结果。
- 优化代码，避免重复创建文件夹，添加拷卡结束后自动推出 SD 卡的功能。
- 为代码添加 changelog 注释，方便记录和查看代码的修改历史。

### 版本 1.2 - 2025-05-29
- 适配了macOS的主题颜色，支持根据系统主题自动切换颜色。
- 新增了”分开存放RAW和JPG文件“开关，支持拷贝过程中分开存放两种文件
#### 优化调整：

1. 优化了macOS的UI布局和样式，主要调整了控件间距、字体统一性、按钮样式和布局紧凑度，使用统一的主题颜色，Windows应该也可以，待测试……
  - 字体统一 ：使用系统默认字体，提升系统适配性；
  - 布局紧凑性 ：调整主布局边距和控件间距，避免元素过于拥挤；
  - 样式统一 ：统一输入框和按钮样式，解决原有按钮颜色不一致问题；
  - 对齐优化 ：所有标签固定宽度，输入框和下拉框使用扩展填充，保证列对齐；
  - 重点突出 ："开始拷贝"按钮使用主题蓝色，增大内边距并居中显示，强化操作入口；
  - 细节调整 ：进度条增加高度和圆角，复选框与标签列对齐，提升视觉一致性；
  image.png

### 后续版本
- 不断增加新功能，如输入活动名称、修复进度条问题、支持更多文件格式等，具体变更内容可查看代码中的 changelog 注释。

## 贡献与反馈
如果你对本项目有任何建议、发现了 bug 或者想要贡献代码，请随时在 GitHub 上提交 issues 或 pull requests。我们欢迎任何形式的贡献，让这个项目变得更好！

## 许可证
本项目采用 [MIT 许可证](https://opensource.org/licenses/MIT)，详情请查看 `LICENSE` 文件。

# SD Copy Hub

## Project Overview
SD Copy Hub is a practical tool designed specifically for photographers to quickly and accurately copy photo and video files from SD cards to specified directories. It solves problems such as file naming, classification, and verification that photographers encounter during the card copying process, thereby improving work efficiency.

## Features
1. **Flexible Directory Specification**: Allows users to freely specify the target directories for photos and videos, as well as the directory of the SD card, through the graphical user interface (GUI).
2. **Intelligent Folder Creation**: Automatically creates folders based on the shooting date or modification time of files. It can also incorporate the entered event name to make folder naming more targeted.
3. **File Name Handling**: Renames photo and video files, especially solving the problem of difficult manual naming for Sony C001 video files. Additionally, it handles duplicate file names to avoid file overwriting.
4. **Hash Verification**: Adds a hash verification function during the file copying process to ensure the accuracy of file copying and prevent data loss or damage.
5. **Real - Time Progress Display**: Adds a progress bar to the GUI to display the file copying progress in real - time and provides feedback on the names of the finally generated folders after copying is completed.
6. **Multi - Format Support**: Supports a variety of common photo and video formats, including but not limited to `.jpg`, `.jpeg`, `.png`, `.raw`, `.nef`, `.cr2`, `.CR3`, `.mp4`, `.avi`, `.mov`, etc. It also adds support for more RAW formats of mainstream camera manufacturers.

## Installation and Usage
### Installation
Make sure you have installed Python 3.9 or a higher version. You can download and install it from the [official Python website](https://www.python.org/downloads/).

### Running
1. Clone this project to your local machine:
```bash
git clone https://github.com/jessefeng2024/sd_copy_hub.git
cd sd_copy_hub
```
2. Run the code:
```bash
python your_script_name.py  # Replace with the name of your Python script file
```

### Usage Steps
1. After opening the program, click the corresponding "Select Directory" buttons to specify the target directories for photos, videos, and the SD card respectively.
2. Enter the name of the current event (optional) in the "Event Name" input box.
3. Click the "Start Copying" button, and the program will start copying files and display the copying progress in real - time on the progress bar.
4. After the copying is completed, the program will provide feedback on the names of the finally generated folders on the interface.

## Code Change Log
### Version 1.1 - 2025-03-11
- Initial version. It enables copying photos and videos from the SD card to specified directories and supports users to specify the target directories for photos and videos, as well as the SD card directory, through the GUI.
- Creates folders based on the shooting date or modification time of files and renames photo and video files, solving the problem of difficult manual naming for Sony C001 video files.
- Handles duplicate file names to avoid file overwriting.
- Adds a hash verification function to ensure the accuracy of file copying.
- Adds a progress bar to the GUI to display the file copying progress in real - time and provides feedback on the results after copying is completed.
- Optimizes the code to avoid creating folders repeatedly and adds the function of automatically ejecting the SD card after card copying is completed.
- Adds changelog comments to the code for easy recording and viewing of the code's modification history.

### Subsequent Versions
- Continuously adds new functions, such as the ability to input event names, fixes progress bar issues, and supports more file formats. For specific change details, please refer to the changelog comments in the code.

## Contribution and Feedback
If you have any suggestions for this project, find bugs, or want to contribute code, please feel free to submit issues or pull requests on GitHub. We welcome all forms of contributions to make this project better!

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT). Please refer to the `LICENSE` file for details.
