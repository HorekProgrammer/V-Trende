import json
import pytest
from pathlib import Path
from database.db import connect
from database.load_outbox import load_file, load_outbox, PayloadError

@pytest.fixture
def db_conn():
    try:
        with connect() as conn:
            yield conn
    except Exception:
        pytest.skip("Нет подключения к БД")

def test_load_file_success(db_conn, tmp_path):
    """Тест успешной загрузки корректного пакета."""
    payload = {
        "type": "chart",
        "source": "test_source",
        "chart": "test_chart",
        "category": "music",
        "week_start": "2026-11-16",  # Понедельник (исправлено!)
        "entries": [
            {
                "position": 1,
                "title": "Тестовый трек",
                "match_key": "test_track",
                "genre": None
            }
        ]
    }
    file_path = tmp_path / "test_payload.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    result_message = load_file(db_conn, file_path)

    assert "test_source" in result_message
    assert "test_chart" in result_message
    assert "1 позиций" in result_message

def test_load_file_invalid_json(db_conn, tmp_path):
    """Тест обработки битого JSON."""
    file_path = tmp_path / "broken.json"
    file_path.write_text("{ невалидный json", encoding="utf-8")

    with pytest.raises(PayloadError) as exc_info:
        load_file(db_conn, file_path)

    assert "Не удалось прочитать JSON" in str(exc_info.value)

def test_load_outbox_moves_files(db_conn, tmp_path):
    """Тест того, что после загрузки файлы переносятся в папку loaded."""
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()

    payload = {
        "type": "chart",
        "source": "test_source",
        "chart": "test_chart",
        "category": "movies",
        "week_start": "2026-11-16",  # Понедельник (исправлено!)
        "entries": [{"position": 1, "title": "Фильм", "match_key": "movie_1"}]
    }
    file_path = outbox_dir / "valid.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded, failed = load_outbox(db_conn, directory=outbox_dir, keep=False)

    assert len(loaded) == 1
    assert len(failed) == 0
    assert not file_path.exists()
    assert (outbox_dir / "loaded" / "valid.json").exists()