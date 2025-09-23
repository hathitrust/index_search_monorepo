"""TKSeal - A command-line utility for managing sealed secrets in Kubernetes environments."""

__version__ = "1.0.0"

from .exceptions import TKSealError

__all__ = ["TKSealError", "__version__"]
