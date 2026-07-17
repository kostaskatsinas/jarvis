from jarvis.core.memory import Memory


async def test_roundtrip_and_namespacing():
    a, b = Memory("ns-a"), Memory("ns-b")
    await a.put("k", {"x": 1})
    assert await a.get("k") == {"x": 1}
    assert await b.get("k") is None
    assert await a.get("missing", "fallback") == "fallback"


async def test_overwrite_keys_delete():
    m = Memory("ns-c")
    await m.put("job/1", "a")
    await m.put("job/2", "b")
    await m.put("job/1", "a2")
    assert await m.get("job/1") == "a2"
    assert sorted(await m.keys("job/")) == ["job/1", "job/2"]
    await m.delete("job/1")
    assert await m.keys() == ["job/2"]
