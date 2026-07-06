"""Agent control-flow exceptions."""


class BudgetExceeded(Exception):
    """Raised when a hard budget limit (calls/tokens/wall/fetches) is hit."""


class NodeOutputError(Exception):
    """Raised when an LLM node returns malformed control data after a retry."""
