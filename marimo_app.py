import marimo

__generated_with = "0.21.1"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import pandas as pd

    def load_study_log(name: str = "log.csv") -> pd.DataFrame:
        """Read the pre-processed event log from `public/`.

        Resolved relative to the notebook rather than the working directory,
        so the notebook can be launched from anywhere.
        """
        source = str(mo.notebook_location() / "public" / name)
        return pd.read_csv(source, parse_dates=["time:timestamp"])

    event_log = load_study_log()
    return event_log, mo


@app.cell(hide_code=True)
def _(event_log):
    from app.factory import create_process_analytics_service
    from core.constants import ACTIVITY_COL

    def apply_folds(log, fold_specs):
        """Rename every folded activity to its fold name, as the Dash app does."""
        if not fold_specs:
            return log
        mapping = {
            act: fold["name"] for fold in fold_specs for act in fold["activities"]
        }
        folded = log.copy()
        folded[ACTIVITY_COL] = folded[ACTIVITY_COL].replace(mapping)
        return folded

    # Built once from the unfolded log. This is the source of truth for which
    # activities exist, so the folding UI keeps offering original activity names
    # no matter what folds are currently defined. It is also reused directly
    # whenever the committed view has no folds, which avoids a ~0.6s rebuild.
    base_service = create_process_analytics_service(event_log)
    base_activities = base_service.get_all_activities()
    return (
        apply_folds,
        base_activities,
        base_service,
        create_process_analytics_service,
    )


@app.cell(hide_code=True)
def _(base_activities):
    def build_view(folds, activities, builder, allow_loops, show_empty):
        """The single constructor for a committed view snapshot.

        Used both by the Refresh button and by the staleness check, so the two
        can never drift apart.
        """
        return {
            "folds": folds,
            "activities": list(activities or []),
            "builder": builder,
            "allow_loops": allow_loops,
            "show_empty": show_empty,
        }

    def views_equal(a, b):
        """Compare two snapshots, ignoring activity selection order."""
        if a is None or b is None:
            return a is b

        def _normalised(view):
            return {**view, "activities": sorted(view["activities"])}

        return _normalised(a) == _normalised(b)

    # What the map renders before anything has been committed.
    default_view = build_view(
        folds=[],
        activities=base_activities,
        builder="set_based",
        allow_loops=True,
        show_empty=True,
    )
    return build_view, default_view, views_equal


@app.cell(hide_code=True)
def _(mo):
    # A fold is {"name": str, "activities": [str]}, matching the Dash
    # `folding-store` format.
    get_folds, set_folds = mo.state([])
    get_fold_error, set_fold_error = mo.state("")

    # The committed view: the only thing the (expensive) map cell depends on.
    # Controls write into it via the Refresh button, never directly, so
    # fiddling with a control does not trigger a rebuild.
    get_view, set_view = mo.state(None)
    return (
        get_fold_error,
        get_folds,
        get_view,
        set_fold_error,
        set_folds,
        set_view,
    )


@app.cell(hide_code=True)
def _(base_activities, get_folds):
    folds = get_folds()

    # An activity may belong to at most one fold, so anything already folded is
    # withheld from the "activities to fold" picker.
    already_folded = {act for fold in folds for act in fold["activities"]}
    foldable_activities = sorted(set(base_activities) - already_folded)

    # What the map's activity picker should offer. Computed directly rather
    # than via `service.get_all_activities()` so that adding a fold does not
    # cost a service rebuild -- that only happens on Refresh.
    map_activities = sorted(
        (set(base_activities) - already_folded) | {fold["name"] for fold in folds}
    )
    return folds, foldable_activities, map_activities


@app.cell(hide_code=True)
def _(foldable_activities, mo):
    # Defined in their own cell: a UI element's value is not readable from the
    # cell that creates it, but the add-button callback below can read it.
    fold_activities_input = mo.ui.multiselect(
        options=foldable_activities,
        label="Activities to fold",
    )
    fold_name_input = mo.ui.text(placeholder="e.g. Rejections", label="Fold name")
    return fold_activities_input, fold_name_input


@app.cell(hide_code=True)
def _(
    fold_activities_input,
    fold_name_input,
    get_folds,
    mo,
    set_fold_error,
    set_folds,
):
    def _add_fold(_):
        # Validation mirrors core/services/fold_manager.py::add_fold.
        name = (fold_name_input.value or "").strip()
        activities = list(fold_activities_input.value or [])
        existing = get_folds()

        if not activities or not name:
            set_fold_error("Select at least one activity and enter a fold name.")
            return
        if any(fold["name"] == name for fold in existing):
            set_fold_error(f"A fold named '{name}' already exists.")
            return
        for fold in existing:
            clash = [act for act in activities if act in fold["activities"]]
            if clash:
                set_fold_error(
                    f"{', '.join(clash)} already belongs to fold '{fold['name']}'."
                )
                return

        set_fold_error("")
        set_folds(existing + [{"name": name, "activities": activities}])

    add_fold_button = mo.ui.button(label="Add fold", on_click=_add_fold)
    return (add_fold_button,)


@app.cell(hide_code=True)
def _(folds, get_folds, mo, set_fold_error, set_folds):
    def _make_remove_button(name):
        def _remove(_):
            set_fold_error("")
            set_folds([f for f in get_folds() if f["name"] != name])

        return mo.ui.button(label="Remove", on_click=_remove)

    # Keyed by fold name (unique, enforced above) rather than by index, so a
    # removal cannot act on a stale position.
    remove_fold_buttons = mo.ui.array(
        [_make_remove_button(fold["name"]) for fold in folds]
    )
    return (remove_fold_buttons,)


