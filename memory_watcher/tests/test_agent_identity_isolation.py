import pytest
from unittest.mock import AsyncMock

try:
    from identity.store import IdentityStore
    from identity.models import IdentityProfile, TraitObject
    from uams_sdk.client import UAMSClient
except ImportError:
    from memory_watcher.identity.store import IdentityStore
    from memory_watcher.identity.models import IdentityProfile, TraitObject
    from uams_sdk.client import UAMSClient


def test_identity_store_creates_isolated_agent_profiles(tmp_path):
    store = IdentityStore(vault_path=str(tmp_path))

    # Hermes Profile
    hermes_profile = IdentityProfile(
        entity_id="Hermes",
        entity_name="Hermes Agent",
        traits={"coding_style": TraitObject(trait_id="coding_style", name="coding_style", value="concise", confidence=0.9, domain_id="coding")},
    )
    store.save_profile(hermes_profile)

    # OpenClaw Profile
    openclaw_profile = IdentityProfile(
        entity_id="OpenClaw",
        entity_name="OpenClaw Agent",
        traits={"coding_style": TraitObject(trait_id="coding_style", name="coding_style", value="verbose_with_comments", confidence=0.95, domain_id="coding")},
    )
    store.save_profile(openclaw_profile)


    # Verify both exist independently as separate JSON files
    assert (tmp_path / "Identity" / "Hermes.json").exists()
    assert (tmp_path / "Identity" / "OpenClaw.json").exists()

    loaded_hermes = store.get_profile("Hermes")
    loaded_openclaw = store.get_profile("OpenClaw")

    assert loaded_hermes.traits["coding_style"].value == "concise"
    assert loaded_openclaw.traits["coding_style"].value == "verbose_with_comments"


@pytest.mark.asyncio
async def test_sdk_identity_defaults_to_source_agent():
    client = UAMSClient(source_agent="VoiceAI")
    client._request = AsyncMock(return_value={"entity_id": "VoiceAI", "traits": {}})

    await client.get_identity()
    client._request.assert_called_once()
    assert client._request.call_args[0][2]["entity_id"] == "VoiceAI"
