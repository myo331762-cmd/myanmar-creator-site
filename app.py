import os
import sys
import asyncio
import io
import requests
import yt_dlp
import edge_tts
import re
import random
import logging
import threading
import uuid
from flask import Flask, render_template_string, request, jsonify, send_file
from flask_cors import CORS
from deep_translator import GoogleTranslator

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Global dictionary ဖြင့် Task များကို မှတ်ခြင်း
BACKGROUND_TASKS = {}
# 💡 Fix 1: Thread-Safety အတွက် Lock စနစ်ကို အသုံးပြုခြင်း
tasks_lock = threading.Lock()

# ==========================================
# 1. HTML UI Template
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phone Media Suite Pro</title>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .nav-tabs .nav-link.active { background-color: #0d6efd; color: white; border-color: #0d6efd; }
        .card { border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <div class="container py-4" style="max-width: 600px;">
        <h3 class="text-center mb-4 fw-bold text-primary">📱 Mobile All-In-One Downloader</h3>
        
        <ul class="nav nav-tabs mb-4 justify-content-center" id="myTab" role="tablist">
            <li class="nav-item"><button class="nav-link active fw-bold" id="video-tab" data-bs-toggle="tab" data-bs-target="#video-panel">Video</button></li>
            <li class="nav-item"><button class="nav-link fw-bold" id="sub-tab" data-bs-toggle="tab" data-bs-target="#sub-panel">Subtitle</button></li>
            <li class="nav-item"><button class="nav-link fw-bold" id="tts-tab" data-bs-toggle="tab" data-bs-target="#tts-panel">Text-To-Speech</button></li>
        </ul>

        <div class="tab-content">
            <div class="tab-pane fade show active" id="video-panel">
                <div class="card p-3">
                    <h5>Social Media Downloader</h5>
                    <div class="input-group mb-3">
                        <input type="text" id="videoUrl" class="form-control" placeholder="Paste link here...">
                        <button class="btn btn-primary" onclick="startTask('/ext', 'videoUrl', renderVideoResults)">Extract</button>
                    </div>
                    <div id="videoResult" class="mt-2"></div>
                </div>
            </div>

            <div class="tab-pane fade" id="sub-panel">
                <div class="card p-3">
                    <h5>YouTube Subtitle Extractor</h5>
                    <div class="input-group mb-3">
                        <input type="text" id="subUrl" class="form-control" placeholder="Paste YouTube link here...">
                        <button class="btn btn-primary" onclick="startTask('/get-sub', 'subUrl', renderSubResults)">Get Subs</button>
                    </div>
                    <div id="subResult" class="mt-2"></div>
                </div>
            </div>

            <div class="tab-pane fade" id="tts-panel">
                <div class="card p-3">
                    <h5>Myanmar Edge TTS</h5>
                    <div class="mb-3">
                        <textarea id="ttsText" class="form-control" rows="3" placeholder="မြန်မာစာသားများ ရိုက်ထည့်ပါ..."></textarea>
                    </div>
                    <button class="btn btn-primary w-100" onclick="generateTTS()">အသံပြောင်းမည်</button>
                    <audio id="audioPlayer" class="w-100 mt-3 d-none" controls></audio>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function startTask(endpoint, inputId, successCallback) {
            const url = document.getElementById(inputId).value.trim();
            if(!url) return Swal.fire('Error', 'လင့်ခ် အရင်ထည့်ပါ!', 'error');
            
            Swal.fire({ title: 'Processing...', text: 'ခေတ္တစောင့်ဆိုင်းပေးပါ...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

            try {
                const res = await fetch(endpoint, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url}) });
                const data = await res.json();
                if(data.success && data.task_id) {
                    checkStatus(data.task_id, successCallback);
                } else {
                    Swal.fire('Error', data.error || 'အဆင်မပြေပါ', 'error');
                }
            } catch(e) { Swal.fire('Error', 'Server Error', 'error'); }
        }

        function checkStatus(taskId, successCallback) {
            const interval = setInterval(async () => {
                const res = await fetch(`/status/${taskId}`);
                const data = await res.json();
                if(data.status === 'Completed') {
                    clearInterval(interval); Swal.close(); successCallback(data.result);
                } else if(data.status === 'Failed') {
                    clearInterval(interval); Swal.fire('Failed', data.error || 'မအောင်မြင်ပါ', 'error');
                }
            }, 2000);
        }

        function renderVideoResults(res) {
            if(!res.success) return Swal.fire('Error', res.error, 'error');
            let html = `<h6>${res.title}</h6><table class="table table-sm mt-2"><tbody>`;
            res.fmts.forEach(f => {
                html += `<tr><td>${f.res}</td><td><a href="${f.url}" target="_blank" download="video.mp4" class="btn btn-success btn-sm">Download</a></td></tr>`;
            });
            html += '</tbody></table>';
            html += `<div class="alert alert-warning small mt-2">⚠️ <b>မှတ်ချက်:</b> Download ခလုတ်နှိပ်လို့ မကျဘဲ ဗီဒီယိုပဲ ပွင့်လာပါက ခလုတ်ကို ဖိနှိပ်ပြီး <b>"Copy link address"</b> ကိုယူကာ Advanced Downloader (သို့) IDM တို့ဖြင့် ဒေါင်းလုဒ်ဆွဲပါ။</div>`;
            document.getElementById('videoResult').innerHTML = html;
        }

        function renderSubResults(res) {
            if(!res.success) return Swal.fire('Error', res.error, 'error');
            let html = `<h6>စာတန်းထိုး ထွက်လာပါပြီ</h6><div class="d-flex gap-2 my-2">`;
            if(res.my_srt) html += `<button class="btn btn-outline-primary btn-sm" onclick="downloadBlob('${btoa(unescape(encodeURIComponent(res.my_srt)))}', 'sub.srt')">Download SRT</button>`;
            if(res.my_txt) html += `<button class="btn btn-outline-secondary btn-sm" onclick="downloadBlob('${btoa(unescape(encodeURIComponent(res.my_txt)))}', 'text.txt')">Download TXT</button>`;
            html += `</div><textarea class="form-control text-start" rows="5" readonly>${res.my_txt || res.eng_txt}</textarea>`;
            document.getElementById('subResult').innerHTML = html;
        }

        function downloadBlob(base64Str, filename) {
            const binary = atob(base64Str);
            const array = [];
            for (let i = 0; i < binary.length; i++) array.push(binary.charCodeAt(i));
            const blob = new Blob([new Uint8Array(array)], {type: 'text/plain'});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            link.click();
        }

        async function generateTTS() {
            const text = document.getElementById('ttsText').value.trim();
            if(!text) return Swal.fire('Error', 'စာသားထည့်ပါ', 'error');
            Swal.fire({ title: 'Converting...', didOpen: () => Swal.showLoading() });
            
            const res = await fetch('/tts', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text}) });
            if(res.status === 200) {
                Swal.close();
                const blob = await res.blob();
                const audio = document.getElementById('audioPlayer');
                audio.src = URL.createObjectURL(blob);
                audio.classList.remove('d-none');
                audio.play();
            } else { Swal.fire('Error', 'မအောင်မြင်ပါ', 'error'); }
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# ==========================================
# 2. Helpers (Thread-Safe & Robust Cleanup)
# ==========================================
def cleanup_tasks():
    """💡 Fix 1 & 3: Thread-safe ဖြစ်ပြီး အတင်းအကျပ် ဖျက်ထုတ်ပေးမည့် Cleanup စနစ်"""
    with tasks_lock:
        # စိတ်ချရအောင် list() ပြောင်းပြီးမှ loop ပတ်ခြင်း (Crash မဖြစ်စေရန်)
        current_tasks = list(BACKGROUND_TASKS.items())
        
        # ၁။ ပြီးဆုံးသွားသော Task အဟောင်းများကို အရင်ဖျက်ထုတ်ခြင်း
        keys_to_del = [k for k, v in current_tasks if v.get('status') in ['Completed', 'Failed']]
        for k in keys_to_del[:10]:
            BACKGROUND_TASKS.pop(k, None)
            
        # ၂။ အကယ်၍ အားလုံး Processing ဖြစ်ပြီး အရေအတွက် ၂၅ ခုထက် ကျော်လာပါက အဟောင်းဆုံးကို အတင်းဖျက်ပစ်ခြင်း
        if len(BACKGROUND_TASKS) > 25:
            oldest_keys = list(BACKGROUND_TASKS.keys())[:10]
            for k in oldest_keys:
                BACKGROUND_TASKS.pop(k, None)

