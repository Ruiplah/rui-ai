import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from huggingface_hub import hf_hub_download
path = hf_hub_download(
    "google/gemma-4-12B-it-qat-q4_0-gguf",
    "gemma-4-12b-it-qat-q4_0.gguf",
    local_dir=r"D:\llama\models"
)
print(f"DOWNLOAD_COMPLETE: {path}")
