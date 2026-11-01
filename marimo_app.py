import marimo

__generated_with = "0.21.1"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import black
    import marimo as mo

    import lcm

    # Resolved relative to the notebook rather than the working directory, so
    # the notebook can be launched from anywhere.
    log_dir = mo.notebook_location() / "logs"
    log_names = []
    if log_dir.is_dir():
        log_names = sorted(
            p.name
            for p in log_dir.iterdir()
            if p.is_file() and p.suffix.lower() in lcm.LOG_SUFFIXES
        )

    mo.stop(
        not log_names,
        mo.callout(
            mo.md(f"No event logs found. Add a `.csv` or `.xes` file to `{log_dir}`."),
            kind="warn",
        ),
    )

    # Defined in its own cell: a UI element's value is not readable from the
    # cell that creates it.
    log_picker = mo.ui.dropdown(
        options=log_names,
        value="log.csv" if "log.csv" in log_names else log_names[0],
        label="Event log",
    )
    return black, lcm, log_dir, log_picker, mo


@app.cell(hide_code=True)
def _(lcm, log_dir, log_picker, mo):
    # Show a readable message for a bad file instead of a traceback.
    try:
        lcm_service = lcm.get_service(lcm.load_event_log(log_dir / log_picker.value))
    except Exception as _e:
        mo.stop(
            True,
            mo.callout(
                mo.md(f"Could not load `{log_picker.value}`: {_e}"), kind="danger"
            ),
        )
    return (lcm_service,)


@app.cell(hide_code=True)
def _(lcm_service, mo):
    # Referencing the service makes this cell re-run when another log is picked,
    # which resets folds and the committed settings; they name activities that
    # may not exist in the new log.
    lcm_service

    # Fold name mapped to its activities, as `generate` takes them.
    get_folds, set_folds = mo.state({})
    get_fold_error, set_fold_error = mo.state("")

    # The arguments of the map on screen. Only the Refresh button writes them,
    # so changing a control does not redraw the map.
    get_settings, set_settings = mo.state(
        {"map_type": "set_based", "allow_loops": True, "visualize_empty_cases": True}
    )
    return (
        get_fold_error,
        get_folds,
        get_settings,
        set_fold_error,
        set_folds,
        set_settings,
    )


@app.cell(hide_code=True)
def _(get_folds, lcm_service):
    folds = get_folds()

    # An activity may belong to at most one fold, so anything already folded is
    # withheld from the "activities to fold" picker.
    already_folded = {act for members in folds.values() for act in members}
    foldable_activities = sorted(set(lcm_service.get_all_activities()) - already_folded)
    map_activities = lcm_service.get_all_activities(folds)
    return foldable_activities, folds, map_activities


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
    lcm_service,
    mo,
    set_fold_error,
    set_folds,
):
    def _add_fold(_):
        name = (fold_name_input.value or "").strip()
        existing = get_folds()
        if name in existing:
            set_fold_error(f"A fold named '{name}' already exists.")
            return

        extended = {**existing, name: list(fold_activities_input.value or [])}
        try:
            lcm_service.get_all_activities(extended)
        except ValueError as e:
            set_fold_error(str(e))
            return

        set_fold_error("")
        set_folds(extended)

    add_fold_button = mo.ui.button(label="Add fold", on_click=_add_fold)
    return (add_fold_button,)


