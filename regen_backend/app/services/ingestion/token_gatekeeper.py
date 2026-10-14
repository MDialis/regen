# app/services/ingestion/token_gatekeeper.py
import tiktoken


class TokenGatekeeper:
    """
    Calculates token footprints using tiktoken to quantify deterministic savings
    and prevent context-window overflow before any LLM call is made.
    """

    def __init__(self, encoding_name: str = "o200k_base") -> None:
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Fallback to cl100k_base if o200k_base is unavailable
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def truncate_to_budget(self, text: str, max_tokens: int) -> str:
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoder.decode(tokens[:max_tokens])


token_gatekeeper = TokenGatekeeper()
