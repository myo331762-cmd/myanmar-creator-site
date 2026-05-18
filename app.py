import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import asyncio, io, requests, edge_tts, re
from flask import Flask, request, jsonify 
render_template_string, Response, stream_with_context, send_file
from flask_cors import CORS
from yt_dlp import YoutubeDL

app = Flask(__name__)
CORS(app)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Myanmar Creator Site</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-[#1a1f2c] border border-slate-800 p-5 rounded-2xl shadow-2xl w-full max-w-md space-y-5">
        <div class="text-center">
            <h1 class="text-2xl font-black text-cyan-400 tracking-wider uppercase">MYANMAR CREATOR SITE</h1>
        </div>
        <div class="space-y-3.5 bg-[#11151e] p-4 rounded-2xl border border-slate-800/60">
            <div class="flex justify-between items-center">
                <p class="text-xs text-amber-400 font-black uppercase tracking-wide">📍 PART 1: AI MYANMAR VOICE STUDIO</p>
                <button onclick="clearTxt('ttsTxt')" class="text-xs bg-red-600/20 border border-red-500/30 text-red-400 px-3 py-1 rounded-xl font-bold">❌ Clear Text</button>
            </div>
            <textarea id="ttsTxt" rows="4" placeholder="မြန်မာဇာတ်ညွှန်းများကို ဒီမှာ ရေးထည့်ပါ..." class="w-full p-3 rounded-2xl bg-[#1e2533] text-xs text-slate-200 focus:outline-none border border-slate-700/40 focus:border-amber-500/50"></textarea>
            <div class="grid grid-cols-2 gap-2.5">
                <select id="vc" class="p-2.5 rounded-2xl bg-[#1e2533] text-xs text-slate-200 border border-slate-700/40">
                    <option value="my-MM-NilarNeural">👩 Female (နီလာ)</option>
                    <option value="my-MM-ThihaNeural">👨 Male (သီဟ)</option>
                </select>
                <select id="sp" class="p-2.5 rounded-2xl bg-[#1e2533] text-xs text-slate-200 border border-slate-700/40">
                    <option value="1.0">😐 Normal (0%)</option>
                    <option value="1.1">⚡ Fast (+10%)</option>
                    <option value="1.2">⚡ Fast (+20%)</option>
                    <option value="1.3" selected>⚡ Fast (+30%)</option>
                    <option value="1.4">🚀 Fast (+40%)</option>
                </select>
            </div>
            <button onclick="gVoice()" class="w-full bg-amber-500 p-2.5 rounded-2xl font-black text-xs text-slate-950 shadow-lg shadow-amber-500/20 uppercase tracking-wide">🗣️ Convert Script to AI Voice</button>
            <div id="vRes" class="hidden space-y-2">
                <audio id="aud" controls class="w-full h-9"></audio>
                <a id="dlA" download="voice.mp3" class="block bg-cyan-600 p-2 text-center text-xs font-black rounded-2xl uppercase">📥 Download MP3</a>
            </div>
        </div>
        <div id="ld" class="hidden text-center text-xs text-cyan-400 font-bold bg-[#11151e] p-3 rounded-2xl border border-cyan-500/20 animate-pulse">
            ⏳ Extracting Data from Server... Please wait...
        </div>
        <div class="space-y-3.5 bg-[#11151e] p-4 rounded-2xl border border-slate-800/60">
            <p class="text-xs text-cyan-400 font-black uppercase tracking-wide">📹 PART 2: VIDEO LINK EXTRACTOR</p>
            <input type="text" id="url" placeholder="Paste Video Link here..." class="w-full p-3 rounded-2xl bg-[#1e2533] text-xs text-slate-200 focus:outline-none border border-slate-700/40 focus:border-cyan-500/50">
            <div class="grid grid-cols-2 gap-2.5">
                <button onclick="extVideo()" class="w-full bg-cyan-600 p-2.5 rounded-2xl font-black text-xs text-white uppercase tracking-wide">💥 Extract Video Info</button>
                <button onclick="getOriginalSRTAndText()" class="w-full bg-emerald-600 p-2.5 rounded-2xl font-black text-xs text-white uppercase tracking-wide">🇬🇧 Get SRT & Text</button>
            </div>
            <div id="res" class="hidden space-y-3 pt-1">
                <p id="t" class="text-xs font-bold text-slate-300 truncate p-1 bg-[#1e2533]/50 rounded-xl px-2 border border-slate-800"></p>
                <div id="vPreviewBox" class="hidden rounded-2xl border border-slate-700 bg-black overflow-hidden"><video id="vPreview" controls playsinline class="w-full max-h-36 object-contain"></video></div>
                <div id="fmts" class="space-y-1.5 max-h-24 overflow-y-auto"></div>
                <div id="engTextsSection" class="hidden space-y-3 pt-2 border-t border-slate-800/80">
                    <div class="space-y-1">
                        <label class="text-[11px] text-cyan-400 font-black uppercase tracking-wide">🇬🇧 Original English SRT</label>
                        <textarea id="engSrtOut" rows="4" readonly class="w-full p-2.5 rounded-xl bg-[#1e2533] text-xs text-slate-300 focus:outline-none border border-slate-700/30 select-all"></textarea>
                    </div>
                    <div class="space-y-1">
                        <label class="text-[11px] text-emerald-400 font-black uppercase tracking-wide">🇬🇧 Original English Text</label>
                        <textarea id="engTxtOut" rows="4" readonly class="w-full p-2.5 rounded-xl bg-[#1e2533] text-xs text-slate-200 focus:outline-none border border-slate-700/30 select-all"></textarea>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        const $ = id => document.getElementById(id);
        const toggle = (id, s) => { const el = $(id); if(s) { el.classList.remove('hidden'); } else { el.classList.add('hidden'); } };
        window.onload = () => { if(localStorage.getItem('fS')) $('ttsTxt').value = localStorage.getItem('fS'); };
        $('ttsTxt').oninput = (e) => localStorage.setItem('fS', e.target.value);
        function clearTxt(id) { $(id).value = ""; if(id==='ttsTxt') localStorage.setItem('fS', ""); }
        async function gVoice() {
            const text=$('ttsTxt').value, voice=$('vc').value, speed=$('sp').value; if(!text.trim()) return alert('စာထည့်ပါ');
            toggle('ld', 1); toggle('vRes', 0);
            try {
                const r = await fetch('/tts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text, voice, speed})});
                if(r.ok) { const b=await r.blob(), u=URL.createObjectURL(b); $('aud').src=u; $('dlA').href=u; toggle('vRes', 1); } else alert(await r.text());
            } catch(e){alert('Error');} finally { toggle('ld', 0); }
        }
        async function extVideo() {
            const url = $('url').value.trim(); if(!url) return alert('လင့်ခ်အရင်ထည့်ပေးပါဗျာ!');
            toggle('ld', 1); toggle('res', 0); toggle('vPreviewBox', 0); $('engTextsSection').classList.add('hidden');
            try {
                const r = await fetch('/ext', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
                const d = await r.json();
                if(d.success) {
                    $('t').innerText = d.title; $('fmts').innerHTML = "";
                    if(d.fmts.length > 0) { $('vPreview').src = d.fmts[0].url; toggle('vPreviewBox', 1); }
                    d.fmts.forEach(f => { $('fmts').innerHTML += `<a href="/dl?url=${encodeURIComponent(f.url)}&ext=${f.ext}" class="block bg-[#1e2533] p-2 rounded-2xl text-xs text-slate-300 flex justify-between border border-slate-800"><span>Video ${f.res} (${f.size})</span><span class="text-cyan-400 font-bold">Download</span></a>`; });
                    toggle('res', 1);
                } else alert(d.error);
            } catch(e){alert('Error');} finally { toggle('ld', 0); }
        }
        async function getOriginalSRTAndText() {
            const url = $('url').value.trim(); if(!url) return alert('ဗီဒီယိုလင့်ခ် အရင်ထည့်ပေးပါဦးဗျာ!');
            toggle('ld', 1); $('engTextsSection').classList.add('hidden');
            try {
                const r = await fetch('/get-sub', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
                const d = await r.json();
                if(d.success) {
                    $('engSrtOut').value = d.srt_data; $('engTxtOut').value = d.txt_data;
                    toggle('res', 1); $('engTextsSection').classList.remove('hidden');
                    alert('🎉 Extraction Complete!');
                } else alert(d.error);
            } catch(e){alert('Error');} finally { toggle('ld', 0); }
        }
    </script>
</body>
</html>
"""

def convert_srt_to_clean_text(srt_text):
    if not srt_text: return ""
    text = re.sub(r'\d\d:\d\d:\d\d[,\.]\d\d\d --> \d\d:\d\d:\d\d[,\.]\d\d\d', '', srt_text)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line_strip = line.strip()
        if line_strip.isdigit(): continue
        if line_strip:
            line_strip = re.sub(r'^\d+\s*$', '', line_strip)
            if line_strip: cleaned.append(line_strip)
    return "\n".join(cleaned)

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/tts', methods=['POST'])
def tts():
    data = request.json
    text, voice, speed = data.get('text', '').strip(), data.get('voice', 'my-MM-NilarNeural'), data.get('speed', '1.0')
    if not text: return "No text", 400
    v = float(speed)
    rate = f"+{int((v - 1.0) * 100)}%" if v >= 1.0 else f"-{int((1.0 - v) * 100)}%"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_data = loop.run_until_complete(run_tts(text, voice, rate))
        loop.close()
        return send_file(io.BytesIO(audio_data), mimetype="audio/mp3", as_attachment=True, download_name="ai.mp3")
    except Exception as e: return str(e), 500

async def run_tts(text, voice, rate):
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    audio = b""
    for chunk in chunks:
        if not chunk.strip(): continue
        comm = edge_tts.Communicate(chunk, voice, rate=rate)
        async for data in comm.stream():
            if data["type"] == "audio": audio += data["data"]
    return audio

@app.route('/dl')
def download_proxy():
    url, ext = request.args.get('url'), request.args.get('ext', 'mp4')
    try:
        req = requests.get(url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}, timeout=180)
        def generate():
            for c in req.iter_content(chunk_size=65536):
                if c: yield c
        return Response(stream_with_context(generate()), headers={'Content-Disposition': 'attachment; filename="video.' + str(ext) + '"', 'Content-Type': req.headers.get('content-type', 'video/mp4')})
    except Exception as e: return str(e), 500

@app.route('/ext', methods=['POST'])
def extract_video():
    url = request.json.get('url', '').strip()
    if not url or not url.startswith('http'): return jsonify({'success': False, 'error': 'လင့်ခ်ပုံစံ မှားယွင်းနေပါသည်။'})
    try:
        with YoutubeDL({'format': 'all', 'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Video')
            formats = info.get('formats', [])
            fmts_data, seen = [], set()
            for f in formats:
                if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    res = f.get('resolution') or (str(f.get('height')) + "p")
                    if res in seen: continue
                    seen.add(res)
                    sz = f.get('filesize') or f.get('filesize_approx') or 0
                    sz_txt = f"{sz / (1024*1024):.1f} MB" if sz else "Unknown"
                    fmts_data.append({'res': str(res), 'url': f.get('url'), 'h': f.get('height') or 0, 'ext': f.get('ext', 'mp4'), 'size': sz_txt})
            if not fmts_data and info.get('url'): fmts_data.append({'res': "Best Quality", 'url': info.get('url'), 'h': 9999, 'ext': 'mp4', 'size': 'Unknown'})
            fmts_data.sort(key=lambda x: x['h'], reverse=True)
            return jsonify({'success': True, 'title': title, 'fmts': fmts_data})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

@app.route('/get-sub', methods=['POST'])
def get_original_subtitle():
    url = request.json.get('url', '').strip()
    ydl_opts = {'writesubtitles': True, 'allsubtitles': True, 'skip_download': True, 'quiet': True, 'no_warnings': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            srt_url = None
            if 'en' in subtitles:
                for sub in subtitles['en']:
                    if sub.get('ext') in ['srt', 'vtt']: srt_url = sub.get('url'); break
            if not srt_url and 'en' in automatic_captions:
                for sub in automatic_captions['en']:
                    if sub.get('ext') in ['srt', 'vtt']: srt_url = sub.get('url'); break
            if srt_url:
                sub_res = requests.get(srt_url, timeout=30)
                if sub_res.status_code == 200:
                    pure_srt = sub_res.text
                    if "WEBVTT" in pure_srt: pure_srt = re.sub(r'^WEBVTT.*?\\n\\n', '', pure_srt, flags=re.DOTALL)
                    pure_text = convert_srt_to_clean_text(pure_srt)
                    return jsonify({'success': True, 'srt_data': pure_srt.strip(), 'txt_data': pure_text.strip()})
            return jsonify({'success': False, 'error': 'No Subtitles found.'})
    except Exception as e: return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
