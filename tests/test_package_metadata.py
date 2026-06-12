from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_scripts_are_declared():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'video-frame-preprocess = "video_frame_preprocess.cli:main"' in pyproject
    assert 'video-frame-preprocess-batch = "video_frame_preprocess.batch:main"' in pyproject
    assert 'video-frame-preprocess-health = "video_frame_preprocess.health:main"' in pyproject
    assert 'video-frame-preprocess-demo = "video_frame_preprocess.demo:main"' in pyproject


def test_project_metadata_is_release_ready():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "keywords = [" in pyproject
    assert "classifiers = [" in pyproject
    assert "[project.urls]" in pyproject
    assert 'opencv-python>=' in pyproject
    assert 'numpy>=' in pyproject
    assert "[project.optional-dependencies]" in pyproject
    assert '"build"' in pyproject
    assert '"ruff"' in pyproject
    assert '"mypy"' in pyproject
    assert '"pre-commit"' in pyproject
    assert "[tool.ruff]" in pyproject
    assert "[tool.mypy]" in pyproject


def test_quality_filter_has_focused_modules():
    expected_modules = [
        "models.py",
        "quality.py",
        "selection.py",
        "video_io.py",
        "reporting.py",
        "demo.py",
    ]

    package_dir = ROOT / "src" / "video_frame_preprocess"
    for name in expected_modules:
        assert (package_dir / name).is_file(), name

    quality_filter = package_dir / "quality_filter.py"
    assert len(quality_filter.read_text(encoding="utf-8").splitlines()) < 260


def test_default_config_uses_standalone_paths():
    config_path = ROOT / "src" / "video_frame_preprocess" / "config" / "default.json"
    text = config_path.read_text(encoding="utf-8")

    old_project_output_path = "video_" + "preprocess/outputs"
    assert old_project_output_path not in text
    assert '"input_dir": "input"' in text
    assert '"output_dir": "outputs"' in text


def test_design_notes_do_not_include_private_connection_details():
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "docs").glob("*.md"))

    forbidden = ["connect." + "westx", "16" + "NHz"]
    for token in forbidden:
        assert token not in docs


def test_release_docs_are_present():
    required = [
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "SECURITY.md",
        ".pre-commit-config.yaml",
        "docs/artifact-contract.md",
        "docs/usage.md",
    ]

    for relative_path in required:
        path = ROOT / relative_path
        assert path.is_file(), relative_path
        assert path.read_text(encoding="utf-8").strip(), relative_path
