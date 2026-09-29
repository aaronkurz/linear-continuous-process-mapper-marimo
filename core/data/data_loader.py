from pathlib import Path

import pm4py
import pandas as pd
from core.constants import ACTIVITY_COL, CASE_ID_COL, TIMESTAMP_COL
from core.logger_config import setup_logger

logger = setup_logger(__name__)

# File types the notebook's log picker offers and `load_event_log` accepts.
LOG_SUFFIXES = (".csv", ".xes")


def load_xes_log(file_path: str) -> pd.DataFrame:
    try:
        event_log = pm4py.read_xes(file_path, variant="rustxes")
        return event_log
    except Exception as e:
        logger.error(f"Error loading event log from: {file_path}: {e}")
        return None


def load_csv_log(file_path: str) -> pd.DataFrame:
    event_log = pd.read_csv(file_path)
    # Parsed here rather than via `parse_dates`, which would raise its own
    # error before `load_event_log` can report the missing column.
    if TIMESTAMP_COL in event_log.columns:
        event_log[TIMESTAMP_COL] = pd.to_datetime(event_log[TIMESTAMP_COL])
    return event_log


def load_event_log(file_path) -> pd.DataFrame:
    """Load a .csv or .xes event log and check it has the columns we need."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        event_log = load_csv_log(str(path))
    elif suffix == ".xes":
        event_log = load_xes_log(str(path))
        if event_log is None:
            raise ValueError(f"Could not read XES log '{path.name}'.")
    else:
        raise ValueError(
            f"Unsupported log type '{suffix}'; expected one of {', '.join(LOG_SUFFIXES)}."
        )

    missing = [
        col
        for col in (CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL)
        if col not in event_log.columns
    ]
    if missing:
        raise ValueError(f"'{path.name}' is missing column(s): {', '.join(missing)}.")
    return event_log