def convert_srt_to_clean_text(srt_text):
    if not srt_text: return ""
    text = re.sub(r'(\d{2}:)?\d{2}:\d{2}[,\.]\d{3} --> (\d{2}:)?\d{2}:\d{2}[,\.]\d{3}', '', srt_text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = text.split('\n')
    cleaned = [line.strip() for line in lines if line.strip() and not line.strip().isdigit() and line.strip().lower() != "webvtt"]
    return "\n".join(cleaned)

def vtt_to_srt(vtt_content):
    if not vtt_content: return ""
    srt = re.sub(r'^WEBVTT([\s\S]*?)\n\n', '', vtt_content)
    srt = re.sub(r'(\d{2}:)?(\d{2}:\d{2})\.(\d{3})', r'\1\2,\3', srt)
    lines = srt.split('\n')
    new_lines = []
    counter = 1
    expect_timeline = True
    for line in lines:
        if '-->' in line:
            if expect_timeline:
                new_lines.append(str(counter)); counter += 1
            new_lines.append(line); expect_timeline = False
        else:
            if line.strip() == "": expect_timeline = True
            new_lines.append(line)
    return '\n'.join(new_lines)

def get_tiktok_nowatermark(url):
    try:
        api_url = f"https://www.tikwm.com/api/?url={url}&hd=1"
        response = requests.get(api_url, timeout=15).json()
        if response.get('code') == 0:
            data = response['data']
            return {
                'success': True, 'title': data.get('title', 'TikTok Video'),
                'fmts': [
                    {'res': 'HD Video (No Watermark)', 'url': data.get('hdplay') or data.get('play'), 'size': 'Auto', 'ext': 'mp4'},
                    {'res': 'Audio ONLY (MP3)', 'url': data.get('music'), 'size': 'Auto', 'ext': 'mp3'}
                ]
            }
        return {'success': False, 'error': 'Private ဗီဒီယို ဖြစ်နိုင်ပါသည်'}
    except Exception as e: return {'success': False, 'error': str(e)}

def translate_srt_to_myanmar(srt_text):
    if not srt_text: return ""
    original_srt = srt_text
    translator = GoogleTranslator(source='en', target='my')
    lines = srt_text.split('\n')
    texts_to_translate, translate_indices = [], []
    
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and '-->' not in stripped and not stripped.isdigit():
            texts_to_translate.append(stripped)
            translate_indices.append(idx)
            
    if not texts_to_translate: return srt_text
    
    try:
        translated_texts = []
        for i in range(0, len(texts_to_translate), 30):
            chunk = texts_to_translate[i:i+30]
            translated_texts.extend(translator.translate_batch(chunk))
            
        for idx, trans_txt in zip(translate_indices, translated_texts): 
            lines[idx] = trans_txt
        return '\n'.join(lines)
    except Exception as e: 
        logger.error(f"Batch Translation Failed: {str(e)}")
        return original_srt

async def _generate_audio_bytes(text):
    audio_data = b""
    comm = edge_tts.Communicate(text, 'my-MM-NilarNeural', rate="+0%")
    async for chunk in comm.stream():
        if chunk["type"] == "audio": audio_data += chunk["data"]
    return audio_data

# ==========================================
# 3. Threaded Background Workers
# ==========================================
def bg_video_download(task_id, url):
    if 'tiktok.com' in url or 'douyin.com' in url:
        with tasks_lock:
            BACKGROUND_TASKS[task_id] = {'status': 'Completed', 'result': get_tiktok_nowatermark(url)}
        return

    ydl_opts = 
    try:    ydl_opts = {
        'quiet': True, 
        'no_warnings': True, 
        'format': 'best[ext=mp4]/best',
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'skip': ['webpage']
            }
        }
    }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            fmts_data = []
            if 'formats' in info:
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                        res = f.get('resolution') or (str(f.get('height')) + "p")
                        fmts_data.append({'res': str(res), 'url': f.get('url'), 'ext': f.get('ext', 'mp4'), 'size': 'View'})
            if not fmts_data and info.get('url'):
                fmts_data.append({'res': 'Standard Quality', 'url': info.get('url'), 'ext': info.get('ext', 'mp4'), 'size': 'View'})
            
            with tasks_lock:
                BACKGROUND_TASKS[task_id] = {
                    'status': 'Completed',
                    'result': {'success': True, 'title': info.get('title', 'Video'), 'fmts': fmts_data[:5]}
                }
    except Exception as e:
        with tasks_lock:
            BACKGROUND_TASKS[task_id] = {'status': 'Failed', 'error': str(e)}

