import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Analyzing a log with the `lcm` library

    This notebook uses `lcm` from code, without any widgets: each map is
    fixed by the arguments in its cell. For exploring a log interactively,
    see `marimo_app.py`.

    The log holds the travel expense declarations of a university, from
    submission to payment.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    import lcm

    return lcm, mo, pd


@app.cell
def _(lcm, mo):
    event_log = lcm.load_event_log(mo.notebook_location() / "logs" / "log.csv")
    lcm_service = lcm.get_service(event_log)
    event_log.head()
    return event_log, lcm_service


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The activities

    An event log is a plain DataFrame, so pandas works as usual. Here is how
    many cases contain each activity.
    """)
    return


@app.cell
def _(event_log):
    (
        event_log.groupby("concept:name")["case:concept:name"]
        .nunique()
        .sort_values(ascending=False)
        .rename("cases")
        .reset_index()
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Comparing the map types

    Each map type decides when two cases have reached the same state, which
    sets how large the map gets. `generate` returns the figure and a dict of
    counts, so the map types can be compared without drawing them.
    """)
    return


@app.cell
def _(lcm, lcm_service, pd):
    pd.DataFrame(
        {
            map_type.value: lcm_service.generate(map_type=map_type)[1]
            for map_type in lcm.MapType
        }
    ).T.rename_axis("map type")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Folding the rejections

    The four kinds of rejection differ only in who rejected. Folding them
    into one activity gives a much smaller map, and it's still set-based.
    """)
    return


@app.cell
def _(lcm_service):
    rejections = [
        activity
        for activity in lcm_service.get_all_activities()
        if "REJECTED" in activity
    ]
    folds = {"Declaration REJECTED": rejections}

    folded_map, folded_metadata = lcm_service.generate(folds=folds)
    folded_map
    return folded_metadata, folds


@app.cell
def _(folded_metadata):
    folded_metadata
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Focusing on a few activities

    `activities` keeps only the named ones, and a fold goes by its fold name.
    Cases with none of them become the `EMPTY TRACE` node. Here, those are
    the declarations that were saved but never submitted.
    """)
    return


@app.cell
def _(folds, lcm_service):
    focus_map, focus_metadata = lcm_service.generate(
        activities=[
            "Declaration SUBMITTED by EMPLOYEE",
            "Declaration REJECTED",
            "Payment Handled",
        ],
        folds=folds,
    )
    focus_map
    return (focus_metadata,)


@app.cell
def _(focus_metadata):
    focus_metadata
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Which activities make the map complex?

    Each `generate` call starts from the full log, so maps can be computed in
    a loop. Leaving out each activity in turn shows how much it adds to the
    map. Frequency doesn't explain it: `Declaration FOR_APPROVAL by
    ADMINISTRATION` occurs in a single case, yet the map still shrinks
    without it.
    """)
    return


@app.cell
def _(lcm_service, pd):
    all_activities = lcm_service.get_all_activities()
    _full_size = lcm_service.generate()[1]["total_nodes"]


    def nodes_without(left_out):
        """Count the nodes of the set-based map without one activity."""
        kept = [activity for activity in all_activities if activity != left_out]
        return lcm_service.generate(activities=kept)[1]["total_nodes"]


    (
        pd.DataFrame(
            {
                "left out": all_activities,
                "nodes removed": [
                    _full_size - nodes_without(activity) for activity in all_activities
                ],
            }
        )
        .sort_values("nodes removed", ascending=False)
        .reset_index(drop=True)
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Transforming the log first

    A set-based map can't show resubmissions: submitting again adds nothing to
    the set, so the case stays in the same node. To make them visible, unfold
    the activity in the log before creating a service. Any change to the
    DataFrame works this way. Here, every submission after a case's first gets
    a new activity name.
    """)
    return


@app.cell
def _(event_log, folds, lcm):
    events = event_log.sort_values("time:timestamp", kind="stable")
    is_submission = events["concept:name"] == "Declaration SUBMITTED by EMPLOYEE"
    submission_number = is_submission.groupby(events["case:concept:name"]).cumsum()
    is_resubmission = is_submission & (submission_number > 1)

    unfolded_log = events.assign(
        **{
            "concept:name": events["concept:name"].mask(
                is_resubmission, "Declaration RESUBMITTED by EMPLOYEE"
            )
        }
    )

    unfolded_map, unfolded_metadata = lcm.get_service(unfolded_log).generate(
        folds=folds
    )
    unfolded_map
    return (unfolded_metadata,)


@app.cell
def _(unfolded_metadata):
    unfolded_metadata
    return


if __name__ == "__main__":
    app.run()
