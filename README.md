# FIT File Merge Project

这个项目用于合并多个FIT文件，并提供FIT与CSV格式之间的转换工具。

## 文件夹结构

### 📁 **FitSDK/**
官方Garmin FIT SDK解压文件
- `java/` - Java工具，包含官方FitCSVTool.jar
- `c/`, `cpp/`, `cs/`, `py/`, `swift/` - 各种编程语言的SDK
- `examples/` - 示例文件
- `config.csv`, `Profile.xlsx` - 配置和协议文件

### 📁 **original_files/**
原始和最终的FIT文件
- `ride-0-2025-07-19-09-41-59.fit` - 第一个骑行文件
- `ride-0-2025-07-19-14-53-44.fit` - 第二个骑行文件
- `gpxt_result.fit` - 参考文件
- `final_merged.fit` - 最终合并结果

### 📁 **converted_files/**
转换生成的CSV文件
- `*.csv` - 各种FIT到CSV转换的结果

### 📁 **tools/**
自定义开发的工具脚本
- `csv_merger.py` - CSV合并工具
- `fit_to_csv_converter.py` - FIT到CSV转换器
- `complete_csv_to_fit.py` - 完整的CSV到FIT转换器
- `merge_official_csv.py` - 官方CSV格式合并工具
- `fix_csv_format.py` - CSV格式修复工具
- `binary_analyzer.py` - 二进制结构分析工具

### 📁 **temp_files/**
临时文件和压缩包
- `*.zip` - 下载的压缩包
- `*.txt` - 临时文本文件

### 📁 **fit_env/**
Python虚拟环境
- 包含fitparse, pandas等依赖

## 使用方法

### 1. 使用官方工具转换FIT到CSV
```bash
java -jar FitSDK/java/FitCSVTool.jar -b input.fit output.csv
```

### 2. 转换CSV回FIT格式
```bash
java -jar FitSDK/java/FitCSVTool.jar -c input.csv output.fit
```

### 3. 合并两个FIT文件
1. 将FIT文件转换为CSV
2. 使用merge_official_csv.py合并CSV
3. 修复格式后转换回FIT

## 最终结果

最成功的合并结果在 `original_files/final_merged.fit`：
- 2,919条记录
- 包含所有必要的消息类型
- 107,198字节
- 时间范围：2025-07-19 01:41:58 到 07:18:47

## 工具特色

1. **官方兼容性** - 使用Garmin官方FIT SDK确保100%兼容
2. **完整数据保留** - 保留所有消息类型和元数据
3. **智能合并** - 自动排序和去重
4. **格式修复** - 自动处理pandas格式问题