def bg_subtitle_extract(task_id, url):
    ydl_opts = 
    try:    ydl_opts = {
        'quiet': True, 
        'skip_download': True, 
        'writesubtitles': True, 
        'writeautomaticsub': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
                'skip': ['webpage']
            }
        }
    }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get('subtitles', {}); auto_subs = info.get('automatic_captions', {})
            base_sub_url = None; is_youtube = 'youtube.com' in url or 'youtu.be' in url
            for lang in ['en', 'en-US', 'en-GB']:
                if lang in subs: base_sub_url = subs[lang][0].get('url'); break
                elif lang in auto_subs: base_sub_url = auto_subs[lang][0].get('url'); break
            
            if not base_sub_url:
                with tasks_lock: BACKGROUND_TASKS[task_id] = {'status': 'Failed', 'error': 'ဤဗီဒီယိုတွင် အင်္ဂလိပ်စာတန်းထိုး မတွေ့ပါ'}
                return
            
            if is_youtube and "fmt=" not in base_sub_url: base_sub_url += "&fmt=vtt"
            
            eng_res = requests.get(base_sub_url, timeout=15)
            
            # 💡 Fix 2: Subtitle စာသား တကယ် ရမရ စစ်ဆေးခြင်း
            if eng_res.status_code != 200 or not eng_res.text.strip():
                with tasks_lock: BACKGROUND_TASKS[task_id] = {'status': 'Failed', 'error': 'စာတန်းထိုးဆွဲ၍မရပါ (Network Error သို့မဟုတ် လင့်ခ်သေနေခြင်း)'}
                return

            eng_srt = vtt_to_srt(eng_res.text)
            eng_txt = convert_srt_to_clean_text(eng_srt)
            
            my_srt = translate_srt_to_myanmar(eng_srt)
            my_txt = convert_srt_to_clean_text(my_srt)
            
            with tasks_lock:
                BACKGROUND_TASKS[task_id] = {
                    'status': 'Completed',
                    'result': {'success': True, 'eng_srt': eng_srt, 'eng_txt': eng_txt, 'my_srt': my_srt, 'my_txt': my_txt}
                }
    except Exception as e:
        with tasks_lock: BACKGROUND_TASKS[task_id] = {'status': 'Failed', 'error': str(e)}

