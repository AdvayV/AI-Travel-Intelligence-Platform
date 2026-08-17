"""Configure Python HTTPS clients to use the operating system trust store."""

import logging

logger = logging.getLogger(__name__)


def enable_system_trust_store() -> bool:
    """Enable native CA certificates when truststore is installed."""
    try:
        import truststore

        truststore.inject_into_ssl()
        return True
    except ImportError:
        logger.warning("truststore is not installed; Python will use its default CA bundle.")
    except Exception as exc:
        logger.warning("Could not configure the system trust store: %s", exc)
    return False
