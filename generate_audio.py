"""
VOICEVOX API を使って SPEECHES_PRESS の音声を一括生成するスクリプト
前提: VOICEVOX が localhost:50021 で起動済みであること
     ffmpeg がインストール済みであること
"""

import re
import os
import requests

VOICEVOX_URL = "http://localhost:50021"
SPEAKER_ID   = 3          # 3 = ずんだもん
OUTPUT_DIR   = "audio"
HTML_FILE    = "index.html"

# ----------------------------------------------------------------
# index.html から SPEECHES_PRESS 配列の文字列を抽出
# ----------------------------------------------------------------
with open(HTML_FILE, encoding="utf-8") as f:
    html = f.read()

# const SPEECHES_PRESS = [ ... ]; の中身を取得
m = re.search(r"const SPEECHES_PRESS\s*=\s*(\[[\s\S]*?\]);", html)
if not m:
    raise RuntimeError("SPEECHES_PRESS 配列が見つかりませんでした")

speeches_js = m.group(1)

# クォートされた文字列を全件抽出
raw_texts = re.findall(r'"((?:[^"\\]|\\.)*)"', speeches_js)
print(f"取得件数: {len(raw_texts)} 件")


def clean(text):
    """エスケープシーケンスを処理し、\n を 。に変換"""
    text = text.replace("\\n", "。")
    text = text.replace('\\"', '"')
    text = text.replace("\\\\", "\\")
    return text


texts = [clean(t) for t in raw_texts]

# ----------------------------------------------------------------
# 出力フォルダ作成
# ----------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ----------------------------------------------------------------
# VOICEVOX で音声生成
# ----------------------------------------------------------------
import subprocess
import tempfile

total = len(texts)
for i, text in enumerate(texts):
    filename = os.path.join(OUTPUT_DIR, f"{i+1:03d}.mp3")

    if os.path.exists(filename):
        print(f"[{i+1:3d}/{total}] スキップ（既存）: {filename}")
        continue

    print(f"[{i+1:3d}/{total}] 生成中: {text[:40]}...")

    # 1. audio_query
    r = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": SPEAKER_ID},
    )
    r.raise_for_status()
    query = r.json()

    # 2. synthesis → wav
    r = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": SPEAKER_ID},
        json=query,
        headers={"Content-Type": "application/json"},
    )
    r.raise_for_status()
    wav_data = r.content

    # 3. wav → mp3 変換（ffmpeg）
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_data)
        tmp_path = tmp.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_path,
             "-codec:a", "libmp3lame", "-q:a", "2", filename],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        os.unlink(tmp_path)

    print(f"         → 保存: {filename}")

print(f"\n完了: {OUTPUT_DIR}/ に {total} ファイル生成しました")
