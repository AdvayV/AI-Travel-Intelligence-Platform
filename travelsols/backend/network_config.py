"""Use OS-trusted certificates without disabling TLS verification."""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
