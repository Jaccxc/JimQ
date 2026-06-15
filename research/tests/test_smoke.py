"""Smoke tests for the isolated research venv.

Behaviour under test: the research environment can import its full heavy
dependency stack AND the shared ``jimq_core`` feature library (anti train/serve
skew), and the ``jimq_research`` package skeleton is importable.

These start RED (deps not installed / package not built) and turn GREEN once
``uv sync`` provisions the isolated research venv.
"""


def test_import_torch():
    import torch  # noqa: F401

    assert torch.__version__


def test_import_gymnasium():
    import gymnasium  # noqa: F401

    assert gymnasium.__version__


def test_import_stable_baselines3():
    import stable_baselines3  # noqa: F401

    assert stable_baselines3.__version__


def test_import_mlflow():
    import mlflow  # noqa: F401

    assert mlflow.__version__


def test_import_polars():
    import polars  # noqa: F401

    assert polars.__version__


def test_import_jimq_core_features():
    """Shared feature lib must be importable via local path dependency."""
    import jimq_core  # noqa: F401
    from jimq_core import features  # noqa: F401

    assert hasattr(features, "__file__")


def test_jimq_research_skeleton_importable():
    """Package skeleton + all placeholder subpackages import cleanly."""
    import jimq_research
    from jimq_research import data, envs, models, training, export  # noqa: F401

    assert jimq_research.__version__
