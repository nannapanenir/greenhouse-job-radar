from .ashby import AshbyAdapter
from .base import Company, CompanyResult, FetchError, FixtureTransport, HttpError, HttpTransport, JobAdapter, RecordingTransport, collect_all
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter

ADAPTERS = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
}

__all__ = [
    "ADAPTERS",
    "AshbyAdapter",
    "Company",
    "CompanyResult",
    "FetchError",
    "FixtureTransport",
    "GreenhouseAdapter",
    "HttpError",
    "HttpTransport",
    "JobAdapter",
    "LeverAdapter",
    "RecordingTransport",
    "collect_all",
]
