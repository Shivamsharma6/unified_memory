import pytest
from unittest.mock import AsyncMock, patch

try:
    from uams_sdk.diagnostics import check_system
except ImportError:
    from diagnostics import check_system


@pytest.mark.asyncio
async def test_diagnostics_check_system(tmp_path, monkeypatch):
    monkeypatch.setenv("UAMS_VAULT_PATH", str(tmp_path))

    with patch("uams_sdk.diagnostics.UAMSClient") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.health = AsyncMock(return_value={"ready": True, "storage": "ok"})

        report = await check_system("http://localhost:8000")
        assert report["vault_accessible"] is True
        assert report["server_connected"] is True
        assert report["subsystems"]["ready"] is True
