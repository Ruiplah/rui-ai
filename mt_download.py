"""
多线程分块下载器 - 解决单线程限速问题
8线程同时下载，支持断点续传
"""
import os
import sys
import time
import threading
import urllib.request
import ssl

URL = "https://hf-mirror.com/google/gemma-4-12B-it-qat-q4_0-gguf/resolve/main/gemma-4-12b-it-qat-q4_0.gguf"
OUTPUT = r"D:\llama\models\gemma-4-12b-it-qat-q4_0.gguf"
NUM_THREADS = 8
CHUNK_DIR = r"D:\llama\models\.chunks_gemma"

# 禁用SSL验证（hf-mirror证书可能有问题）
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get_file_size():
    """获取文件总大小"""
    req = urllib.request.Request(URL, method="HEAD")
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return int(r.headers["Content-Length"])

def download_chunk(chunk_id, start, end, total_size):
    """下载单个分块"""
    chunk_file = os.path.join(CHUNK_DIR, f"chunk_{chunk_id:02d}.part")
    # 检查已下载大小（断点续传）
    downloaded = 0
    if os.path.exists(chunk_file):
        downloaded = os.path.getsize(chunk_file)
        if downloaded >= (end - start + 1):
            print(f"[线程{chunk_id}] 已完成，跳过")
            return
    
    actual_start = start + downloaded
    if actual_start > end:
        print(f"[线程{chunk_id}] 已完成，跳过")
        return
    
    req = urllib.request.Request(URL)
    req.add_header("Range", f"bytes={actual_start}-{end}")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            mode = "ab" if downloaded > 0 else "wb"
            with open(chunk_file, mode) as f:
                while True:
                    data = response.read(1024 * 256)  # 256KB buffer
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
        print(f"[线程{chunk_id}] 完成: {downloaded//1024//1024} MB")
    except Exception as e:
        print(f"[线程{chunk_id}] 出错: {e}，已保存进度，可重试")

def merge_chunks(total_size):
    """合并所有分块"""
    print("\n开始合并分块...")
    with open(OUTPUT, "wb") as out:
        for i in range(NUM_THREADS):
            chunk_file = os.path.join(CHUNK_DIR, f"chunk_{i:02d}.part")
            if os.path.exists(chunk_file):
                with open(chunk_file, "rb") as f:
                    while True:
                        data = f.read(1024 * 1024)  # 1MB
                        if not data:
                            break
                        out.write(data)
                print(f"  已合并 chunk_{i:02d}")
            else:
                print(f"  警告: chunk_{i:02d} 不存在！")
    final_size = os.path.getsize(OUTPUT)
    print(f"\n合并完成: {final_size//1024//1024} MB (预期 {total_size//1024//1024} MB)")
    if final_size == total_size:
        print("✅ 大小校验通过！")
        # 清理临时文件
        for i in range(NUM_THREADS):
            cf = os.path.join(CHUNK_DIR, f"chunk_{i:02d}.part")
            if os.path.exists(cf):
                os.remove(cf)
        os.rmdir(CHUNK_DIR)
        print("临时文件已清理")
    else:
        print("❌ 大小不匹配，请检查")

def main():
    os.makedirs(CHUNK_DIR, exist_ok=True)
    
    print("获取文件大小...")
    total_size = get_file_size()
    print(f"文件大小: {total_size//1024//1024} MB")
    
    # 计算每个线程的分块范围
    chunk_size = total_size // NUM_THREADS
    ranges = []
    for i in range(NUM_THREADS):
        start = i * chunk_size
        end = (i + 1) * chunk_size - 1 if i < NUM_THREADS - 1 else total_size - 1
        ranges.append((start, end))
    
    print(f"\n启动 {NUM_THREADS} 个线程下载...")
    start_time = time.time()
    
    threads = []
    for i, (s, e) in enumerate(ranges):
        t = threading.Thread(target=download_chunk, args=(i, s, e, total_size))
        t.start()
        threads.append(t)
    
    # 监控进度
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        total_downloaded = 0
        for i in range(NUM_THREADS):
            cf = os.path.join(CHUNK_DIR, f"chunk_{i:02d}.part")
            if os.path.exists(cf):
                total_downloaded += os.path.getsize(cf)
        elapsed = time.time() - start_time
        speed = total_downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
        pct = total_downloaded / total_size * 100
        print(f"进度: {total_downloaded//1024//1024} MB / {total_size//1024//1024} MB ({pct:.1f}%) | 速度: {speed:.1f} MB/s | 已用: {elapsed:.0f}s")
    
    for t in threads:
        t.join()
    
    # 合并
    merge_chunks(total_size)
    elapsed = time.time() - start_time
    print(f"\n总耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")

if __name__ == "__main__":
    main()
