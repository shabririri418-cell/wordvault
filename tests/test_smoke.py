def test_package_exposes_version() -> None:
    import wordvault

    assert wordvault.__version__ == "0.1.0"