# ==========================================
# 4. Flask Routes
# ==========================================
@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/ext', methods=['POST'])
def extract_video():
    url = (request.json or {}).get('url', '').strip()
    if not url: return jsonify({'success': False, 'error': 'လင့်ခ်ထည့်ပါ'})
    cleanup_tasks() 
    task_id = str(uuid.uuid4())
    with tasks_lock: BACKGROUND_TASKS[task_id] = {'status': 'Processing'}
    threading.Thread(target=bg_video_download, args=(task_id, url)).start()
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/get-sub', methods=['POST'])
def get_subtitles():
    url = (request.json or {}).get('url', '').strip()
    if not url: return jsonify({'success': False, 'error': 'လင့်ခ်ထည့်ပါ'})
    cleanup_tasks() 
    task_id = str(uuid.uuid4())
    with tasks_lock: BACKGROUND_TASKS[task_id] = {'status': 'Processing'}
    threading.Thread(target=bg_subtitle_extract, args=(task_id, url)).start()
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    with tasks_lock:
        task = BACKGROUND_TASKS.get(task_id, {'status': 'Failed', 'error': 'Task Not Found'})
    return jsonify(task)

@app.route('/tts', methods=['POST'])
def tts():
    text = (request.json or {}).get('text', '').strip()
    if not text: return "No text", 400
    try:
        audio = asyncio.run(_generate_audio_bytes(text))
        return send_file(io.BytesIO(audio), mimetype="audio/mp3")
    except Exception as e: return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
