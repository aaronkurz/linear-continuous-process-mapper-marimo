import marimo

__generated_with = "0.21.1"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import black
    import marimo as mo
    import pandas as pd

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
    return black, lcm, log_dir, log_picker, mo, pd


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
def _(lcm_service, mo, pd):
    # A form sends its values to Python only on submit, so changing a control
    # does not redraw the map until "Refresh visualization" is clicked.
    all_activities = lcm_service.get_all_activities()
    controls = (
        mo.md(
            """
            {map_type} &nbsp; {allow_loops} &nbsp; {visualize_empty_cases}

            Untick an activity to hide it. Activities given the same fold name
            become one activity.

            {table}
            """
        )
        .batch(
            map_type=mo.ui.dropdown(
                options={
                    "Set-Based": "set_based",
                    "Sequence-Based": "sequence_based",
                    "Last-Activity-Based": "last_activity_based",
                },
                value="Set-Based",
                label="Map type",
            ),
            allow_loops=mo.ui.switch(value=True, label="Allow self-loops"),
            visualize_empty_cases=mo.ui.switch(
                value=True, label="Visualize empty traces"
            ),
            table=mo.ui.data_editor(
                # A space, because the editor displays an empty string as "null".
                pd.DataFrame(
                    {"activity": all_activities, "show": True, "fold name": " "}
                ),
                editable_columns=["show", "fold name"],
            ),
        )
        .form(submit_button_label="Refresh visualization", bordered=False)
    )
    return all_activities, controls


@app.cell(hide_code=True)
def _(controls, log_picker, mo):
    mo.vstack(
        [mo.md("## Linear Continuous Process Mapper"), log_picker, controls],
        gap=0.75,
    )
    return


@app.cell(hide_code=True)
def _(all_activities, black):
    def to_settings(choices):
        """Translate the form's value into arguments for `generate`."""
        table = choices["table"]
        # The editor also lets people add rows, which start out blank.
        shown = table[table["show"].eq(True) & table["activity"].notna()]
        fold_names = shown["fold name"].fillna("").str.strip()
        is_folded = fold_names != ""
        folds = shown[is_folded].groupby(fold_names)["activity"].agg(list).to_dict()

        settings = {
            "map_type": choices["map_type"],
            "allow_loops": choices["allow_loops"],
            "visualize_empty_cases": choices["visualize_empty_cases"],
        }
        if folds:
            settings["folds"] = folds
        if set(shown["activity"]) != set(all_activities):
            settings["activities"] = sorted(
                {*shown.loc[~is_folded, "activity"], *folds}
            )
        return settings

    def to_code(settings):
        """Write `settings` as a call to paste into a cell of its own."""
        arguments = ", ".join(f"{k}={v!r}" for k, v in settings.items())
        # Not `figure, metadata`: marimo needs names unique across cells.
        call = f"fixed_map, fixed_metadata = lcm_service.generate({arguments})\nfixed_map"
        return black.format_str(call, mode=black.Mode()).strip()

    return to_code, to_settings


@app.cell
def _(controls, lcm_service, mo, to_code, to_settings):
    # Until the form is first submitted, `generate()` draws its defaults.
    _settings = to_settings(controls.value) if controls.value else {}
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
