import uuid

from app.tasks_registry import REGISTRY


def test_registry_has_exactly_the_required_task_types():
    assert set(REGISTRY.keys()) == {
        "text",
        "writing_task",
        "true_false",
        "fill_gaps",
        "match_cards",
        "reorder",
        "sorting",
        "integration",
        "test",
        "file",
        "image",
        "audio",
        "word_list",
        "voice_recording",
    }
    assert "html_code" not in REGISTRY


def test_file_task_rejects_non_document_mime_type(api_client):
    c = api_client
    r = c.post("/lessons", json={"owner_id": str(uuid.uuid4()), "title": "Lesson"})
    lesson = r.json()
    section = c.get(f"/lessons/{lesson['id']}/sections").json()[0]

    upload = c.post("/files", files={"file": ("clip.mp3", b"not-a-document", "audio/mpeg")})
    file_id = upload.json()["id"]

    r = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "file",
            "payload": {"description": ""},
            "created_by": lesson["owner_id"],
            "file_id": file_id,
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_request"


def test_file_task_accepts_pdf(api_client):
    c = api_client
    r = c.post("/lessons", json={"owner_id": str(uuid.uuid4()), "title": "Lesson"})
    lesson = r.json()
    section = c.get(f"/lessons/{lesson['id']}/sections").json()[0]

    upload = c.post(
        "/files", files={"file": ("worksheet.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )
    file_id = upload.json()["id"]

    r = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "file",
            "payload": {"description": "Homework worksheet"},
            "created_by": lesson["owner_id"],
            "file_id": file_id,
        },
    )
    assert r.status_code == 200, r.text


def test_image_task_accepts_png_but_not_pdf(api_client):
    c = api_client
    r = c.post("/lessons", json={"owner_id": str(uuid.uuid4()), "title": "Lesson"})
    lesson = r.json()
    section = c.get(f"/lessons/{lesson['id']}/sections").json()[0]

    png_upload = c.post("/files", files={"file": ("pic.png", b"fake-png-bytes", "image/png")})
    r_ok = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "image",
            "payload": {"alt_text": "A picture"},
            "created_by": lesson["owner_id"],
            "file_id": png_upload.json()["id"],
        },
    )
    assert r_ok.status_code == 200, r_ok.text

    pdf_upload = c.post(
        "/files", files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")}
    )
    r_bad = c.post(
        f"/sections/{section['id']}/tasks",
        json={
            "task_type": "image",
            "payload": {"alt_text": "Wrong type"},
            "created_by": lesson["owner_id"],
            "file_id": pdf_upload.json()["id"],
        },
    )
    assert r_bad.status_code == 400
