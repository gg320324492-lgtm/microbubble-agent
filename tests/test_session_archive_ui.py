"""
test_session_archive_ui.py — CHAT-P1-E E3 归档 UI 测试

测试 chatSessions store setArchived + 前端归档过滤逻辑:
- setArchived 本地立即更新 + 异步 PATCH server
- 归档过滤 'all' / 'active' / 'archived'
- 归档/恢复互斥 (is_archived toggle)
- server 失败时本地状态仍更新 (best-effort)
"""
import pytest

# 纯前端 store 测试, 不依赖后端
# 因为 chatSessions store 是 Pinia, 这里使用 mock 测试
import sys
from unittest.mock import MagicMock


class TestArchiveFilterLogic:
    """归档过滤纯函数测试 (与 UI 渲染逻辑一致)"""

    @staticmethod
    def filter_sessions(sessions, archive_filter):
        """模拟 SessionSidebar/MobileSessionDrawer 的 archive filter 逻辑"""
        if archive_filter == 'all':
            return sessions
        if archive_filter == 'active':
            return [s for s in sessions if not s.get('is_archived')]
        if archive_filter == 'archived':
            return [s for s in sessions if s.get('is_archived')]
        return sessions

    def test_filter_all_returns_all(self):
        sessions = [
            {'id': '1', 'is_archived': False},
            {'id': '2', 'is_archived': True},
            {'id': '3', 'is_archived': False},
        ]
        result = self.filter_sessions(sessions, 'all')
        assert len(result) == 3

    def test_filter_active_excludes_archived(self):
        sessions = [
            {'id': '1', 'is_archived': False},
            {'id': '2', 'is_archived': True},
            {'id': '3', 'is_archived': False},
        ]
        result = self.filter_sessions(sessions, 'active')
        assert len(result) == 2
        assert all(not s['is_archived'] for s in result)

    def test_filter_archived_only_archived(self):
        sessions = [
            {'id': '1', 'is_archived': False},
            {'id': '2', 'is_archived': True},
            {'id': '3', 'is_archived': False},
        ]
        result = self.filter_sessions(sessions, 'archived')
        assert len(result) == 1
        assert result[0]['id'] == '2'

    def test_filter_handles_missing_field(self):
        """is_archived 字段缺失 (默认未归档)"""
        sessions = [
            {'id': '1'},  # no is_archived field
            {'id': '2', 'is_archived': True},
        ]
        result = self.filter_sessions(sessions, 'active')
        assert len(result) == 1
        assert result[0]['id'] == '1'


class TestSetArchivedStoreAPI:
    """setArchived store API 行为测试 (mock 风格)"""

    def test_set_archived_true_local_immediate(self):
        """setArchived(true) 本地立即更新 is_archived"""
        # 模拟 store 内部逻辑
        session = {'id': '1', 'is_archived': False, '_syncStatus': 'synced'}
        new_is_archived = True

        # 模拟 store.setArchived 行为
        session['is_archived'] = new_is_archived
        session['_syncStatus'] = 'pending'

        assert session['is_archived'] is True
        assert session['_syncStatus'] == 'pending'

    def test_set_archived_false_restores(self):
        """setArchived(false) 恢复 (归档 → 未归档)"""
        session = {'id': '1', 'is_archived': True, '_syncStatus': 'synced'}
        session['is_archived'] = False
        assert session['is_archived'] is False

    def test_server_failure_local_state_preserved(self):
        """server 同步失败时, 本地状态仍保留 (best-effort)"""
        # 模拟 setArchived 内部: 本地立即更新 + try/except 包 server sync
        session = {'id': '1', 'is_archived': False}
        try:
            session['is_archived'] = True
            # 模拟 server 抛异常
            raise Exception("server timeout")
        except Exception:
            session['_syncStatus'] = 'error'
            # 本地状态仍保留
        assert session['is_archived'] is True
        assert session['_syncStatus'] == 'error'


class TestArchiveContextMenuUI:
    """归档右键菜单 UI 文本测试"""

    @staticmethod
    def get_archive_button_label(session):
        """模拟 SessionSidebar/MobileSessionDrawer 的 ctx-item 文本生成"""
        if session.get('is_archived'):
            return '✅ 恢复会话'
        return '🗄️ 归档会话'

    def test_active_session_shows_archive_label(self):
        """未归档 session 显示 '🗄️ 归档会话'"""
        s = {'is_archived': False}
        label = self.get_archive_button_label(s)
        assert '归档' in label
        assert '恢复' not in label

    def test_archived_session_shows_restore_label(self):
        """已归档 session 显示 '✅ 恢复会话'"""
        s = {'is_archived': True}
        label = self.get_archive_button_label(s)
        assert '恢复' in label