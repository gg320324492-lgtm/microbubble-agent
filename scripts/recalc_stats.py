"""重新计算项目统计 — 本地 Python 按扩展名 + 严格 exclude + 二进制检测"""
import os
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json

EXCLUDE_DIRS = {
    'node_modules', '.git', 'dist', '__pycache__', '.venv', 'venv',
    'frp', '.meta', '.log', '.wav', '.exe', '.cache', 'models',
    '.claude', 'data',  # postgres/minio runtime data
    'results',  # 临时结果
    '.agents',  # skill scripts (本地工具，不算项目源码)
    '.vscode',
}
EXCLUDE_EXT = {
    '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg',
    '.woff', '.woff2', '.ttf', '.eot',
    '.webm', '.wav', '.mp3', '.mp4', '.zip', '.tar', '.gz',
    '.pdf', '.docx', '.xlsx', '.pptx',
    '.1', '.2', '.3', '.4', '.5',  # MinIO 大文件分片 part.N
    '.log',  # frpc/runtime 日志
}

EXT_TYPE = {
    '.py': 'python', '.vue': 'vue', '.js': 'javascript', '.ts': 'typescript',
    '.css': 'css', '.scss': 'css', '.html': 'html', '.md': 'markdown',
    '.sh': 'shell', '.bat': 'shell', '.ps1': 'shell', '.vbs': 'shell',
    '.sql': 'sql', '.yml': 'config', '.yaml': 'config',
    '.json': 'config', '.jsonl': 'config', '.toml': 'config',
    '.ini': 'config', '.conf': 'config', '.env': 'config',
    '.example': 'config', '.service': 'config',
    '.csv': 'other', '.txt': 'config', '.tag': 'other',
    '.cjs': 'javascript', '.mjs': 'javascript',
    '.mako': 'other',
    '.whisper': 'docker', '.mcp': 'docker', '.db': 'docker',
    '.voice-pipeline': 'docker', '.webhook': 'docker',
}

# 按文件名判断类型
NAME_TYPE = {
    'Dockerfile': 'docker',
    '.env': 'config', '.gitignore': 'config', '.hintrc': 'config',
    'requirements.txt': 'config',
    'start.bat': 'shell', 'status.bat': 'shell',
}

total_lines = 0
total_files = 0
lines_by_type = defaultdict(int)
files_by_type = defaultdict(int)

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for f in files:
        p = Path(root) / f
        if any(ex in p.parts for ex in EXCLUDE_DIRS):
            continue
        if p.suffix.lower() in EXCLUDE_EXT:
            continue
        try:
            if p.stat().st_size > 1024 * 1024:
                continue
        except OSError:
            continue
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
            n_lines = len(content.splitlines())
        except Exception:
            continue
        total_lines += n_lines
        total_files += 1
        ext = p.suffix.lower()
        if f in NAME_TYPE:
            t = NAME_TYPE[f]
        elif f == 'Dockerfile':
            t = 'docker'
        elif ext in EXT_TYPE:
            t = EXT_TYPE[ext]
        else:
            t = 'other'
        lines_by_type[t] += n_lines
        files_by_type[t] += 1

commit_count = int(subprocess.check_output(['git', 'rev-list', '--count', 'HEAD']).strip())
first_commit_date = subprocess.check_output(['git', 'log', '--reverse', '--format=%cs']).splitlines()[0].decode().strip()
first_dt = datetime.strptime(first_commit_date, '%Y-%m-%d')
days = (datetime.now() - first_dt).days + 1

stats = {
    'total_lines': total_lines,
    'total_commits': commit_count,
    'first_commit_date': first_commit_date,
    'dev_days': days,
    'total_files': total_files,
    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'lines_by_type': dict(lines_by_type),
    'files_by_type': dict(files_by_type),
}
with open('app/stats.json', 'w', encoding='utf-8') as fh:
    json.dump(stats, fh, indent=2, ensure_ascii=False)
print(f'total_lines={total_lines} total_commits={commit_count} total_files={total_files} dev_days={days} first={first_commit_date}')
print('--- by_type ---')
for k, v in sorted(stats['lines_by_type'].items(), key=lambda x: -x[1]):
    print(f'  {k:12s}: {v:7d} lines, {stats["files_by_type"][k]:3d} files')