from types import SimpleNamespace

from app.api_extra import _note_author, _note_out


def test_system_notes_are_labeled_system():
    out = _note_author()
    assert out["role"] == "system"
    assert out["username"] == "system"
    assert out["actor"] == "system"


def test_admin_and_user_notes_use_username():
    admin = SimpleNamespace(username="root", role="admin", name="Root Admin")
    user = SimpleNamespace(username="ops", role="user", name="Ops")
    assert _note_author(admin) == {"actor": "root", "username": "root", "role": "admin"}
    assert _note_author(user) == {"actor": "ops", "username": "ops", "role": "user"}


def test_historic_username_without_user_row_is_still_a_user():
    out = _note_author(actor="atanu")
    assert out["role"] == "user"
    assert out["username"] == "atanu"


def test_note_out_includes_author_fields():
    note = SimpleNamespace(
        id=8,
        actor="root",
        user_id=1,
        body="Working on the incident.",
        work_note=1,
        created_at="2026-09-24T18:19:00",
    )
    user = SimpleNamespace(username="root", role="admin", name="Root")
    out = _note_out(note, user)
    assert out["username"] == "root"
    assert out["role"] == "admin"
    assert out["body"] == "Working on the incident."
