from core.video.batch.processor import _get_linktree_publish_connection_issue


class _ReadyLinktree:
    def require_connected_for_publish(self):
        return True, ""


class _MissingWebhookLinktree:
    def require_connected_for_publish(self):
        return False, "Linktree 자동 발행이 켜져 있지만 Webhook URL이 없습니다."


class _LegacyDisconnectedLinktree:
    def is_connected(self):
        return False


def test_linktree_publish_issue_empty_when_ready():
    assert _get_linktree_publish_connection_issue(_ReadyLinktree()) == ""


def test_linktree_publish_issue_uses_manager_reason():
    message = _get_linktree_publish_connection_issue(_MissingWebhookLinktree())

    assert "Webhook URL" in message
    assert "Linktree 자동 발행" in message


def test_linktree_publish_issue_handles_missing_manager():
    message = _get_linktree_publish_connection_issue(None)

    assert "Linktree 매니저" in message


def test_linktree_publish_issue_handles_legacy_disconnected_manager():
    message = _get_linktree_publish_connection_issue(_LegacyDisconnectedLinktree())

    assert "연결되어 있지 않습니다" in message
