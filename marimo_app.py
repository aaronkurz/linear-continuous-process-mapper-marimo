import marimo

__generated_with = "0.21.1"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import pandas as pd

    from tracker import init_marimo, omit_functions, operation_type

    _notebook_dir = mo.notebook_location()
    _pmprov_dir = _notebook_dir / ".pmprov"
    _artifact_dir = _pmprov_dir / "artifacts"
    _db_path = _pmprov_dir / "provenance.db"
    _artifact_dir.mkdir(parents=True, exist_ok=True)

    DATA_FILE = _notebook_dir / "public" / "log.csv"

    # init_marimo() and every import downstream cells depend on must live in
    # one cell -- pmprov's AST rewriter can't add its own dependency edges to
    # Marimo's reactive graph, so cell ordering has to come from the normal
    # dependency mechanism instead (every pipeline cell below takes `pd` or
    # `DATA_FILE` as a parameter, which transitively orders it after this one).
    rt = init_marimo(
        history_name="Linear Continuous Process Mapper",
        branch_name="main",
        db_path=str(_db_path),
        artifact_dir=str(_artifact_dir),
    )

    operation_type("data_loading", pd.read_csv)

    # UI construction and state-plumbing calls -- not analysis operations, so
    # tracing them automatically would just bury the real pipeline steps
    # (data_loading / apply_folds / service_construction / visualization) in
    # noise.
    omit_functions(
        "notebook_location",
        "state", "get_folds", "get_fold_error", "get_view", "build_view",
        "get_all_activities", "sorted",
        "multiselect", "dropdown", "switch", "text", "button", "array",
        "table", "md", "vstack", "hstack", "accordion", "callout",
        "update_layout", "summarize_metadata",
        # pmprov's own API calls below -- a bare top-level call to
        # rt.last_call_params(...) would otherwise be traced like any other
        # cell statement and pollute the provenance graph with steps for
        # pmprov's own bookkeeping.
        "last_call_params",
    )

    # Recover the last committed configuration from a resumed provenance
    # history (pmprov resumes by default -- see init_marimo() above), so a
    # kernel restart doesn't reset every fold/activity/toggle back to its
    # hardcoded default. None on a fresh history, or one that never got past
    # data loading. generate_sankey_figure is called below as a bound method
    # (service.generate_sankey_figure(...)), so pmprov records its func_name
    # with the receiver prefix -- "service.generate_sankey_figure", not
    # "generate_sankey_figure". Its real kwarg names (selected_activities/
    # builder_key/allow_loops/visualize_empty_cases) also come from how it's
    # actually called below, not from pmprov's own naming.
    _last_folds_params = rt.last_call_params("apply_folds")
    _last_sankey_params = rt.last_call_params("service.generate_sankey_figure")
    initial_folds = _last_folds_params["fold_specs"] if _last_folds_params else []
    initial_sankey_params = _last_sankey_params

    return (
        DATA_FILE,
        initial_folds,
        initial_sankey_params,
        mo,
        operation_type,
        pd,
        rt,
    )


@app.cell(hide_code=True)
def _(DATA_FILE, pd):
    # Tracked: registered above as "data_loading". Resolved relative to the
    # notebook rather than the working directory, so the notebook can be
    # launched from anywhere.
    event_log = pd.read_csv(str(DATA_FILE), parse_dates=["time:timestamp"])
    return (event_log,)


@app.cell(hide_code=True)
def _(event_log, operation_type):
    from app.factory import create_process_analytics_service
    from core.constants import ACTIVITY_COL
    from core.services.process_analytics_service import ProcessAnalyticsService

    operation_type("service_construction", create_process_analytics_service)
    operation_type("visualization", ProcessAnalyticsService.generate_sankey_figure)

    @operation_type("transformation")
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
    # activities exist, so the folding UI keeps offering original activity
    # names no matter what folds are currently defined.
    base_service = create_process_analytics_service(event_log)
    base_activities = base_service.get_all_activities()
    return apply_folds, base_activities, create_process_analytics_service


@app.cell(hide_code=True)
def _(base_activities, initial_folds, initial_sankey_params):
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

    # What the map renders before anything has been committed. On a resumed
    # history this is the prior session's last committed view (see
    # initial_sankey_params in the init cell), so the map shows the same
    # settings immediately -- no Refresh click needed. On a fresh history
    # (or one that never got past data loading), falls back to today's
    # hardcoded defaults.
    if initial_sankey_params is not None:
        default_view = build_view(
            folds=initial_folds,
            activities=initial_sankey_params["selected_activities"],
            builder=initial_sankey_params["builder_key"],
            allow_loops=initial_sankey_params["allow_loops"],
            show_empty=initial_sankey_params["visualize_empty_cases"],
        )
    else:
        default_view = build_view(
            folds=[],
            activities=base_activities,
            builder="set_based",
            allow_loops=True,
            show_empty=True,
        )
    return build_view, default_view, views_equal


