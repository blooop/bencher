import textwrap

import bencher as bch

from .generate_examples import GENERATED_DIR


class MetaGeneratorBase(bch.ParametrizedSweep):
    """Shared base class for meta-generators that produce Python example files."""

    plots = bch.ResultReference(units="int")

    def generate_example(
        self,
        *,
        title,
        output_dir,
        filename,
        function_name,
        imports,
        body,
        run_kwargs=None,
        module_docstring=None,
        function_docstring=None,
    ):
        """Write a runnable Python example file.

        Args:
            title: Docstring / heading text.
            output_dir: Relative path under ``GENERATED_DIR``.
            filename: Python file stem (e.g. ``result_var_1d``).
            function_name: Name of the example function (e.g. ``example_result_var_1d``).
            imports: Import lines placed at the top of the file.
            body: Unindented function body lines. Indentation is applied automatically.
            run_kwargs: Dict of keyword args for ``bch.run()`` in ``__main__``
                        (e.g. ``{"level": 4, "repeats": 10}``).
            module_docstring: Optional multi-line module docstring. Falls back to title.
            function_docstring: Optional multi-line function docstring. Falls back to title.
        """
        if run_kwargs is None:
            run_kwargs = {}
        indented_body = textwrap.indent(body, "    ")
        kwargs_str = "".join(f", {k}={v!r}" for k, v in run_kwargs.items())
        mod_doc = module_docstring or f"Auto-generated example: {title}."
        func_doc = function_docstring or f"{title}."
        # Indent multi-line function docstrings
        if "\n" in func_doc:
            func_doc = textwrap.indent(func_doc, "    ").strip()
        content = f'''"""{mod_doc}"""

{imports}


def {function_name}(run_cfg=None):
    """{func_doc}"""
{indented_body}
    return bench


if __name__ == "__main__":
    bch.run({function_name}{kwargs_str})
'''
        fpath = GENERATED_DIR / output_dir / f"{filename}.py"
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return fpath

    def generate_sweep_example(
        self,
        *,
        title,
        output_dir,
        filename,
        function_name,
        benchable_class,
        benchable_module,
        input_vars,
        result_vars,
        const_vars=None,
        post_sweep_line=None,
        run_cfg_lines=None,
        extra_imports=None,
        run_kwargs=None,
        module_docstring=None,
        function_docstring=None,
        body_comments=None,
    ):
        """Build imports + body and call generate_example() for a standard sweep.

        Args:
            benchable_class: Class name to instantiate (e.g. "BenchableObject").
            benchable_module: Module to import from (e.g. "bencher.example.meta.example_meta").
            input_vars: Code string for input_vars (e.g. '["float1"]').
            result_vars: Code string for result_vars (e.g. '["distance"]').
            const_vars: Optional code string for const_vars (e.g. 'dict(noise_scale=0.15)').
            post_sweep_line: Optional line after plot_sweep (e.g. 'res.to_bar()').
            run_cfg_lines: Optional list of lines like 'run_cfg.use_optuna = True'.
            extra_imports: Optional list of additional import lines.
            run_kwargs: Dict of kwargs for bch.run() (e.g. {"level": 4, "repeats": 10}).
            module_docstring: Optional multi-line module docstring.
            function_docstring: Optional multi-line function docstring.
            body_comments: Optional dict mapping body section to inline comment.
                Keys: "run_cfg", "bench", "sweep", "post_sweep".
        """
        if body_comments is None:
            body_comments = {}
        import_lines = [
            "import bencher as bch",
            f"from {benchable_module} import {benchable_class}",
        ]
        if extra_imports:
            import_lines.extend(extra_imports)
        imports = "\n".join(import_lines)

        body_lines = []
        if run_cfg_lines:
            if "run_cfg" in body_comments:
                body_lines.append(f"# {body_comments['run_cfg']}")
            body_lines.append("run_cfg = run_cfg or bch.BenchRunCfg()")
            body_lines.extend(run_cfg_lines)

        if "bench" in body_comments:
            body_lines.append(f"# {body_comments['bench']}")
        body_lines.append(f"bench = {benchable_class}().to_bench(run_cfg)")

        # Build plot_sweep call
        if "sweep" in body_comments:
            body_lines.append(f"# {body_comments['sweep']}")
        sweep_parts = [f"input_vars={input_vars}"]
        sweep_parts.append(f"result_vars={result_vars}")
        if const_vars:
            sweep_parts.append(f"const_vars={const_vars}")
        sweep_args = ", ".join(sweep_parts)

        use_res = post_sweep_line is not None
        prefix = "res = " if use_res else ""
        body_lines.append(f"{prefix}bench.plot_sweep({sweep_args})")

        if post_sweep_line:
            if "post_sweep" in body_comments:
                body_lines.append(f"# {body_comments['post_sweep']}")
            body_lines.append(post_sweep_line)

        body = "\n".join(body_lines) + "\n"

        return self.generate_example(
            title=title,
            output_dir=output_dir,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            run_kwargs=run_kwargs or {},
            module_docstring=module_docstring,
            function_docstring=function_docstring,
        )
