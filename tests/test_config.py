from geopulse import config


def test_project_root_exists():
    assert config.PROJECT_ROOT.exists()


def test_directories_created():
    config.ensure_directories()
    assert config.RAW_DIR.exists()
    assert config.PROCESSED_DIR.exists()