@app.cell(hide_code=True)
def _(folds, get_folds, mo, set_fold_error, set_folds):
    def _make_remove_button(name):
        def _remove(_):
            set_fold_error("")
            set_folds({k: v for k, v in get_folds().items() if k != name})

        return mo.ui.button(label="Remove", on_click=_remove)

    # Keyed by fold name (unique, enforced above) rather than by index, so a
    # removal cannot act on a stale position.
    remove_fold_buttons = mo.ui.array([_make_remove_button(name) for name in folds])
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
                    mo.md(f"**{name}** &nbsp; {', '.join(members)}"),
                    remove_fold_buttons[i],
                ],
                justify="space-between",
                align="center",
            )
            for i, (name, members) in enumerate(folds.items())
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
def _(mo):
    # Apart from the activity picker, so these keep their values when folds change.
    map_type = mo.ui.dropdown(
        options={
            "Set-Based": "set_based",
            "Sequence-Based": "sequence_based",
            "Last-Activity-Based": "last_activity_based",
        },
        value="Set-Based",
        label="Map type",
    )
    allow_loops = mo.ui.switch(value=True, label="Allow self-loops")
    visualize_empty_cases = mo.ui.switch(value=True, label="Visualize empty traces")
    return allow_loops, map_type, visualize_empty_cases


@app.cell(hide_code=True)
def _(map_activities, mo):
    # Recreated whenever the fold set changes, which re-selects every activity
    # including any new fold name.
    activities = mo.ui.multiselect(
        options=map_activities,
        value=map_activities,
        label="Activities",
    )
    return (activities,)


@app.cell(hide_code=True)
def _(
    activities,
    allow_loops,
    folds,
    map_activities,
    map_type,
    visualize_empty_cases,
):
    # The arguments for `generate` that the controls currently describe.
    settings = {
        "map_type": map_type.value,
        "allow_loops": allow_loops.value,
        "visualize_empty_cases": visualize_empty_cases.value,
    }
    if folds:
        settings["folds"] = folds
    if set(activities.value) != set(map_activities):
        settings["activities"] = sorted(activities.value)
    return (settings,)


@app.cell(hide_code=True)
def _(mo, set_settings, settings):
    # A plain button rather than `mo.ui.run_button`: `run_button.value` resets
    # on unrelated re-runs, which would blank the map whenever a control
    # changed. An on_click callback fires only on an actual click.
    refresh_button = mo.ui.button(
        label="Refresh visualization",
        kind="success",
        on_click=lambda _: set_settings(settings),
    )
    return (refresh_button,)


@app.cell(hide_code=True)
def _(get_settings, mo, settings):
    # Apart from the button: a state setter does not re-run its own cell, so
    # this would otherwise miss the click.
    if settings == get_settings():
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
    folding_panel,
    log_picker,
    map_type,
    mo,
    refresh_button,
    refresh_status,
    visualize_empty_cases,
):
    mo.vstack(
        [
            mo.md("## Linear Continuous Process Mapper"),
            log_picker,
            mo.hstack(
                [map_type, allow_loops, visualize_empty_cases], justify="start", gap=2
            ),
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
def _(black):
    def to_code(settings):
        """Write `settings` as a call to paste into a cell of its own."""
        arguments = ", ".join(f"{k}={v!r}" for k, v in settings.items())
        # Not `figure, metadata`: marimo needs names unique across cells.
        call = f"fixed_map, fixed_metadata = lcm_service.generate({arguments})\nfixed_map"
        return black.format_str(call, mode=black.Mode()).strip()

    return (to_code,)


@app.cell
def _(get_settings, lcm_service, mo, to_code):
    _settings = get_settings()
    try:
        _figure, _metadata = lcm_service.generate(**_settings)
    except ValueError as _e:
        mo.stop(True, mo.callout(mo.md(str(_e)), kind="danger"))

    _summary = lcm_service.summarize_metadata(_metadata)
    mo.vstack(
        [
            # Render the figure directly. Do NOT wrap it in `mo.ui.plotly()`:
            # that wrapper adds Plotly selection-event handling, which Sankey
            # traces do not support, and it fails at render time with
            # "Cannot read properties of null (reading 'getAttribute')",
            # leaving a blank plot area. Hover and node dragging still work.
            _figure,
            mo.md(" · ".join(f"**{k}**: {v}" for k, v in _summary.items())),
            mo.accordion(
                {
                    "Reproduce this map in code": mo.md(
                        f"```python\n{to_code(_settings)}\n```"
                    )
                }
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
