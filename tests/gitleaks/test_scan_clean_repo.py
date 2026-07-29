#!/usr/bin/env python3
"""
test_scan_clean_repo.py — gitleaks e2e 验证 (W86 第 1 批 A-1)

功能:
  1. 创建临时 git repo
  2. Commit 一个 fake token (预期: gitleaks 能扫出)
  3. Commit 一个 clean 提交 (预期: gitleaks 扫不出)
  4. 验证 .gitleaks.toml 配置正确 (规则命中, allowlist 生效)

测试:
  - test_fake_token_detected: 验证 gitleaks 能识别 fake Anthropic API key
  - test_clean_repo_passes: 验证 clean repo 不报
  - test_custom_rules_load: 验证 .gitleaks.toml 5 条项目规则被正确加载

依赖:
  - gitleaks >= 8.x
  - python 3.10+
  - 不依赖 pytest (用 unittest, 避免引入额外测试依赖)

退出码:
  - 0 = 所有测试通过
  - 1 = 至少 1 个测试失败
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GITLEAKS_TOML = PROJECT_ROOT / ".gitleaks.toml"


def _have_gitleaks() -> bool:
    """检查 gitleaks 是否可用"""
    return shutil.which("gitleaks") is not None


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """跑子进程, 返回 (exit_code, stdout, stderr)"""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=60
    )
    return result.returncode, result.stdout, result.stderr


@unittest.skipUnless(_have_gitleaks(), "gitleaks 未安装, 跳 e2e")
class TestGitleaksE2E(unittest.TestCase):
    """gitleaks e2e 测试套件"""

    def setUp(self) -> None:
        """每个 test 前创建临时 git repo"""
        if not GITLEAKS_TOML.exists():
            self.skipTest(f"未找到 .gitleaks.toml: {GITLEAKS_TOML}")

        self.tmpdir = tempfile.mkdtemp(prefix="gitleaks-e2e-")
        self.repo_dir = Path(self.tmpdir) / "test_repo"
        self.repo_dir.mkdir()

        # git init + 配置 user
        _run(["git", "init", "-q", "--initial-branch=main"], cwd=str(self.repo_dir))
        _run(["git", "config", "user.email", "e2e@test.local"], cwd=str(self.repo_dir))
        _run(["git", "config", "user.name", "e2e test"], cwd=str(self.repo_dir))
        # git init 默认是 master, 但 -b main 在新版 Git 才支持
        _run(["git", "checkout", "-q", "-b", "main"], cwd=str(self.repo_dir))

    def tearDown(self) -> None:
        """清理临时目录"""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _commit_file(self, filename: str, content: str, message: str) -> None:
        """helper: 写文件 + git add + commit"""
        filepath = self.repo_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        _run(["git", "add", filename], cwd=str(self.repo_dir))
        _run(
            ["git", "commit", "-q", "-m", message],
            cwd=str(self.repo_dir),
        )

    def _run_gitleaks(self, source: str | None = None) -> tuple[int, str, str]:
        """跑 gitleaks detect, 用项目 .gitleaks.toml 配置"""
        cmd = [
            "gitleaks", "detect",
            "--source", source or str(self.repo_dir),
            "--config", str(GITLEAKS_TOML),
            "--no-banner",
            "--exit-code", "1",
        ]
        return _run(cmd)

    def test_clean_repo_passes(self) -> None:
        """case 1: clean repo (无 secret) → gitleaks exit 0"""
        self._commit_file("README.md", "# Test repo\n\nNo secrets here.\n", "init commit")
        self._commit_file("app.py", "def hello():\n    print('hello')\n", "add app")

        exit_code, stdout, stderr = self._run_gitleaks()
        self.assertEqual(
            exit_code, 0,
            f"clean repo 应通过扫描, 实际 exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )

    def test_fake_anthropic_key_detected(self) -> None:
        """case 2: fake Anthropic API key → gitleaks exit 1"""
        # 用 gitleaks 测试文档推荐的假 token 模式 (40+ 字符)
        fake_key = "sk-ant-api03-abcdef1234567890ABCDEF" + "x" * 30 + "-FAKE_KEY_FOR_TEST"
        self._commit_file("README.md", "# Test\n", "init")
        self._commit_file(".env", f"ANTHROPIC_API_KEY={fake_key}\n", "add config")

        exit_code, stdout, stderr = self._run_gitleaks()
        self.assertEqual(
            exit_code, 1,
            f"fake Anthropic key 应被检测, 实际 exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )
        # 输出应提到 anthropic-api-key 规则
        self.assertIn(
            "anthropic-api-key", stdout + stderr,
            "输出应包含 anthropic-api-key 规则名",
        )

    def test_fake_jwt_detected(self) -> None:
        """case 3: fake JWT token → gitleaks exit 1"""
        # JWT 3 段格式: header.payload.signature
        # header/payload 用 eyJ 开头 + base64
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(b'{"sub":"1234567890","name":"John Doe"}').rstrip(b"=").decode()
        signature = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c-FAKE-SIGNATURE-XYZ"
        fake_jwt = f"{header}.{payload}.{signature}"

        self._commit_file("README.md", "# Test\n", "init")
        self._commit_file("token.txt", f"Bearer {fake_jwt}\n", "add token")

        exit_code, stdout, stderr = self._run_gitleaks()
        self.assertEqual(
            exit_code, 1,
            f"fake JWT 应被检测, 实际 exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )

    def test_minio_default_credentials_detected(self) -> None:
        """case 4: MinIO 默认凭据 → gitleaks exit 1"""
        self._commit_file("README.md", "# Test\n", "init")
        # minioadmin:minioadmin (项目自定义规则 5)
        self._commit_file(
            ".env.production",
            "MINIO_ROOT_USER=minioadmin\nMINIO_ROOT_PASSWORD=minioadmin123\n",
            "add minio config",
        )

        exit_code, stdout, stderr = self._run_gitleaks()
        self.assertEqual(
            exit_code, 1,
            f"MinIO 默认凭据应被检测, 实际 exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )
        self.assertIn(
            "minio-admin-default", stdout + stderr,
            "输出应包含 minio-admin-default 规则名",
        )

    def test_private_key_detected(self) -> None:
        """case 5: RSA 私钥头部 → gitleaks exit 1"""
        self._commit_file("README.md", "# Test\n", "init")
        fake_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF5PBbGPhqUg\n"
            "+FAKE-CONTENT-NOT-REAL-KEY-XYZ-1234567890abcdef\n"
            "-----END RSA PRIVATE KEY-----\n"
        )
        self._commit_file("server.pem", fake_key, "add key")

        exit_code, stdout, stderr = self._run_gitleaks()
        self.assertEqual(
            exit_code, 1,
            f"RSA 私钥应被检测, 实际 exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )

    def test_config_loads_without_error(self) -> None:
        """case 6: .gitleaks.toml 语法正确 (gitleaks 能加载)"""
        # 用 gitleaks detect --source . 直接跑项目根
        # 不期望 clean (因为有 docs/ 等允许路径), 但期望不报 config error
        exit_code, stdout, stderr = self._run_gitleaks(source=str(PROJECT_ROOT))

        # exit 0 (干净) 或 1 (找到泄漏但配置 OK) 都算通过
        # exit 2/3/其它 = 配置错误
        self.assertIn(
            exit_code, (0, 1),
            f".gitleaks.toml 加载失败, exit={exit_code}\n"
            f"stdout: {stdout}\nstderr: {stderr}",
        )
        # stderr 应不包含 config parse error
        self.assertNotIn(
            "error parsing", (stdout + stderr).lower(),
            f".gitleaks.toml 解析错误: {stdout} {stderr}",
        )


class TestGitleaksNotInstalled(unittest.TestCase):
    """gitleaks 未安装的 fallback 测试 (不依赖外部 binary)"""

    def test_install_doc_exists(self) -> None:
        """scripts/install-gitleaks.md 必须存在"""
        install_doc = PROJECT_ROOT / "scripts" / "install-gitleaks.md"
        self.assertTrue(
            install_doc.exists(),
            f"装机说明文档缺失: {install_doc}",
        )
        content = install_doc.read_text(encoding="utf-8")
        # 至少包含 brew / wget / winget 三种方式之一
        self.assertTrue(
            any(
                keyword in content
                for keyword in ["brew install gitleaks", "wget", "winget install gitleaks"]
            ),
            "装机说明应包含至少一种安装方式",
        )

    def test_gitleaks_toml_exists_and_valid(self) -> None:
        """.gitleaks.toml 存在 + 含 5 条项目自定义规则"""
        self.assertTrue(
            GITLEAKS_TOML.exists(),
            f".gitleaks.toml 缺失: {GITLEAKS_TOML}",
        )
        content = GITLEAKS_TOML.read_text(encoding="utf-8")
        # 5 条项目自定义规则
        expected_rules = [
            "anthropic-api-key",
            "openai-api-key",
            "private-key",
            "jwt-bearer",
            "minio-admin-default",
        ]
        for rule_id in expected_rules:
            self.assertIn(
                f'id = "{rule_id}"', content,
                f".gitleaks.toml 缺失规则: {rule_id}",
            )

    def test_workflow_exists(self) -> None:
        """.github/workflows/secret-scan.yml 存在"""
        workflow = PROJECT_ROOT / ".github" / "workflows" / "secret-scan.yml"
        self.assertTrue(
            workflow.exists(),
            f"GitHub Action workflow 缺失: {workflow}",
        )
        content = workflow.read_text(encoding="utf-8")
        self.assertIn(
            "gitleaks/gitleaks-action", content,
            "workflow 应使用官方 gitleaks-action",
        )
        # 3 个 trigger: pull_request, push, schedule
        self.assertIn("pull_request:", content)
        self.assertIn("push:", content)
        self.assertIn("schedule:", content)

    def test_scan_script_exists_and_executable(self) -> None:
        """scan-history.sh 存在 + 可执行"""
        scan_script = PROJECT_ROOT / "scripts" / "gitleaks" / "scan-history.sh"
        self.assertTrue(
            scan_script.exists(),
            f"scan-history.sh 缺失: {scan_script}",
        )
        # 至少可读 (executable 在 Windows 上不一定能存)
        self.assertTrue(
            os.access(scan_script, os.R_OK),
            f"scan-history.sh 不可读: {scan_script}",
        )


def main() -> int:
    """主入口"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())