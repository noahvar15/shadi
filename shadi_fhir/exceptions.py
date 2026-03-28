"""FHIR ingestion errors."""


class FHIRValidationError(ValueError):
    """Raised when a FHIR bundle or resource fails structural / content validation."""


class FHIRAuthError(RuntimeError):
    """Raised when SMART / OAuth token exchange fails."""
