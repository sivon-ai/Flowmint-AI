"""
Custom exceptions for Flowmint AI.

These are caught by exception handlers in main.py and converted to proper HTTP responses.
"""


class FlowmintError(Exception):
    """Base exception for all Flowmint errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(FlowmintError):
    def __init__(self, resource: str, identifier: str = ""):
        detail = f"{resource} not found" + (f": {identifier}" if identifier else "")
        super().__init__(detail, code="NOT_FOUND", status_code=404)


class ValidationError(FlowmintError):
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR", status_code=422)


class AuthenticationError(FlowmintError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, code="AUTHENTICATION_ERROR", status_code=401)


class AuthorizationError(FlowmintError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, code="AUTHORIZATION_ERROR", status_code=403)


class ConflictError(FlowmintError):
    def __init__(self, message: str):
        super().__init__(message, code="CONFLICT", status_code=409)


class PaymentError(FlowmintError):
    def __init__(self, message: str):
        super().__init__(message, code="PAYMENT_ERROR", status_code=400)


class InvalidStateTransitionError(FlowmintError):
    def __init__(self, entity: str, current_state: str, target_state: str):
        message = f"{entity} cannot transition from '{current_state}' to '{target_state}'"
        super().__init__(message, code="INVALID_STATE_TRANSITION", status_code=409)


class DuplicateError(FlowmintError):
    def __init__(self, message: str = "Duplicate operation detected"):
        super().__init__(message, code="DUPLICATE", status_code=409)


class InsufficientStockError(FlowmintError):
    def __init__(self, product_name: str, available: int, requested: int):
        message = f"Insufficient stock for '{product_name}': {available} available, {requested} requested"
        super().__init__(message, code="INSUFFICIENT_STOCK", status_code=422)
