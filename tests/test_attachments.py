from app.attachments import attachment_kind, sanitize_filename
from app.models import ARCHIVE_INCIDENT_STATUSES, INCIDENT_STATUSES, LIVE_INCIDENT_STATUSES, normalize_incident_status


def test_live_queue_is_open_work():
    assert "open" in LIVE_INCIDENT_STATUSES
    assert "active" in LIVE_INCIDENT_STATUSES
    assert "work_in_progress" in LIVE_INCIDENT_STATUSES
    assert "pending" in LIVE_INCIDENT_STATUSES
    assert "monitor" in LIVE_INCIDENT_STATUSES
    assert "closed_successful" in ARCHIVE_INCIDENT_STATUSES
    assert "closed_unsuccessful" in ARCHIVE_INCIDENT_STATUSES
    assert "cancelled" in ARCHIVE_INCIDENT_STATUSES
    assert "auto_resolved" in ARCHIVE_INCIDENT_STATUSES
    assert "open" not in ARCHIVE_INCIDENT_STATUSES
    assert INCIDENT_STATUSES == (
        "open",
        "active",
        "work_in_progress",
        "closed_successful",
        "closed_unsuccessful",
        "cancelled",
        "auto_resolved",
        "monitor",
        "pending",
    )
    assert normalize_incident_status("acknowledged") == "work_in_progress"
    assert normalize_incident_status("resolved") == "closed_successful"
    assert normalize_incident_status("Closed unsucessfull") == "closed_unsuccessful"


def test_attachment_kind_accepts_images_and_files():
    assert attachment_kind("shot.PNG") == "image"
    assert attachment_kind("notes.pdf") == "file"
    assert attachment_kind("trace.pcap") == "file"
    assert attachment_kind("payload.exe") is None
    assert attachment_kind("page.html") is None


def test_sanitize_filename_strips_paths():
    assert "/" not in sanitize_filename("../../etc/passwd.txt")
    assert sanitize_filename("my screenshot (1).png").endswith(".png")
