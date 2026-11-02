from enum import StrEnum

CASE_ID_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"
# Stands in for the activities of a case that has none of the selected ones.
EMPTY_TRACE = "EMPTY TRACE"


class MapType(StrEnum):
    SET_BASED = "set_based"
    SEQUENCE_BASED = "sequence_based"
    LAST_ACTIVITY_BASED = "last_activity_based"
