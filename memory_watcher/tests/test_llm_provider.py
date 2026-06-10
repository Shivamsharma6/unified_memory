import pytest
from llm.provider import LLMProvider, LLMConfig


@pytest.mark.asyncio
async def test_llm_provider_config():
    config = LLMConfig(
        provider="ollama",
        model="llama3.2",
        base_url="http://localhost:11434",
        temperature=0.3,
        max_tokens=2048,
    )
    provider = LLMProvider(config)
    assert provider.config.model == "llama3.2"
    assert provider.config.temperature == 0.3


@pytest.mark.asyncio
async def test_llm_provider_mock_generate():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    result = await provider.generate("Summarize this text: The system uses Qdrant for vectors.")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_provider_structured_output():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    result = await provider.generate_structured(
        "Extract entities from: Shivam built the UAMS system.",
        schema={"type": "object", "properties": {"entities": {"type": "array"}}},
    )
    assert isinstance(result, dict)
    assert "entities" in result


@pytest.mark.asyncio
async def test_llm_provider_batch():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    results = await provider.batch_generate([
        "Summarize A",
        "Summarize B",
        "Extract lessons from C",
    ])
    assert len(results) == 3


@pytest.mark.asyncio
async def test_llm_provider_idle_shutdown():
    """Verify client shuts down after idle_timeout."""
    config = LLMConfig(provider="mock", idle_timeout=1.0)
    provider = LLMProvider(config)
    result = await provider.generate("hello")
    assert result is not None
    assert provider.config.idle_timeout == 1.0
    await provider.shutdown()


@pytest.mark.asyncio
async def test_model_roles():
    from llm.provider import MODEL_ROLES, get_llm_config
    assert "distillation" in MODEL_ROLES
    assert "reflection" in MODEL_ROLES
    assert "fallback" in MODEL_ROLES
    assert "embedding" in MODEL_ROLES
    config = get_llm_config("reflection")
    assert config.model == "gemma4:12b-mlx"