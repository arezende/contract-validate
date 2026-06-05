"""ContractFOL corpus subsystem — schema, ingest, and sampling utilities."""

from contractfol.corpus.schema import DiscrepancyInstance, Dimension, PerturbType
from contractfol.corpus.ingest import load_instances
from contractfol.corpus.sample import (
    stratified_sample,
    make_splits,
    save_splits,
    load_splits,
    load_test_split_with_warning,
)

__all__ = [
    "DiscrepancyInstance",
    "Dimension",
    "PerturbType",
    "load_instances",
    "stratified_sample",
    "make_splits",
    "save_splits",
    "load_splits",
    "load_test_split_with_warning",
]
