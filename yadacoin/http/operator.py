"""Compatibility shim. Operator routes live in plugins.operator."""

from plugins.operator.handlers import HANDLERS, OPERATOR_HANDLERS

__all__ = ["OPERATOR_HANDLERS", "HANDLERS"]
