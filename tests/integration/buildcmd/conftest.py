import logging

LOG = logging.getLogger(__name__)

def pytest_sessionstart(session):
    LOG.info(session)