@app.cell(hide_code=True)
def _(
    add_fold_button,
    fold_activities_input,
    fold_name_input,
    folds,
    get_fold_error,
    mo,
    remove_fold_buttons,
):
    if folds:
        _rows = [
            mo.hstack(
                [
                    mo.md(f"**{fold['name']}** &nbsp; {', '.join(fold['activities'])}"),
                    remove_fold_buttons[i],
                ],
                justify="space-between",
                align="center",
            )
            for i, fold in enumerate(folds)
        ]
        _existing = mo.vstack(_rows, gap=0.5)
    else:
        _existing = mo.md("*No folds defined yet.*")

    _error = get_fold_error()
    _banner = mo.callout(mo.md(_error), kind="danger") if _error else mo.md("")

    folding_panel = mo.accordion(
        {
            f"Activity folding ({len(folds)} defined)": mo.vstack(
                [
                    _existing,
                    mo.md("---"),
                    fold_activities_input,
                    fold_name_input,
                    add_fold_button,
                    _banner,
                ],
                gap=0.75,
            )
        }
    )
    return (folding_panel,)


@app.cell(hide_code=True)
def _(map_activities, mo):
    # Recreated whenever the fold set changes, which re-selects every activity
    # including any new fold name.
    activities = mo.ui.multiselect(
        options=map_activities,
        value=map_activities,
        label="Activities",
    )
    builder = mo.ui.dropdown(
        options={
            "Set-Based": "set_based",
            "Sequence-Based": "sequence_based",
            "Last-Activity-Based": "last_activity_based",
        },
        value="Set-Based",
        label="Generic map",
    )
    allow_loops = mo.ui.switch(value=True, label="Allow self-loops")
    show_empty = mo.ui.switch(value=True, label="Visualize empty traces")
    return activities, allow_loops, builder, show_empty


@app.cell(hide_code=True)
def _(
    activities,
    allow_loops,
    build_view,
    builder,
    folds,
    mo,
    set_view,
    show_empty,
):
    def _commit(_):
        set_view(
            build_view(
                folds=folds,
                activities=activities.value,
                builder=builder.value,
                allow_loops=allow_loops.value,
                show_empty=show_empty.value,
            )
        )

    # A plain button rather than `mo.ui.run_button`: `run_button.value` resets
    # on unrelated re-runs, which would blank the map whenever a control
    # changed. An on_click callback fires only on an actual click.
    refresh_button = mo.ui.button(
        label="Refresh visualization", kind="success", on_click=_commit
    )
    return (refresh_button,)


@app.cell(hide_code=True)
def _(
    activities,
    allow_loops,
    build_view,
    builder,
    default_view,
    folds,
    get_view,
    mo,
    show_empty,
    views_equal,
):
    # Pure comparison -- writes no state -- so re-running it on every control
    # change is free and cannot disturb the committed view.
    _pending = build_view(
        folds=folds,
        activities=activities.value,
        builder=builder.value,
        allow_loops=allow_loops.value,
        show_empty=show_empty.value,
    )
    _committed = get_view() or default_view

    # Compares values, not events: changing a control and changing it back
    # clears the badge again.
    if views_equal(_pending, _committed):
        refresh_status = mo.md(
            '<span style="color: #15803d;">&#10003; Showing current settings</span>'
        )
    else:
        refresh_status = mo.md(
            '<span style="color: #b45309;">&#9679; Settings changed'
            " &mdash; click Refresh</span>"
        )
    return (refresh_status,)


@app.cell(hide_code=True)
def _(
    activities,
    allow_loops,
    builder,
    folding_panel,
    mo,
    refresh_button,
    refresh_status,
    show_empty,
):
    mo.vstack(
        [
            mo.md("## Linear Continuous Process Mapper"),
            mo.hstack([builder, allow_loops, show_empty], justify="start", gap=2),
            activities,
            folding_panel,
            mo.hstack(
                [refresh_button, refresh_status],
                justify="start",
                align="center",
                gap=1,
            ),
        ],
        gap=0.75,
    )
    return


@app.cell(hide_code=True)
def _(
    apply_folds,
    base_service,
    create_process_analytics_service,
    default_view,
    event_log,
    get_view,
    mo,
):
    # Depends only on the committed view, so control changes never land here.
    _view = get_view() or default_view

    if _view["folds"]:
        _service = create_process_analytics_service(
            apply_folds(event_log, _view["folds"])
        )
    else:
        _service = base_service

    if not _view["activities"]:
        result = mo.md("*Select at least one activity, then click Refresh.*")
    else:
        figure, metadata = _service.generate_sankey_figure(
            selected_activities=_view["activities"],
            builder_key=_view["builder"],
            merge_threshold=None,
            allow_loops=_view["allow_loops"],
            visualize_empty_cases=_view["show_empty"],
        )
        figure.update_layout(height=700)
        result = mo.vstack(
            [
                # Render the figure directly. Do NOT wrap it in `mo.ui.plotly()`:
                # that wrapper adds Plotly selection-event handling, which Sankey
                # traces do not support, and it fails at render time with
                # "Cannot read properties of null (reading 'getAttribute')",
                # leaving a blank plot area. Hover and node dragging still work.
                figure,
                mo.md(
                    " · ".join(
                        f"**{k}**: {v}"
                        for k, v in (
                            _service.summarize_metadata(metadata) or {}
                        ).items()
                    )
                ),
            ]
        )

    result
    return


if __name__ == "__main__":
    app.run()
