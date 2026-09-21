import os
chunk_dir = r"D:\llama\models\.chunks_gemma"
output = r"D:\llama\models\gemma-4-12b-it-qat-q4_0.gguf"
files = sorted([f for f in os.listdir(chunk_dir) if f.endswith('.part')])
print(f"合并 {len(files)} 个分块...")
with open(output, 'wb') as out:
    for f in files:
        path = os.path.join(chunk_dir, f)
        size = os.path.getsize(path)
        print(f"  {f}: {size//1024//1024} MB")
        with open(path, 'rb') as inp:
            while True:
                data = inp.read(1024*1024)
                if not data: break
                out.write(data)
final = os.path.getsize(output)
print(f"\n完成: {final//1024//1024} MB ({final/1024/1024/1024:.2f} GB)")
if final >= 6900000000:
    print("大小校验通过")
    for f in files:
        os.remove(os.path.join(chunk_dir, f))
    os.rmdir(chunk_dir)
    print("临时文件已清理")
