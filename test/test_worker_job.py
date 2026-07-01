"""Tests for bencher/worker_job.py — WorkerJob input preparation and hashing.

WorkerJob pickling is covered in test/test_multiprocessing_executor.py and the
JobCache machinery in test/test_job.py, so they are not duplicated here.
"""

from bencher.worker_job import WorkerJob


def make_job(
    function_input_vars=(1, 2),
    dims_name=("x", "y"),
    constant_inputs=None,
    bench_cfg_sample_hash="sample_hash",
    tag="",
) -> WorkerJob:
    """Construct a WorkerJob with setup_hashes() already applied."""
    job = WorkerJob(
        function_input_vars=list(function_input_vars),
        index_tuple=(0, 0),
        dims_name=list(dims_name),
        constant_inputs=constant_inputs,
        bench_cfg_sample_hash=bench_cfg_sample_hash,
        tag=tag,
    )
    job.setup_hashes()
    return job


# ── construction defaults ───────────────────────────────────────────────────


class TestWorkerJobDefaults:
    def test_defaults_before_setup(self):
        job = WorkerJob(
            function_input_vars=[1],
            index_tuple=(0,),
            dims_name=["x"],
            constant_inputs=None,
            bench_cfg_sample_hash="h",
            tag="",
        )
        assert job.function_input is None
        assert job.canonical_input is None
        assert job.fn_inputs_sorted is None
        assert job.function_input_signature_pure is None
        assert job.found_in_cache is False
        assert job.msgs == []

    def test_msgs_lists_are_independent(self):
        job_a = make_job()
        job_b = make_job()
        job_a.msgs.append("only on a")
        assert job_b.msgs == []


# ── setup_hashes: function input construction ───────────────────────────────


class TestFunctionInputConstruction:
    def test_function_input_zips_dims_with_values(self):
        job = make_job(function_input_vars=(1, 2), dims_name=("x", "y"))
        assert job.function_input == {"x": 1, "y": 2}

    def test_canonical_input_sorted_by_dim_name(self):
        # dims given in non-alphabetical order: canonical form sorts by key
        job = make_job(function_input_vars=(2, 1), dims_name=("y", "x"))
        assert job.function_input == {"y": 2, "x": 1}
        assert job.canonical_input == (1, 2)

    def test_constant_inputs_merged_into_function_input(self):
        job = make_job(constant_inputs={"c": 5})
        assert job.function_input == {"x": 1, "y": 2, "c": 5}

    def test_constant_inputs_excluded_from_canonical_input(self):
        # canonical_input is computed before constants are merged
        job = make_job(constant_inputs={"c": 5})
        assert job.canonical_input == (1, 2)

    def test_constant_inputs_override_dim_values(self):
        job = make_job(function_input_vars=(1, 2), dims_name=("x", "y"), constant_inputs={"y": 9})
        assert job.function_input == {"x": 1, "y": 9}

    def test_fn_inputs_sorted_is_sorted_key_value_pairs(self):
        job = make_job(function_input_vars=(2, 1), dims_name=("y", "x"), constant_inputs={"a": 3})
        assert job.fn_inputs_sorted == [("a", 3), ("x", 1), ("y", 2)]


# ── setup_hashes: hash behavior ─────────────────────────────────────────────


class TestFunctionInputSignature:
    def test_same_inputs_same_hash(self):
        assert make_job().function_input_signature_pure == make_job().function_input_signature_pure

    def test_signature_is_sha1_hex_string(self):
        sig = make_job().function_input_signature_pure
        assert isinstance(sig, str)
        assert len(sig) == 40
        int(sig, 16)  # valid hexadecimal

    def test_different_values_different_hash(self):
        job_a = make_job(function_input_vars=(1, 2))
        job_b = make_job(function_input_vars=(1, 3))
        assert job_a.function_input_signature_pure != job_b.function_input_signature_pure

    def test_different_dim_names_different_hash(self):
        job_a = make_job(dims_name=("x", "y"))
        job_b = make_job(dims_name=("x", "z"))
        assert job_a.function_input_signature_pure != job_b.function_input_signature_pure

    def test_different_tag_different_hash(self):
        job_a = make_job(tag="tag_a")
        job_b = make_job(tag="tag_b")
        assert job_a.function_input_signature_pure != job_b.function_input_signature_pure

    def test_constant_inputs_affect_hash(self):
        job_a = make_job(constant_inputs={"c": 5})
        job_b = make_job(constant_inputs={"c": 6})
        assert job_a.function_input_signature_pure != job_b.function_input_signature_pure

    def test_dim_order_does_not_affect_hash(self):
        # the signature is built from sorted inputs, so dim ordering is irrelevant
        job_a = make_job(function_input_vars=(1, 2), dims_name=("x", "y"))
        job_b = make_job(function_input_vars=(2, 1), dims_name=("y", "x"))
        assert job_a.function_input_signature_pure == job_b.function_input_signature_pure

    def test_bench_cfg_sample_hash_does_not_affect_pure_signature(self):
        # the "pure" signature covers only the function inputs and tag
        job_a = make_job(bench_cfg_sample_hash="hash_a")
        job_b = make_job(bench_cfg_sample_hash="hash_b")
        assert job_a.function_input_signature_pure == job_b.function_input_signature_pure
