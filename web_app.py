#!/usr/bin/env python3
"""
FIT File Merger - Web 前端
基于 Flask 的 Web 界面，上传两个 FIT 文件并合并下载。

使用方法:
    pip install flask pandas
    python web_app.py

然后打开浏览器访问 http://localhost:5000
"""

import os
import uuid
import tempfile
import shutil
from flask import Flask, request, send_file, jsonify, render_template_string

from entrypoint import merge_fit_files, find_fit_csv_tool, check_java

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FIT 文件合并工具</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e0e0e0;
        }

        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            width: 90%;
            max-width: 600px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        h1 {
            text-align: center;
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #ff6b6b, #ffa502);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle {
            text-align: center;
            color: #888;
            font-size: 14px;
            margin-bottom: 30px;
        }

        .upload-zone {
            border: 2px dashed rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 16px;
            position: relative;
        }

        .upload-zone:hover, .upload-zone.dragover {
            border-color: #ffa502;
            background: rgba(255, 165, 2, 0.05);
        }

        .upload-zone.has-file {
            border-color: #2ed573;
            background: rgba(46, 213, 115, 0.05);
        }

        .upload-zone .icon {
            font-size: 36px;
            margin-bottom: 10px;
        }

        .upload-zone .label {
            font-size: 16px;
            font-weight: 500;
        }

        .upload-zone .hint {
            font-size: 12px;
            color: #888;
            margin-top: 6px;
        }

        .upload-zone .filename {
            font-size: 14px;
            color: #2ed573;
            margin-top: 8px;
            font-weight: 500;
        }

        .upload-zone input[type="file"] {
            position: absolute;
            inset: 0;
            opacity: 0;
            cursor: pointer;
        }

        .btn-merge {
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            background: linear-gradient(135deg, #ff6b6b, #ffa502);
            color: white;
            transition: all 0.3s ease;
            margin-top: 20px;
            letter-spacing: 1px;
        }

        .btn-merge:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255, 107, 107, 0.3);
        }

        .btn-merge:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            transform: none;
        }

        .status {
            margin-top: 20px;
            padding: 16px;
            border-radius: 10px;
            font-size: 14px;
            display: none;
            text-align: center;
        }

        .status.loading {
            display: block;
            background: rgba(255, 165, 2, 0.1);
            border: 1px solid rgba(255, 165, 2, 0.3);
            color: #ffa502;
        }

        .status.success {
            display: block;
            background: rgba(46, 213, 115, 0.1);
            border: 1px solid rgba(46, 213, 115, 0.3);
            color: #2ed573;
        }

        .status.error {
            display: block;
            background: rgba(255, 71, 87, 0.1);
            border: 1px solid rgba(255, 71, 87, 0.3);
            color: #ff4757;
        }

        .spinner {
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255, 165, 2, 0.3);
            border-top-color: #ffa502;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            vertical-align: middle;
            margin-right: 8px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .footer {
            text-align: center;
            margin-top: 24px;
            font-size: 12px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚴 FIT 文件合并工具</h1>
        <p class="subtitle">上传两个 Garmin FIT 文件，合并为一个活动文件</p>

        <form id="mergeForm" enctype="multipart/form-data">
            <div class="upload-zone" id="zone1">
                <div class="icon">📄</div>
                <div class="label">第一个 FIT 文件</div>
                <div class="hint">点击选择或拖拽文件到此处</div>
                <div class="filename" id="name1"></div>
                <input type="file" name="file1" id="file1" accept=".fit">
            </div>

            <div class="upload-zone" id="zone2">
                <div class="icon">📄</div>
                <div class="label">第二个 FIT 文件</div>
                <div class="hint">点击选择或拖拽文件到此处</div>
                <div class="filename" id="name2"></div>
                <input type="file" name="file2" id="file2" accept=".fit">
            </div>

            <button type="submit" class="btn-merge" id="btnMerge" disabled>
                合并文件
            </button>
        </form>

        <div class="status" id="status"></div>

        <div class="footer">
            Powered by Garmin FIT SDK · 支持所有 Garmin 设备的 FIT 文件
        </div>
    </div>

    <script>
        const file1 = document.getElementById('file1');
        const file2 = document.getElementById('file2');
        const zone1 = document.getElementById('zone1');
        const zone2 = document.getElementById('zone2');
        const name1 = document.getElementById('name1');
        const name2 = document.getElementById('name2');
        const btn = document.getElementById('btnMerge');
        const status = document.getElementById('status');
        const form = document.getElementById('mergeForm');

        function updateBtn() {
            btn.disabled = !(file1.files.length && file2.files.length);
        }

        function setupZone(zone, input, nameEl) {
            input.addEventListener('change', () => {
                if (input.files.length) {
                    nameEl.textContent = '✅ ' + input.files[0].name;
                    zone.classList.add('has-file');
                } else {
                    nameEl.textContent = '';
                    zone.classList.remove('has-file');
                }
                updateBtn();
            });

            ['dragenter', 'dragover'].forEach(e => {
                zone.addEventListener(e, ev => {
                    ev.preventDefault();
                    zone.classList.add('dragover');
                });
            });

            ['dragleave', 'drop'].forEach(e => {
                zone.addEventListener(e, ev => {
                    ev.preventDefault();
                    zone.classList.remove('dragover');
                });
            });

            zone.addEventListener('drop', ev => {
                const files = ev.dataTransfer.files;
                if (files.length) {
                    input.files = files;
                    input.dispatchEvent(new Event('change'));
                }
            });
        }

        setupZone(zone1, file1, name1);
        setupZone(zone2, file2, name2);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            btn.disabled = true;
            btn.textContent = '合并中...';
            status.className = 'status loading';
            status.innerHTML = '<span class="spinner"></span>正在合并 FIT 文件，请稍候...';

            const formData = new FormData();
            formData.append('file1', file1.files[0]);
            formData.append('file2', file2.files[0]);

            try {
                const resp = await fetch('/merge', {
                    method: 'POST',
                    body: formData
                });

                if (resp.ok) {
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'merged.fit';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);

                    status.className = 'status success';
                    status.textContent = '✅ 合并成功！文件已开始下载。';
                } else {
                    const data = await resp.json();
                    status.className = 'status error';
                    status.textContent = '❌ ' + (data.error || '合并失败，请重试。');
                }
            } catch (err) {
                status.className = 'status error';
                status.textContent = '❌ 网络错误: ' + err.message;
            } finally {
                btn.disabled = false;
                btn.textContent = '合并文件';
                updateBtn();
            }
        });
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/health')
def health():
    """检查运行环境"""
    java_ok = check_java()
    tool_jar = find_fit_csv_tool()
    return jsonify({
        'java': java_ok,
        'fit_csv_tool': tool_jar is not None,
        'fit_csv_tool_path': tool_jar,
    })