@app.cell(hide_code=True)
def _(initial_folds, mo):
    # A fold is {"name": str, "activities": [str]}, matching the Dash
    # `folding-store` format. Seeded from the resumed history's last commit
    # (see initial_folds in the init cell) rather than always starting empty.
    get_folds, set_folds = mo.state(initial_folds)
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
def _(initial_sankey_params, map_activities, mo):
    # Recreated whenever the fold set changes, which re-selects every activity
    # including any new fold name. Defaults come from the resumed history's
    # last commit (initial_sankey_params) when present, so the control panel
    # matches what the map already shows via default_view -- otherwise falls
    # back to today's hardcoded defaults.
    _builder_key_to_label = {
        "set_based": "Set-Based",
        "sequence_based": "Sequence-Based",
        "last_activity_based": "Last-Activity-Based",
    }
    if initial_sankey_params is not None:
        _default_activities = [
            a for a in initial_sankey_params["selected_activities"]
            if a in map_activities
        ] or map_activities
        _default_builder = _builder_key_to_label.get(
            initial_sankey_params["builder_key"], "Set-Based"
        )
        _default_allow_loops = initial_sankey_params["allow_loops"]
        _default_show_empty = initial_sankey_params["visualize_empty_cases"]
    else:
        _default_activities = map_activities
        _default_builder = "Set-Based"
        _default_allow_loops = True
        _default_show_empty = True

    activities = mo.ui.multiselect(
        options=map_activities,
        value=_default_activities,
        label="Activities",
    )
    builder = mo.ui.dropdown(
        options={
            "Set-Based": "set_based",
            "Sequence-Based": "sequence_based",
            "Last-Activity-Based": "last_activity_based",
        },
        value=_default_builder,
        label="Generic map",
    )
    allow_loops = mo.ui.switch(value=_default_allow_loops, label="Allow self-loops")
    show_empty = mo.ui.switch(value=_default_show_empty, label="Visualize empty traces")
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
    create_process_analytics_service,
    default_view,
    event_log,
    get_view,
    mo,
):
    # Depends only on the committed view, so control changes never land here
    # -- and it re-runs exactly once per Refresh click.
    #
    # apply_folds() and generate_sankey_figure() below are both unconditional,
    # top-level statements (not nested in `if`/`else`): pmprov's AST rewriter
    # only wraps top-level Assign/Expr-with-Call statements in a cell, never
    # ones nested inside control flow, so hiding either call behind an `if`
    # would silently stop it from being tracked. apply_folds() already no-ops
    # when there are no folds, and generate_sankey_figure() already no-ops
    # (returns metadata=None) when there are no activities, so neither branch
    # actually needs its own guard here -- the guard moves to *after* the
    # call, on the result, instead. This does give up the old "reuse
    # base_service when there are no folds" optimization, since the service
    # now has to be rebuilt every Refresh for both steps to be traceable.
    #
    # Concretely, this removed two guards that used to wrap the tracked
    # calls directly:
    #   if _view["folds"]:
    #       folded_log = apply_folds(...)
    #       service = create_process_analytics_service(folded_log.data)
    #   else:
    #       service = base_service
    #   ...
    #   if not _view["activities"]:
    #       result = mo.md("*Select at least one activity...*")
    #   else:
    #       figure, metadata = service.generate_sankey_figure(...)
    # Both calls now run unconditionally instead, and the branching happens
    # below on `metadata` (the call's result) rather than on the view.
    _view = get_view() or default_view

    folded_log = apply_folds(event_log, _view["folds"])
    service = create_process_analytics_service(folded_log)

    figure, metadata = service.generate_sankey_figure(
        selected_activities=_view["activities"],
        builder_key=_view["builder"],
        merge_threshold=None,
        allow_loops=_view["allow_loops"],
        visualize_empty_cases=_view["show_empty"],
    )

    if metadata is None:
        result = mo.md("*Select at least one activity, then click Refresh.*")
    else:
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
                            service.summarize_metadata(metadata) or {}
                        ).items()
                    )
                ),
            ]
        )

    result
    return


if __name__ == "__main__":
    app.run()
