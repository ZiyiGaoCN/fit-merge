# FIT File Merge Project

这个项目用于合并多个 Garmin FIT 文件，并提供 FIT 与 CSV 格式之间的转换工具。

## 🌐 Web 界面（新增）

提供基于 Flask 的 Web 前端，支持拖拽上传两个 FIT 文件并合并下载。

### 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web 服务
python web_app.py
```

然后打开浏览器访问 **http://localhost:5000**

### 功能特点

- 🎨 现代化深色 UI
- 📁 支持拖拽上传
- ⚡ 一键合并下载
- 🔍 自动检测 Java 和 FitCSVTool 环境

### 前置要求

- **Python 3.8+**
- **Java Runtime** (用于 FitCSVTool.jar)
- FitSDK 已包含在项目中

## 命令行使用

### 合并两个 FIT 文件

```bash
python entrypoint.py ride1.fit ride2.fit -o merged.fit
```

### FIT 与 CSV 转换

```bash
# FIT 转 CSV
java -jar FitSDK/java/FitCSVTool.jar -b input.fit output.csv

# CSV 转 FIT
java -jar FitSDK/java/FitCSVTool.jar -c input.csv output.fit
```

## 文件夹结构

| 目录 | 说明 |
|------|------|
| `FitSDK/` | 官方 Garmin FIT SDK（含 FitCSVTool.jar） |
| `tools/` | 自定义工具脚本（CSV 合并、转换、修复） |
| `original_files/` | 原始和合并后的 FIT 文件 |
| `converted_files/` | CSV 转换结果 |

## 核心文件

- **`entrypoint.py`** — 主合并逻辑（CLI 入口）
- **`web_app.py`** — Web 前端（Flask）
- **`tools/csv_merger.py`** — CSV 合并工具
- **`tools/fit_to_csv_converter.py`** — FIT→CSV 转换器
- **`tools/merge_official_csv.py`** — 官方 CSV 格式合并

## 合并流程

1. FIT → CSV（使用官方 FitCSVTool.jar）
2. 合并两个 CSV（按消息类型优先级 + 时间戳排序，record 去重）
3. 修复 CSV 格式（处理 pandas 输出的兼容性问题）
4. CSV → FIT（使用官方 FitCSVTool.jar）

## 工具特色

1. **官方兼容性** — 使用 Garmin 官方 FIT SDK 确保 100% 兼容
2. **完整数据保留** — 保留所有消息类型和元数据
3. **智能合并** — 自动排序和去重
4. **格式修复** — 自动处理 pandas 格式问题
5. **Web 界面** — 无需命令行，浏览器操作即可

## License

MIT
