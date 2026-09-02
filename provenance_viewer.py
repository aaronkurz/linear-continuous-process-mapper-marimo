import marimo

__generated_with = "0.21.1"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    from tracker.storage import DuckDBSQLiteBackend

    # Same db_path/artifact_dir that marimo_app.py's init_marimo() writes to,
    # so this notebook reads whatever provenance that notebook has captured
    # so far. Read-only: this notebook never calls init_marimo() itself, so
    # it never starts its own session or writes anything.
    _pmprov_dir = mo.notebook_location() / ".pmprov"
    storage = DuckDBSQLiteBackend(
        db_path=str(_pmprov_dir / "provenance.db"),
        artifact_dir=str(_pmprov_dir / "artifacts"),
    )
    return mo, storage


@app.cell(hide_code=True)
def _(mo, storage):
    _con = storage._connect(read_only=True)
    _row = _con.execute(
        "SELECT history_id, name FROM analysis_histories"
        " ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    _con.close()

    history_id = _row[0] if _row else None
    history_name = _row[1] if _row else None

    mo.md(
        f"## Captured provenance\n"
        + (
            f"History **{history_name}**"
            if history_id
            else "*No provenance captured yet — run `marimo_app.py` first.*"
        )
    )
    return (history_id,)


@app.cell(hide_code=True)
def _(history_id, storage):
    states = storage.load_states_rich(history_id) if history_id else []
    branches = storage.load_branches(history_id) if history_id else []

    # Only states produced by an actual step carry an operation -- the root
    # state (the session's starting point, before any tracked call) doesn't.
    details = [
        storage.load_state_detail(s["state_id"])
        for s in states
        if s["produced_by_step_id"]
    ]
    return branches, details, states


@app.cell(hide_code=True)
def _(mo, states):
    mo.md(f"**{len(states)}** state(s) recorded.")
    return


@app.cell(hide_code=True)
def _():
    from tracker import format_params

    return (format_params,)


@app.cell(hide_code=True)
def _(details, format_params, mo):
    if not details:
        steps_table = None
        _display = mo.md("")
    else:
        steps_table = mo.ui.table(
            [
                {
                    "state_id": d["state_id"],
                    "command": d["func_name"],
                    "operation_type": d["operation"]["type"],
                    "branch": d["branch_name"],
                    "parameters": format_params(d["params"]) or "—",
                    "created_at": d["timestamp"][:19].replace("T", " "),
                }
                for d in details
            ],
            selection="single",
            label="Operations executed, with their parameters",
        )
        _display = mo.vstack([mo.md("## Analysis steps"), steps_table])
    _display
    return (steps_table,)


@app.cell(hide_code=True)
def _(mo, states, steps_table):
    _selected = (
        steps_table.value[0] if steps_table is not None and steps_table.value else None
    )

    if _selected is None:
        state_preview = mo.md("*Select a step above to preview its output data.*")
    else:
        _state = next(
            (s for s in states if s["state_id"] == _selected["state_id"]), None
        )
        _artifact_ids = _state["artifact_state_ids"] if _state else []
        if not _artifact_ids:
            state_preview = mo.md("*No output artifact stored for this step.*")
        else:
            state_preview = mo.md(
                f"*Artifact state id: `{_artifact_ids[0]}` "
                f"(load via `storage.load_artifact(...)` to preview its data)*"
            )
    state_preview
    return


@app.cell(hide_code=True)
def _(history_id, mo, storage):
    import tracker

    # `build_plotly_graph` is pmprov's own interactive-tree renderer (same
    # tree layout, branch coloring, and hover behavior as this notebook
    # originally built ad hoc) -- kept in the library so any consumer with
    # storage access gets it, not just this notebook.
    _fig = tracker.build_plotly_graph(storage, history_id) if history_id else None

    if _fig is None:
        graph_view = mo.md("")
    else:
        graph_view = mo.vstack(
            [
                mo.md("## Provenance tree"),
                mo.ui.plotly(
                    _fig,
                    config={"scrollZoom": True, "displaylogo": False},
                ),
            ]
        )
    graph_view
    return


@app.cell(hide_code=True)
def _(branches, mo):
    mo.vstack(
        [
            mo.md("## Branches"),
            (
                mo.ui.table(
                    [
                        {
                            "branch": b["name"],
                            "step_count": b["step_count"],
                            "starts_at_state_id": b["starts_at_state_id"],
                            "divergence_point_id": b["divergence_point_id"],
                        }
                        for b in branches
                    ]
                )
                if branches
                else mo.md("*No branches yet.*")
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
