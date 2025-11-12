import subprocess

# pip freeze の結果を取得
result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
lines = result.stdout.strip().split("\n")

# 除外したいライブラリ
EXCLUDE = {
    "pip", "setuptools", "wheel", "pkg-resources",
    "distlib", "platformdirs", "filelock", "virtualenv"
}

# 出力ファイル名
output_file = "requirements.txt"

with open(output_file, "w", encoding="utf-8") as f:
    for line in lines:
        if not line.strip():
            continue
        pkg_name = line.split("==")[0].lower()
        if pkg_name in EXCLUDE:
            continue
        f.write(line + "\n")

print(f"✅ requirements.txt を作成しました ({len(lines)} 行中 {len(lines)-len(EXCLUDE)} 行を出力)")
