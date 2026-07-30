from launcher.updater import check_for_updates, get_release_info


def test_check_for_updates():
    assert check_for_updates() is None


def test_get_release_info():
    assert get_release_info() == {}
