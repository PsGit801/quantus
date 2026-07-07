from ddbot.config import Secrets
from ddbot.sync import owner_allow_set


def test_owner_allow_set_parses_chat_id():
    assert owner_allow_set(Secrets(telegram_chat_id="806402113")) == {806402113}


def test_owner_allow_set_empty_when_missing():
    assert owner_allow_set(Secrets()) == set()


def test_owner_allow_set_ignores_non_integer():
    assert owner_allow_set(Secrets(telegram_chat_id="not-a-number")) == set()


def test_listen_module_imports():
    # The loop is thin over the already-tested handle_update; just ensure it imports.
    import ddbot.listen as listen

    assert hasattr(listen, "main")
