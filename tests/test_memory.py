import asyncio

from agentorch.core import Message
from agentorch.memory import MemoryManager


def test_memory_thread_isolation():
    asyncio.run(_test_memory_thread_isolation())


async def _test_memory_thread_isolation():
    memory = MemoryManager()
    await memory.append_message("thread-a", Message(role="user", content="hello"))
    await memory.append_message("thread-b", Message(role="user", content="world"))
    assert len(await memory.get_thread_messages("thread-a")) == 1
    assert (await memory.get_thread_messages("thread-a"))[0].content == "hello"
    assert (await memory.get_thread_messages("thread-b"))[0].content == "world"


def test_checkpoint_roundtrip():
    asyncio.run(_test_checkpoint_roundtrip())


async def _test_checkpoint_roundtrip():
    memory = MemoryManager()
    await memory.checkpoint("thread-a", "cp1", {"step": 1})
    payload = await memory.load_checkpoint("thread-a", "cp1")
    assert payload == {"step": 1}
