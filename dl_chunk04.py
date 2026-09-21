import urllib.request
import ssl
import time
import os

URL = "https://hf-mirror.com/google/gemma-4-12B-it-qat-q4_0-gguf/resolve/main/gemma-4-12b-it-qat-q4_0.gguf"
OUTPUT = r"D:\llama\models\.chunks_gemma\chunk_04.part"
TOTAL = 6975879296
CHUNK = TOTAL // 8
START = 4 * CHUNK
END = 5 * CHUNK - 1

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print(f"下载 chunk_04: {START}-{END} ({(END-START+1)//1024//1024} MB)")

req = urllib.request.Request(URL)
req.add_header("Range", f"bytes={START}-{END}")
req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

downloaded = 0
start_time = time.time()
with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
    with open(OUTPUT, "wb") as f:
        while True:
            data = response.read(1024 * 256)
            if not data:
                break
            f.write(data)
            downloaded += len(data)
            if downloaded % (1024*1024*50) < 1024*256:
                elapsed = time.time() - start_time
                speed = downloaded / elapsed / 1024 / 1024
                print(f"  {downloaded//1024//1024} MB, 速度 {speed:.1f} MB/s")

final = os.path.getsize(OUTPUT)
print(f"完成: {final//1024//1024} MB")