@app.route('/merge', methods=['POST'])
def merge():
    # 检查环境
    if not check_java():
        return jsonify({'error': '服务器未安装 Java，无法进行 FIT 文件转换。'}), 500

    tool_jar = find_fit_csv_tool()
    if not tool_jar:
        return jsonify({'error': '找不到 FitCSVTool.jar，请检查 FitSDK 是否正确部署。'}), 500

    # 检查上传文件
    if 'file1' not in request.files or 'file2' not in request.files:
        return jsonify({'error': '请上传两个 FIT 文件。'}), 400

    file1 = request.files['file1']
    file2 = request.files['file2']

    if not file1.filename or not file2.filename:
        return jsonify({'error': '请选择两个 FIT 文件。'}), 400

    for f in [file1, file2]:
        if not f.filename.lower().endswith('.fit'):
            return jsonify({'error': f'文件 {f.filename} 不是 .fit 格式。'}), 400

    # 创建临时目录处理文件
    work_dir = tempfile.mkdtemp(prefix='fit_web_')
    try:
        fit1_path = os.path.join(work_dir, 'file1.fit')
        fit2_path = os.path.join(work_dir, 'file2.fit')
        output_path = os.path.join(work_dir, 'merged.fit')

        file1.save(fit1_path)
        file2.save(fit2_path)

        # 执行合并
        merge_fit_files(fit1_path, fit2_path, output_path, tool_jar)

        if not os.path.exists(output_path):
            return jsonify({'error': '合并后未生成输出文件。'}), 500

        # 读取结果返回
        return send_file(
            output_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name='merged.fit'
        )

    except Exception as e:
        return jsonify({'error': f'合并失败: {str(e)}'}), 500

    finally:
        # 延迟清理（send_file 需要文件存在）
        # Flask 会在请求结束后处理，这里用 after_request 不太方便
        # 简单方案：不立即清理，依赖系统 tmp 清理
        pass


if __name__ == '__main__':
    print("=" * 50)
    print("FIT 文件合并工具 - Web 界面")
    print("=" * 50)

    # 环境检查
    if not check_java():
        print("⚠️  警告: 未检测到 Java，合并功能将不可用。")
        print("   请安装 Java Runtime: https://adoptium.net/")
    else:
        print("✅ Java: 已安装")

    tool = find_fit_csv_tool()
    if tool:
        print(f"✅ FitCSVTool: {tool}")
    else:
        print("⚠️  警告: 找不到 FitCSVTool.jar")

    print()
    print("🌐 打开浏览器访问: http://localhost:5000")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=False)
