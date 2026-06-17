// recalc_stats.js — Node.js version (host Python 不可用,改用 Node)
// 与 recalc_stats.py 逻辑一致
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const EXCLUDE_DIRS = new Set([
  'node_modules', '.git', 'dist', '__pycache__', '.venv', 'venv',
  'frp', '.meta', '.log', '.wav', '.exe', '.cache', 'models',
  '.claude', 'data', 'results', '.agents', '.vscode', 'backups',
  '.next', '.codex', 'web/node_modules', 'web/dist',
]);
const EXCLUDE_EXT = new Set([
  '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg',
  '.woff', '.woff2', '.ttf', '.eot',
  '.webm', '.wav', '.mp3', '.mp4', '.zip', '.tar', '.gz',
  '.pdf', '.docx', '.xlsx', '.pptx', '.log', '.exe',
]);
const EXT_TYPE = {
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
};
const NAME_TYPE = {
  Dockerfile: 'docker',
  '.env': 'config', '.gitignore': 'config', '.hintrc': 'config',
  'requirements.txt': 'config',
  'start.bat': 'shell', 'status.bat': 'shell',
};

const root = process.cwd();
let totalLines = 0;
let totalFiles = 0;
const linesByType = {};
const filesByType = {};
for (const k of new Set([...Object.values(EXT_TYPE), ...Object.values(NAME_TYPE)])) {
  linesByType[k] = 0;
  filesByType[k] = 0;
}

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) continue;
      walk(full);
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (EXCLUDE_EXT.has(ext)) continue;
      let st;
      try { st = fs.statSync(full); } catch { continue; }
      if (st.size > 1024 * 1024) continue;
      let content;
      try { content = fs.readFileSync(full, 'utf8'); } catch { continue; }
      const n = content.length === 0 ? 0 : content.split('\n').length;
      totalLines += n;
      totalFiles += 1;
      let t;
      if (NAME_TYPE[entry.name]) t = NAME_TYPE[entry.name];
      else if (entry.name === 'Dockerfile') t = 'docker';
      else if (EXT_TYPE[ext]) t = EXT_TYPE[ext];
      else t = 'other';
      linesByType[t] = (linesByType[t] || 0) + n;
      filesByType[t] = (filesByType[t] || 0) + 1;
    }
  }
}
walk(root);

const commitCount = parseInt(execSync('git rev-list --count HEAD', { encoding: 'utf8' }).trim(), 10);
const firstDate = execSync('git log --reverse --format=%cs', { encoding: 'utf8' }).split('\n')[0].trim();
const firstDt = new Date(firstDate);
const now = new Date();
const devDays = Math.floor((now - firstDt) / 86400000) + 1;

const stats = {
  total_lines: totalLines,
  total_commits: commitCount,
  first_commit_date: firstDate,
  dev_days: devDays,
  total_files: totalFiles,
  updated_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
  lines_by_type: linesByType,
  files_by_type: filesByType,
};
fs.writeFileSync(path.join('app', 'stats.json'), JSON.stringify(stats, null, 2), 'utf8');
console.log(`total_lines=${totalLines} total_files=${totalFiles} total_commits=${commitCount} dev_days=${devDays} first=${firstDate}`);
console.log('--- by_type ---');
const sorted = Object.entries(linesByType).sort((a, b) => b[1] - a[1]);
for (const [k, v] of sorted) {
  console.log(`  ${k.padEnd(12)}: ${String(v).padStart(7)} lines, ${String(filesByType[k]).padStart(3)} files`);
}
