import pandas as pd
import pytest

import lcm

CASE, ACTIVITY, TIME = "case:concept:name", "concept:name", "time:timestamp"


def make_log(traces):
    """Build an event log from {case id: "ABC"}, one event per letter."""
    return pd.DataFrame(
        {
            CASE: case,
            ACTIVITY: activity,
            TIME: pd.Timestamp("2024-01-01") + pd.Timedelta(minutes=minute),
        }
        for case, trace in traces.items()
        for minute, activity in enumerate(trace)
    )


def generate(traces, **kwargs):
    return lcm.get_service(make_log(traces)).generate(**kwargs)


def nodes(figure):
    return list(figure.data[0].node.label)


def links(figure):
    """Return the links as a set of (source label, target label, cases)."""
    sankey = figure.data[0]
    labels = sankey.node.label
    return {
        (labels[source], labels[target], value)
        for source, target, value in zip(
            sankey.link.source, sankey.link.target, sankey.link.value
        )
    }


def node_colors(figure):
    return dict(zip(figure.data[0].node.label, figure.data[0].node.color))


def legend(figure):
    return [trace.name for trace in figure.data[1:]]


BRANCHING = {"c1": "AB", "c2": "AB", "c3": "AC"}


@pytest.mark.parametrize(
    "map_type, expected",
    [
        (
            "set_based",
            {
                ("START", "{A}", 3),
                ("{A}", "{A, B}", 2),
                ("{A}", "{A, C}", 1),
            },
        ),
        (
            "sequence_based",
            {
                ("START", "A", 3),
                ("A", "A → B", 2),
                ("A", "A → C", 1),
            },
        ),
        (
            "last_activity_based",
            {
                ("START", "A", 3),
                ("A", "B", 2),
                ("A", "C", 1),
            },
        ),
    ],
)
def test_map_type_decides_the_abstraction(map_type, expected):
    figure, _ = generate(BRANCHING, map_type=map_type)
    assert links(figure) == expected


def test_prefixes_in_a_different_order_share_a_set_based_node_only():
    traces = {"c1": "AB", "c2": "BA"}
    set_figure, _ = generate(traces, map_type="set_based")
    sequence_figure, _ = generate(traces, map_type="sequence_based")
    assert sorted(nodes(set_figure)) == ["START", "{A, B}", "{A}", "{B}"]
    assert sorted(nodes(sequence_figure)) == [
        "A",
        "A → B",
        "B",
        "B → A",
        "START",
    ]


def test_map_type_accepts_the_enum():
    figure, _ = generate(BRANCHING, map_type=lcm.MapType.SEQUENCE_BASED)
    assert "A → B" in nodes(figure)


def test_unknown_map_type_is_rejected():
    with pytest.raises(ValueError, match="tree"):
        generate(BRANCHING, map_type="tree")


def test_defaults_draw_a_set_based_map_of_all_activities():
    figure, _ = generate(BRANCHING)
    assert sorted(nodes(figure)) == ["START", "{A, B}", "{A, C}", "{A}"]


def test_metadata_describes_the_map():
    _, metadata = generate(BRANCHING)
    assert metadata == {
        "nodes_leakage_gt_0": 2,
        "terminal_nodes": 2,
        "total_nodes": 4,
        "empty_cases": 0,
    }


def test_activities_filter_events_out_of_traces():
    figure, _ = generate({"c1": "ABC"}, activities=["A", "C"], map_type="sequence_based")
    assert links(figure) == {("START", "A", 1), ("A", "A → C", 1)}


def test_cases_without_selected_activities_become_an_empty_trace():
    figure, metadata = generate(
        {"c1": "AB", "c2": "CC"}, activities=["A", "B"], map_type="sequence_based"
    )
    assert ("START", "EMPTY TRACE", 1) in links(figure)
    assert metadata["empty_cases"] == 1


def test_empty_traces_can_be_left_out_but_are_still_counted():
    figure, metadata = generate(
        {"c1": "AB", "c2": "CC"},
        activities=["A", "B"],
        visualize_empty_cases=False,
        map_type="sequence_based",
    )
    assert "EMPTY TRACE" not in nodes(figure)
    assert metadata["empty_cases"] == 1


@pytest.mark.parametrize(
    "map_type, label",
    [
        ("set_based", "{EMPTY TRACE}"),
        ("sequence_based", "EMPTY TRACE"),
        ("last_activity_based", "EMPTY TRACE"),
    ],
)
def test_empty_trace_node_is_white(map_type, label):
    figure, _ = generate(
        {"c1": "AB", "c2": "CC"}, activities=["A", "B"], map_type=map_type
    )
    assert node_colors(figure)[label] == "white"


def test_folded_activities_share_their_fold_name():
    figure, _ = generate(
        {"c1": "ABC"}, folds={"F": ["A", "B"]}, map_type="sequence_based"
    )
    assert links(figure) == {
        ("START", "F", 1),
        ("F", "F → F", 1),
        ("F → F", "F → F → C", 1),
    }


def test_consecutive_folded_activities_form_a_self_loop_unless_disallowed():
    with_loops, _ = generate({"c1": "AB"}, folds={"F": ["A", "B"]})
    without_loops, _ = generate(
        {"c1": "AB"}, folds={"F": ["A", "B"]}, allow_loops=False
    )
    assert ("{F}", "{F}", 1) in links(with_loops)
    assert links(without_loops) == {("START", "{F}", 1)}


