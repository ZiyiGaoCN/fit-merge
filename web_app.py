#!/usr/bin/env python3
"""
FIT File Merger - Web 前端
基于 Flask 的 Web 界面，上传两个 FIT 文件并合并下载。
支持轨迹预览（合并前双色对比 + 合并后结果）。

使用方法:
    pip install flask pandas fitparse matplotlib
    python web_app.py

然后打开浏览器访问 http://localhost:5000
"""

import os
import io
import base64
import tempfile
import shutil
from flask import Flask, request, send_file, jsonify, render_template_string

from entrypoint import merge_fit_files, find_fit_csv_tool, check_java

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max


def extract_gps_from_fit(fit_path):
    """从 FIT 文件中提取 GPS 坐标"""
    import fitparse

    lats = []
    lons = []

    fitfile = fitparse.FitFile(fit_path)
    for record in fitfile.get_messages('record'):
        lat = None
        lon = None
        for field in record:
            if field.name == 'position_lat' and field.value is not None:
                lat = field.value * (180 / 2**31)
            elif field.name == 'position_long' and field.value is not None:
                lon = field.value * (180 / 2**31)
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)

    return lats, lons


def _get_cn_font():
    """获取中文字体"""
    from matplotlib import font_manager
    font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
    ]
    for p in font_paths:
        if os.path.exists(p):
            return font_manager.FontProperties(fname=p)
    return None


