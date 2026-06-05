"""LLM subsystem — adapters, registry, cache, and public interface."""

from contractfol.llm.interface import generate, generate_sync

__all__ = ["generate", "generate_sync"]
