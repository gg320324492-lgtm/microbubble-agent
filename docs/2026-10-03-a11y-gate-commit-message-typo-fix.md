# 9cb3337c1 commit message 两处乱码更正 (2026-10-03)

`9cb3337c1` 的 commit message 有 2 处字符在写入时被写成 U+FFFD 替换字符:

| 行 | 现存(乱码) | 应为 |
|---|---|---|
| 20 | 现状比入库基线多 17 条真`���`违规, 旧流程报 success。 | 现状比入库基线多 17 条**真**违规, 旧流程报 success。 |
| 30 | 修 debug 步骤的 glob: 原`��` `test-results/*-actual.txt` 单层 | 修 debug 步骤的 glob: 原本 `test-results/*-actual.txt` 单层 |

被改的**文件本身干净** (`git show HEAD:.github/workflows/playwright.yml` 无 U+FFFD),
乱码只在 commit message 的说明文字里, 不影响门禁行为。

## 为什么不 amend

该 commit 已被 post-commit hook 自动 push 到 `origin/main` (HEAD 与 origin/main 同为
9cb3337c1)。已推送的历史不能 amend (会 force-push 改写公共分支)。按本仓库既有惯例
处理 —— 参照 `45cfaae17` / `09b9bf05f` / `8eaea56a9` 三次同类更正, 均为新增 docs commit
说明, 不动历史。

## 成因与防范

本次用 `cat > /tmp/commitmsg.txt <<'EOF'` heredoc 写中文 commit message, 在 Windows
Git Bash 下该 heredoc 路径会把部分多字节字符转成 U+FFFD。后续写中文 commit message
建议改用 `git commit -F <file>` + Write 工具直接写文件 (与本次最终提交方式一致,
无乱码), 或提交后立即 `git log -1 --format=%B | grep $'�'` 核验。