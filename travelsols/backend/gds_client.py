import logging
from mock_gds_data import get_mock_snapshots

logger = logging.getLogger(__name__)

def get_top_destinations(origin: str) -> dict:
    logger.info(f"Retrieving hardcoded/mock top destinations for origin: {origin}")
    return get_mock_snapshots(origin)

