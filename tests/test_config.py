from training import config


def test_protocol_dir_exists_and_version():
    assert config.PROTOCOL_DIR.is_dir()
    assert config.PROTOCOL_VERSION == "0.3.0"
