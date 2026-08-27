from pathlib import Path


def pytest_addoption(parser):
    """Add baseline generation flag."""
    parser.addoption(
        "--generate-baselines",
        action="store_true",
        help="Generate baseline images for visual tests"
    )


def generate_baselines_if_requested(config, artifacts_dir):
    """Write face.png if --generate-baselines is passed."""
    if config.getoption("--generate-baselines"):
        from boostgauge.skins.stingray import render_face
        img = render_face(256)
        path = artifacts_dir / "face-256.png"
        img.save(path)
        print(path.resolve())


def pytest_sessionfinish(session, exitstatus):
    """Hook baseline generation into pytest after tests finish."""
    artifacts_dir = Path(session.config.rootdir) / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    generate_baselines_if_requested(session.config, artifacts_dir)