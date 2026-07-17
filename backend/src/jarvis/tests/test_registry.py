import pytest

from jarvis.core import registry


@registry.tool(scopes=("test-registry",))
def shout(text: str) -> str:
    """Uppercase the given text."""
    return text.upper()


@registry.tool(name="reg_double", scopes=("test-registry",))
async def double(n: int) -> int:
    """Double a number."""
    return n * 2


def test_schema_generation():
    spec = registry.get_tool("shout")
    fn = spec.schema["function"]
    assert fn["name"] == "shout"
    assert "Uppercase" in fn["description"]
    assert fn["parameters"]["properties"]["text"]["type"] == "string"


def test_resolve_by_scope_and_name():
    by_scope = {t.name for t in registry.resolve(scopes=("test-registry",))}
    assert {"shout", "reg_double"} <= by_scope
    by_name = registry.resolve(names=("shout",))
    assert [t.name for t in by_name] == ["shout"]
    with pytest.raises(KeyError):
        registry.resolve(names=("nope",))


async def test_call_tool_sync_and_async():
    assert await registry.call_tool("shout", {"text": "hi"}) == "HI"
    assert await registry.call_tool("reg_double", {"n": 4}) == "8"


def test_duplicate_name_rejected():
    with pytest.raises(ValueError):

        @registry.tool(name="shout")
        def other(x: str) -> str:
            """Dup."""
            return x