def test_legend_lists_fold_names_instead_of_their_members():
    figure, _ = generate({"c1": "ABC"}, folds={"F": ["A", "B"]})
    assert legend(figure) == ["C", "F", "EMPTY TRACE"]


def test_activities_are_named_as_they_appear_after_folding():
    figure, metadata = generate(
        {"c1": "AB", "c2": "CC"},
        activities=["F"],
        folds={"F": ["A", "B"]},
        visualize_empty_cases=False,
    )
    assert sorted(nodes(figure)) == ["START", "{F}"]
    assert metadata["empty_cases"] == 1


def test_a_fold_may_reuse_the_name_of_one_of_its_members():
    figure, _ = generate(
        {"c1": "AB"}, folds={"A": ["A", "B"]}, map_type="last_activity_based"
    )
    assert links(figure) == {("START", "A", 1), ("A", "A", 1)}


def test_activities_can_be_listed_as_they_appear_after_folding():
    service = lcm.get_service(make_log({"c1": "ABC"}))
    assert service.get_all_activities(folds={"F": ["A", "B"]}) == ["C", "F"]


def test_listing_activities_rejects_invalid_folds():
    service = lcm.get_service(make_log({"c1": "ABC"}))
    with pytest.raises(ValueError, match="Z"):
        service.get_all_activities(folds={"F": ["Z"]})


def test_folds_apply_only_to_the_call_they_are_passed_to():
    service = lcm.get_service(make_log({"c1": "AB"}))
    service.generate(folds={"F": ["A", "B"]})
    figure, _ = service.generate(map_type="sequence_based")
    assert links(figure) == {("START", "A", 1), ("A", "A → B", 1)}


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"activities": []}, "at least one"),
        ({"activities": ["A", "Z"]}, "Z"),
        ({"activities": ["A"], "folds": {"F": ["A", "B"]}}, "A"),
        ({"folds": {"F": ["A", "Z"]}}, "Z"),
        ({"folds": {"F": []}}, "F"),
        ({"folds": {" ": ["A"]}}, "name"),
        ({"folds": {"F": ["A"], "G": ["A", "B"]}}, "A"),
        ({"folds": {"B": ["A"]}}, "B"),
    ],
    ids=[
        "no activities",
        "unknown activity",
        "activity hidden by a fold",
        "unknown fold member",
        "empty fold",
        "blank fold name",
        "activity in two folds",
        "fold named after another activity",
    ],
)
def test_invalid_choices_are_rejected_naming_the_problem(kwargs, message):
    with pytest.raises(ValueError, match=message):
        generate({"c1": "ABC"}, **kwargs)


@pytest.mark.parametrize("column", [CASE, ACTIVITY, TIME])
def test_get_service_rejects_a_log_missing_a_column(column):
    with pytest.raises(ValueError, match=column):
        lcm.get_service(make_log({"c1": "AB"}).drop(columns=column))


def test_get_service_leaves_the_log_untouched():
    log = make_log({"c1": "BA"})
    original = log.copy()
    lcm.get_service(log).generate(folds={"F": ["A"]})
    pd.testing.assert_frame_equal(log, original)


def test_events_are_ordered_by_timestamp_not_row_position():
    log = make_log({"c1": "AB"}).iloc[::-1].reset_index(drop=True)
    figure, _ = lcm.get_service(log).generate(map_type="sequence_based")
    assert links(figure) == {("START", "A", 1), ("A", "A → B", 1)}


def test_events_with_equal_timestamps_keep_their_log_order():
    log = make_log({"c1": "BA"})
    log[TIME] = pd.Timestamp("2024-01-01")
    figure, _ = lcm.get_service(log).generate(map_type="sequence_based")
    assert links(figure) == {("START", "B", 1), ("B", "B → A", 1)}


def test_events_without_an_activity_are_ignored():
    log = make_log({"c1": "AB"})
    log.loc[0, ACTIVITY] = None
    service = lcm.get_service(log)
    figure, _ = service.generate(map_type="sequence_based")
    assert service.get_all_activities() == ["B"]
    assert links(figure) == {("START", "B", 1)}


REPEATED = {"c1": "AAAB", "c2": "AAAB"}


@pytest.mark.parametrize(
    "map_type, loop",
    [
        ("set_based", ("{A}", "{A}", 4)),
        ("last_activity_based", ("A", "A", 4)),
    ],
)
def test_self_loops_are_drawn_by_default(map_type, loop):
    figure, _ = generate(REPEATED, map_type=map_type)
    assert loop in links(figure)


@pytest.mark.parametrize(
    "map_type, repeated_node",
    [("set_based", "{A}"), ("last_activity_based", "A")],
)
def test_disallowing_loops_does_not_turn_repeated_activities_into_terminals(
    map_type, repeated_node
):
    figure, metadata = generate(REPEATED, map_type=map_type, allow_loops=False)
    assert node_colors(figure)[repeated_node] != "black"
    assert metadata["terminal_nodes"] == 1


def test_disallowing_loops_changes_nothing_on_sequence_based_maps():
    with_loops, _ = generate(REPEATED, map_type="sequence_based")
    without_loops, _ = generate(REPEATED, map_type="sequence_based", allow_loops=False)
    assert links(with_loops) == links(without_loops)
