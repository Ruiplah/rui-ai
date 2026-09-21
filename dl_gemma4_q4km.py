import urllib.request
import ssl
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "https://hf-mirror.com/ggml-org/gemma-4-12B-it-GGUF/resolve/main/gemma-4-12B-it-Q4_K_M.gguf"
OUTPUT = r"D:\llama\models\gemma-4-12b-it-Q4_K_M.gguf"
CHUNK_DIR = r"D:\llama\models\.chunks_gemma4"
NUM_THREADS = 8

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

os.makedirs(CHUNK_DIR, exist_ok=True)

# 获取文件大小
req = urllib.request.Request(URL, method='HEAD')
req.add_header("User-Agent", "Mozilla/5.0")
with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
    total_size = int(r.headers['Content-Length'])
print(f"文件大小: {total_size//1024//1024} MB")

chunk_size = total_size // NUM_THREADS

def download_chunk(idx):
    start = idx * chunk_size
    end = (idx + 1) * chunk_size - 1 if idx < NUM_THREADS - 1 else total_size - 1
    chunk_path = os.path.join(CHUNK_DIR, f"chunk_{idx:02d}.part")
    
    # 断点续传
    existing = os.path.getsize(chunk_path) if os.path.exists(chunk_path) else 0
    if existing >= (end - start + 1):
        print(f"chunk_{idx:02d} 已完成，跳过")
        return idx
    
    req = urllib.request.Request(URL)
    req.add_header("Range", f"bytes={start+existing}-{end}")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    mode = 'ab' if existing > 0 else 'wb'
    downloaded = existing
    with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
        with open(chunk_path, mode) as f:
            while True:
                data = response.read(1024 * 256)
                if not data:
                    break
                f.write(data)
                downloaded += len(data)
    print(f"chunk_{idx:02d} 完成: {downloaded//1024//1024} MB")
    return idx

print(f"启动 {NUM_THREADS} 个线程下载...")
start_time = time.time()
with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
    futures = [executor.submit(download_chunk, i) for i in range(NUM_THREADS)]
    for f in as_completed(futures):
        f.result()

# 合并
print("合并分块...")
with open(OUTPUT, 'wb') as out:
    for i in range(NUM_THREADS):
        chunk_path = os.path.join(CHUNK_DIR, f"chunk_{i:02d}.part")
        with open(chunk_path, 'rb') as inp:
            while True:
                data = inp.read(1024*1024)
                if not data: break
                out.write(data)

final = os.path.getsize(OUTPUT)
print(f"完成: {final//1024//1024} MB ({final/1024/1024/1024:.2f} GB)")
if final == total_size:
    print("大小校验通过！")
    # 清理
    for i in range(NUM_THREADS):
        os.remove(os.path.join(CHUNK_DIR, f"chunk_{i:02d}.part"))
    os.rmdir(CHUNK_DIR)
    print("临时文件已清理")
else:
    print(f"大小不匹配! 预期 {total_size}, 实际 {final}")
