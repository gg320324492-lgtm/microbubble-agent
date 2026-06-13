#!/usr/bin/env python3
"""
update-stats.py - 准确统计项目动态 stats.json

替代 deploy-auto.sh 中的 find+wc shell 脚本，剔除 .meta/.log/.wav/.gz
等非源代码文件，按扩展名分类统计。

用法：python3 scripts/update-stats.py [output_path]
默认输出到 app/stats.json
"""
import os
import sys
import json
import datetime
import subprocess

# 排除目录（与 deploy-auto.sh 保持一致 + 补充 .next/.cache）
EXCLUDE_DIRS = [
    'node_modules', 'dist', '.git', '__pycache__',
    '.venv', 'venv', 'models', '.agents', '.next', '.cache',
]

# 排除文件（依赖锁文件、压缩包、二进制）
EXCLUDE_FILES = [
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
]

# 扩展名 → 类型分类
TYPE_MAP = {
    'python': ('.py',),
    'vue': ('.vue',),
    'javascript': ('.js', '.jsx', '.mjs', '.cjs'),
    'typescript': ('.ts', '.tsx'),
    'css': ('.css', '.scss', '.sass', '.less'),
    'html': ('.html', '.htm'),
    'markdown': ('.md', '.markdown'),
    'shell': ('.sh', '.bash', '.zsh', '.bat', '.ps1', '.cmd'),
    'config': ('.yml', '.yaml', '.toml', '.json', '.conf', '.ini', '.cfg', '.lock', '.xml', '.properties'),
    'sql': ('.sql',),
    'docker': None,  # 特殊处理：Dockerfile / docker-compose*
    'other': ('.txt', '.env', '.template'),
}


def count_lines(path: str) -> int:
    """统计文件行数（仅文本文件，二进制返回 0）"""
    try:
        with open(path, 'rb') as fh:
            content = fh.read()
        if b'\x00' in content:
            return 0
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = content.decode('gbk')
            except UnicodeDecodeError:
                return 0
        if not text:
            return 0
        return text.count('\n') + (1 if not text.endswith('\n') else 0)
    except (PermissionError, IsADirectoryError, FileNotFoundError, OSError):
        return 0


def is_docker_file(name: str) -> bool:
    return name == 'Dockerfile' or name.endswith('.dockerfile') or name.startswith('docker-compose')


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    line_counts = {k: 0 for k in TYPE_MAP}
    file_counts = {k: 0 for k in TYPE_MAP}

    for root, dirs, files in os.walk('.'):
        # 过滤排除目录
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIRS and not d.startswith('.git')
        ]
        for fname in files:
            if fname in EXCLUDE_FILES:
                continue
            if fname.startswith('.git'):
                continue

            path = os.path.join(root, fname)
            lines = count_lines(path)
            if lines == 0:
                continue

            ext = os.path.splitext(fname)[1].lower()
            matched = False

            # 特殊处理：Dockerfile
            if is_docker_file(fname):
                line_counts['docker'] += lines
                file_counts['docker'] += 1
                continue

            # 按扩展名归类
            for type_name, exts in TYPE_MAP.items():
                if exts and ext in exts:
                    line_counts[type_name] += lines
                    file_counts[type_name] += 1
                    matched = True
                    break
            if not matched:
                line_counts['other'] += lines
                file_counts['other'] += 1

    total_lines = sum(line_counts.values())
    total_files = sum(file_counts.values())

    # git 信息
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            capture_output=True, text=True, check=True
        )
        total_commits = int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        total_commits = 0

    try:
        result = subprocess.run(
            ['git', 'log', '--reverse', '--format=%ai'],
            capture_output=True, text=True, check=True
        )
        first_commit_date = result.stdout.strip().split('\n')[0][:10]
    except (subprocess.CalledProcessError, FileNotFoundError):
        first_commit_date = datetime.date.today().isoformat()

    # 开发天数（动态计算）
    try:
        first = datetime.datetime.strptime(first_commit_date, '%Y-%m-%d')
        now = datetime.datetime.now()
        dev_days = (now - first).days + 1
    except ValueError:
        dev_days = 1

    data = {
        'total_lines': total_lines,
        'total_commits': total_commits,
        'first_commit_date': first_commit_date,
        'dev_days': dev_days,
        'total_files': total_files,
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'lines_by_type': line_counts,
        'files_by_type': file_counts,
    }

    output_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join('app', 'stats.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    print(f"[OK] stats.json updated to {output_path}")
    print(f"   total_lines={total_lines} total_files={total_files} "
          f"total_commits={total_commits} dev_days={dev_days}")


if __name__ == '__main__':
    main()
