import pandas as pd
from typing import Dict, List, Tuple
from lcm.constants import CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL, EMPTY_TRACE


def check_columns(event_log: pd.DataFrame, source: str = "The event log") -> None:
    """Raise a ValueError if `event_log` lacks a column the maps need."""
    missing = [
        col
        for col in (CASE_ID_COL, ACTIVITY_COL, TIMESTAMP_COL)
        if col not in event_log.columns
    ]
    if missing:
        raise ValueError(f"{source} is missing column(s): {', '.join(missing)}.")


class DataProcessor:
    """Handles all data transformation and preparation logic."""

    def prepare_traces(self, event_log: pd.DataFrame) -> List[List[str]]:
        """Return the activities of each case in timestamp order."""
        check_columns(event_log)
        events = event_log.dropna(subset=[ACTIVITY_COL]).sort_values(
            TIMESTAMP_COL, kind="stable"
        )
        return events.groupby(CASE_ID_COL)[ACTIVITY_COL].agg(list).tolist()

    def apply_folds(
        self, traces: List[List[str]], folds: Dict[str, List[str]]
    ) -> List[List[str]]:
        """Rename every folded activity to its fold name."""
        if not folds:
            return traces
        mapping = {act: name for name, members in folds.items() for act in members}
        return [[mapping.get(act, act) for act in trace] for trace in traces]

    def create_variants(
        self,
        traces: List[List[str]],
        selected_activities: List[str],
        visualize_empty_cases: bool,
    ) -> Tuple[List[List[str]], int]:
        """Reduce traces to the selected activities; also count the emptied ones."""
        selected = set(selected_activities)
        filtered = [[act for act in trace if act in selected] for trace in traces]
        variants = [trace for trace in filtered if trace]
        empty_cases = len(filtered) - len(variants)

        if visualize_empty_cases:
            variants += [[EMPTY_TRACE] for _ in range(empty_cases)]

        return variants, empty_cases