def generate_track_image(tracks, labels=None, colors=None, title=None):
    """
    生成轨迹预览图，返回 base64 PNG。
    tracks: list of (lats, lons) tuples
    labels: list of track labels
    colors: list of track colors
    title: optional title
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    cn_font = _get_cn_font()

    if colors is None:
        colors = ['#ff6b6b', '#4ecdc4', '#ffa502', '#a55eea']
    if labels is None:
        labels = [f'Track {i+1}' for i in range(len(tracks))]

    fig, ax = plt.subplots(1, 1, figsize=(6, 5), dpi=120)
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    has_data = False
    for i, (lats, lons) in enumerate(tracks):
        if lats and lons:
            has_data = True
            c = colors[i % len(colors)]
            ax.plot(lons, lats, color=c, linewidth=2, alpha=0.85, label=labels[i])
            # Start marker
            ax.plot(lons[0], lats[0], 'o', color=c, markersize=8, zorder=5,
                    markeredgecolor='white', markeredgewidth=1.5)
            # End marker
            ax.plot(lons[-1], lats[-1], 's', color=c, markersize=8, zorder=5,
                    markeredgecolor='white', markeredgewidth=1.5)

    if not has_data:
        ax.text(0.5, 0.5, '无 GPS 数据', transform=ax.transAxes,
                ha='center', va='center', color='#888', fontsize=14,
                fontproperties=cn_font)

    ax.set_aspect('equal')
    ax.tick_params(colors='#666', labelsize=7)
    for spine in ax.spines.values():
        spine.set_color('#333')
    ax.grid(True, alpha=0.12, color='#555')

    if has_data and len(tracks) > 0:
        legend_kwargs = dict(fontsize=9, loc='upper left',
                             facecolor='#1a1a2e', edgecolor='#444',
                             labelcolor='#ddd', framealpha=0.9)
        if cn_font:
            legend_kwargs['prop'] = cn_font
        ax.legend(**legend_kwargs)

    if title:
        ax.set_title(title, color='#ccc', fontsize=11, pad=10,
                     fontproperties=cn_font)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


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
            padding: 20px;
        }

        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            width: 90%;
            max-width: 650px;
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

        .upload-zone .icon { font-size: 36px; margin-bottom: 10px; }
        .upload-zone .label { font-size: 16px; font-weight: 500; }
        .upload-zone .hint { font-size: 12px; color: #888; margin-top: 6px; }

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

        .track-preview {
            margin-top: 16px;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: #16213e;
            display: none;
        }

        .track-preview.show { display: block; }

        .track-preview img { width: 100%; display: block; }

        .track-preview .track-label {
            text-align: center;
            font-size: 12px;
            color: #888;
            padding: 8px;
            background: rgba(255, 255, 255, 0.03);
        }

        .track-preview .track-loading {
            padding: 30px;
            text-align: center;
            color: #888;
            font-size: 13px;
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

        .result-section {
            margin-top: 24px;
            display: none;
        }

        .result-section.show { display: block; }

        .result-track {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(46, 213, 115, 0.3);
        }

        .result-track img { width: 100%; display: block; }

        .result-label {
            text-align: center;
            font-size: 13px;
            color: #2ed573;
            padding: 8px;
            background: rgba(46, 213, 115, 0.05);
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

        @keyframes spin { to { transform: rotate(360deg); } }

        .color-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 4px;
            vertical-align: middle;
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

            <!-- Combined preview of both tracks -->
            <div class="track-preview" id="previewSection">
                <div class="track-loading" id="previewLoading">
                    <span class="spinner"></span>正在生成轨迹预览...
                </div>
                <img id="previewImg" src="" alt="轨迹预览" style="display:none;">
                <div class="track-label" id="previewLabel"></div>
            </div>

            <button type="submit" class="btn-merge" id="btnMerge" disabled>
                合并文件
            </button>
        </form>

        <div class="status" id="status"></div>

        <!-- Merged result track -->
        <div class="result-section" id="resultSection">
            <div class="result-track">
                <img id="resultTrack" src="" alt="合并后轨迹">
                <div class="result-label">✅ 合并后轨迹 · <span class="color-dot" style="background:#ffa502"></span>合并结果</div>
            </div>
        </div>

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
        const previewSection = document.getElementById('previewSection');
        const previewLoading = document.getElementById('previewLoading');
        const previewImg = document.getElementById('previewImg');
        const previewLabel = document.getElementById('previewLabel');
        const resultSection = document.getElementById('resultSection');
        const resultTrack = document.getElementById('resultTrack');

        function updateBtn() {
            btn.disabled = !(file1.files.length && file2.files.length);
        }

        function tryPreviewBoth() {
            // Only preview when both files are uploaded
            if (!file1.files.length || !file2.files.length) return;

            previewSection.classList.add('show');
            previewLoading.style.display = 'block';
            previewImg.style.display = 'none';
            previewLabel.textContent = '';

            const fd = new FormData();
            fd.append('file1', file1.files[0]);
            fd.append('file2', file2.files[0]);

            fetch('/preview_both', { method: 'POST', body: fd })
                .then(r => r.json())
                .then(data => {
                    previewLoading.style.display = 'none';
                    if (data.image) {
                        previewImg.src = 'data:image/png;base64,' + data.image;
                        previewImg.style.display = 'block';
                        let labelHtml = '合并前预览 · ';
                        labelHtml += '<span class="color-dot" style="background:#ff6b6b"></span>文件 1 (' + (data.points1 || 0) + ' 点) · ';
                        labelHtml += '<span class="color-dot" style="background:#4ecdc4"></span>文件 2 (' + (data.points2 || 0) + ' 点)';
                        previewLabel.innerHTML = labelHtml;
                    } else {
                        previewLabel.textContent = data.message || '无 GPS 数据';
                    }
                })
                .catch(() => {
                    previewLoading.style.display = 'none';
                    previewLabel.textContent = '预览生成失败';
                });
        }

        // Also support single file preview: if only one is uploaded, show it alone
        function tryPreviewSingle() {
            const hasFile1 = file1.files.length > 0;
            const hasFile2 = file2.files.length > 0;

            if (hasFile1 && hasFile2) {
                tryPreviewBoth();
                return;
            }

            if (!hasFile1 && !hasFile2) {
                previewSection.classList.remove('show');
                return;
            }

            const theFile = hasFile1 ? file1.files[0] : file2.files[0];
            const which = hasFile1 ? '文件 1' : '文件 2';
            const color = hasFile1 ? '#ff6b6b' : '#4ecdc4';

            previewSection.classList.add('show');
            previewLoading.style.display = 'block';
            previewImg.style.display = 'none';
            previewLabel.textContent = '';

            const fd = new FormData();
            fd.append('file', theFile);

            fetch('/preview', { method: 'POST', body: fd })
                .then(r => r.json())
                .then(data => {
                    previewLoading.style.display = 'none';
                    if (data.image) {
                        previewImg.src = 'data:image/png;base64,' + data.image;
                        previewImg.style.display = 'block';
                        previewLabel.innerHTML = '<span class="color-dot" style="background:' + color + '"></span>' + which + ' (' + (data.points || 0) + ' GPS 点) · 等待上传另一个文件...';
                    } else {
                        previewLabel.textContent = which + ': 无 GPS 数据';
                    }
                })
                .catch(() => {
                    previewLoading.style.display = 'none';
                    previewLabel.textContent = '预览生成失败';
                });
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
                tryPreviewSingle();
            });

            ['dragenter', 'dragover'].forEach(e => {
                zone.addEventListener(e, ev => { ev.preventDefault(); zone.classList.add('dragover'); });
            });
            ['dragleave', 'drop'].forEach(e => {
                zone.addEventListener(e, ev => { ev.preventDefault(); zone.classList.remove('dragover'); });
            });
            zone.addEventListener('drop', ev => {
                const files = ev.dataTransfer.files;
                if (files.length) { input.files = files; input.dispatchEvent(new Event('change')); }
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
            resultSection.classList.remove('show');

            const formData = new FormData();
            formData.append('file1', file1.files[0]);
            formData.append('file2', file2.files[0]);

            try {
                const resp = await fetch('/merge', { method: 'POST', body: formData });
                const data = await resp.json();

                if (resp.ok && data.file) {
                    // Download the merged file
                    const byteString = atob(data.file);
                    const ab = new ArrayBuffer(byteString.length);
                    const ia = new Uint8Array(ab);
                    for (let i = 0; i < byteString.length; i++) ia[i] = byteString.charCodeAt(i);
                    const blob = new Blob([ab], { type: 'application/octet-stream' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'merged.fit';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);

                    status.className = 'status success';
                    status.textContent = '✅ 合并成功！文件已开始下载（' + (data.size || '?') + ' bytes）';

                    // Show merged track
                    if (data.track_image) {
                        resultTrack.src = 'data:image/png;base64,' + data.track_image;
                        resultSection.classList.add('show');
                    }
                } else {
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


@app.route('/preview', methods=['POST'])
def preview():
    """预览单个 FIT 文件的 GPS 轨迹"""
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': '未选择文件'}), 400

    work_dir = tempfile.mkdtemp(prefix='fit_preview_')
    try:
        fit_path = os.path.join(work_dir, 'preview.fit')
        f.save(fit_path)

        lats, lons = extract_gps_from_fit(fit_path)
        if not lats:
            return jsonify({'message': '无 GPS 数据', 'image': None})

        img = generate_track_image(
            [(lats, lons)],
            labels=['轨迹'],
            colors=['#ff6b6b'],
        )
        return jsonify({'image': img, 'points': len(lats)})

    except Exception as e:
        return jsonify({'error': str(e), 'image': None}), 500
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.route('/preview_both', methods=['POST'])
def preview_both():
    """预览两个 FIT 文件的 GPS 轨迹，画在同一张图上，不同颜色"""
    if 'file1' not in request.files or 'file2' not in request.files:
        return jsonify({'error': '请上传两个文件'}), 400

    f1 = request.files['file1']
    f2 = request.files['file2']

    work_dir = tempfile.mkdtemp(prefix='fit_preview_both_')
    try:
        fit1_path = os.path.join(work_dir, 'file1.fit')
        fit2_path = os.path.join(work_dir, 'file2.fit')
        f1.save(fit1_path)
        f2.save(fit2_path)

        lats1, lons1 = extract_gps_from_fit(fit1_path)
        lats2, lons2 = extract_gps_from_fit(fit2_path)

        if not lats1 and not lats2:
            return jsonify({'message': '两个文件均无 GPS 数据', 'image': None})

        tracks = []
        labels = []
        colors = []

        if lats1:
            tracks.append((lats1, lons1))
            labels.append(f'文件 1 ({len(lats1)} 点)')
            colors.append('#ff6b6b')
        if lats2:
            tracks.append((lats2, lons2))
            labels.append(f'文件 2 ({len(lats2)} 点)')
            colors.append('#4ecdc4')

        img = generate_track_image(tracks, labels=labels, colors=colors,
                                   title='合并前 · 轨迹对比')
        return jsonify({
            'image': img,
            'points1': len(lats1),
            'points2': len(lats2),
        })

    except Exception as e:
        return jsonify({'error': str(e), 'image': None}), 500
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


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

    work_dir = tempfile.mkdtemp(prefix='fit_web_')
    try:
        fit1_path = os.path.join(work_dir, 'file1.fit')
        fit2_path = os.path.join(work_dir, 'file2.fit')
        output_path = os.path.join(work_dir, 'merged.fit')

        file1.save(fit1_path)
        file2.save(fit2_path)

        merge_fit_files(fit1_path, fit2_path, output_path, tool_jar)

        if not os.path.exists(output_path):
            return jsonify({'error': '合并后未生成输出文件。'}), 500

        # 生成合并后轨迹图
        track_image = None
        try:
            lats, lons = extract_gps_from_fit(output_path)
            if lats:
                track_image = generate_track_image(
                    [(lats, lons)],
                    labels=['合并轨迹'],
                    colors=['#ffa502'],
                    title='合并结果',
                )
        except Exception:
            pass

        with open(output_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')

        return jsonify({
            'file': file_data,
            'track_image': track_image,
            'size': os.path.getsize(output_path),
        })

    except Exception as e:
        return jsonify({'error': f'合并失败: {str(e)}'}), 500

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()

    print("=" * 50)
    print("FIT 文件合并工具 - Web 界面")
    print("=" * 50)

    if not check_java():
        print("⚠️  警告: 未检测到 Java，合并功能将不可用。")
    else:
        print("✅ Java: 已安装")

    tool = find_fit_csv_tool()
    if tool:
        print(f"✅ FitCSVTool: {tool}")
    else:
        print("⚠️  警告: 找不到 FitCSVTool.jar")

    print()
    print(f"🌐 打开浏览器访问: http://localhost:{args.port}")
    print("=" * 50)

    app.run(host='0.0.0.0', port=args.port, debug=False)
