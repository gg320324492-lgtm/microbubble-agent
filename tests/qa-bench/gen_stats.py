"""重新生成 app/stats.json"""
import os
import re
import sys
import subprocess
import datetime
import json
from collections import Counter
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 第一 commit 日期
out = subprocess.check_output(['git', 'log', '--reverse', '--format=%as']).decode().strip()
first_date = out.split('\n')[0] if out else 'unknown'
total_commits = int(subprocess.check_output(['git', 'rev-list', '--count', 'HEAD']).decode().strip())
d1 = datetime.date.fromisoformat(first_date)
dev_days = (datetime.date.today() - d1).days + 1

# 数行（按扩展名）
EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', 'dist', '.meta',
                'frp', 'models', 'logs', '.pytest_cache', '.agents', '.codex', '.claude'}
EXCLUDE_EXTS = {'.wav', '.mp3', '.mp4', '.log', '.sqlite', '.pyc', '.png', '.jpg',
                '.jpeg', '.gif', '.ico', '.webp', '.pdf', '.zip', '.tar', '.gz'}

EXT_MAP = {
    '.py': 'python', '.vue': 'vue', '.js': 'javascript', '.ts': 'typescript',
    '.css': 'css', '.html': 'html', '.md': 'markdown', '.json': 'json',
    '.sql': 'sql', '.sh': 'shell', '.ps1': 'powershell', '.yml': 'config',
    '.yaml': 'config', '.toml': 'config', '.ini': 'config', '.env': 'config',
    '.conf': 'config', '.txt': 'other', '.csv': 'other', '': 'other',
}

lines_by_type = Counter()
files_by_type = Counter()
total_lines = 0
total_files = 0

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for f in files:
        path = Path(root) / f
        ext = os.path.splitext(f)[1].lower()
        if ext in EXCLUDE_EXTS:
            continue
        cat = EXT_MAP.get(ext, 'other')
        try:
            with open(path, 'rb') as fp:
                content = fp.read()
            if b'\x00' in content[:8192]:
                continue
            try:
                text = content.decode('utf-8', errors='strict')
            except UnicodeDecodeError:
                continue
            n_lines = text.count('\n') + 1
            lines_by_type[cat] += n_lines
            files_by_type[cat] += 1
            total_lines += n_lines
            total_files += 1
        except (PermissionError, FileNotFoundError):
            continue

print(f'总行数: {total_lines}')
print(f'总文件: {total_files}')
print(f'总提交: {total_commits}')
print(f'开发天数: {dev_days}')

print('\n按类型行数:')
for k, v in sorted(lines_by_type.items(), key=lambda x: -x[1]):
    print(f'  {k:15s} {v:8d} ({files_by_type[k]:4d} files)')

out = {
    'total_lines': total_lines,
    'total_commits': total_commits,
    'first_commit_date': first_date,
    'dev_days': dev_days,
    'total_files': total_files,
    'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'lines_by_type': dict(lines_by_type),
    'files_by_type': dict(files_by_type),
}
os.makedirs('app', exist_ok=True)
with open('app/stats.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('\n✅ 写入 app/stats.json')
