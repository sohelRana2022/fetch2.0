import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, send_file, after_this_request
from flask_cors import CORS
import yt_dlp
import requests

# Initialize Flask
app = Flask(__name__)
CORS(app)

# PythonAnywhere looks for a variable named 'application' by default
application = app

# Use absolute path for downloads to ensure it works in the server environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# FFmpeg configuration for PythonAnywhere
# On PythonAnywhere (Linux), FFmpeg is usually in the system PATH (/usr/bin/ffmpeg).
# We set this to None so yt-dlp finds it automatically.
FFMPEG_DIR = None

# Global dictionary to track tasks
tasks = {}

def background_download(task_id, url, quality, output_template, ffmpeg_dir):
    try:
        def progress_hook(d):
            if d['status'] == 'downloading':
                # Extract progress info
                p = d.get('_percent_str', '0%').replace('%', '')
                s = d.get('_speed_str', 'N/A')
                e = d.get('_eta_str', 'N/A')
                
                if task_id in tasks:
                    tasks[task_id].update({
                        'status': 'downloading',
                        'progress': p,
                        'speed': s,
                        'eta': e
                    })
            elif d['status'] == 'finished':
                if task_id in tasks:
                    tasks[task_id].update({
                        'status': 'processing',
                        'progress': '100'
                    })

        ydl_opts = {
            'outtmpl': output_template,
            'nocheckcertificate': True,
            'prefer_ffmpeg': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True
        }

        # Only set ffmpeg_location if a specific path is provided (not needed on PA)
        if ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = ffmpeg_dir

        if quality == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            if quality == '1080p':
                ydl_opts['format'] = 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best'
            elif quality == '720p':
                ydl_opts['format'] = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best'
            else:
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if task_id in tasks:
            tasks[task_id]['status'] = 'finished'

    except Exception as e:
        if task_id in tasks:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tasks')
def get_tasks():
    return jsonify(tasks)

@app.route('/api/search', methods=['POST'])
def search_video():
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            
        results = []
        for entry in info.get('entries', []):
            video_id = entry.get('id')
            results.append({
                'id': video_id,
                'title': entry.get('title'),
                'thumbnail': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                'url': f"https://www.youtube.com/watch?v={video_id}"
            })
            
        return jsonify({'results': results, 'nextPageToken': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions', methods=['POST'])
def get_suggestions():
    data = request.json
    query = data.get('query')
    if not query: return jsonify({'results': []})
    try:
        url = f"http://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={query}"
        response = requests.get(url)
        data = response.json()
        suggestions = data[1] if len(data) > 1 else []
        return jsonify({'results': suggestions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'error': 'No URL provided'}), 400
    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [
                {'id': 'mp3', 'label': 'Audio Only (MP3)'},
                {'id': 'best_mp4', 'label': 'Best Quality (MP4)'},
                {'id': '1080p', 'label': '1080p (MP4)'},
                {'id': '720p', 'label': '720p (MP4)'}
            ]
            return jsonify({
                'title': info.get('title'), 'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'), 'formats': formats, 'original_url': url
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', 'best_mp4')
    
    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    tasks[file_id] = {
        'id': file_id, 'status': 'pending', 'progress': '0',
        'speed': '0', 'eta': '0', 'quality': quality, 'file_id': file_id
    }

    thread = threading.Thread(
        target=background_download, 
        args=(file_id, url, quality, output_template, FFMPEG_DIR)
    )
    thread.start()
    return jsonify({'task_id': file_id})

@app.route('/api/get_file/<task_id>')
def get_file(task_id):
    task = tasks.get(task_id)
    if not task or task['status'] != 'finished':
        return jsonify({'error': 'File not ready or task not found'}), 404

    final_ext = 'mp3' if task['quality'] == 'mp3' else 'mp4'
    file_path = os.path.join(DOWNLOAD_FOLDER, f"{task['file_id']}.{final_ext}")
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found on server'}), 404

    @after_this_request
    def remove_file(response):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing file: {e}")
        return response

    return send_file(file_path, as_attachment=True, download_name=f"download_{task_id}.{final_ext}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)