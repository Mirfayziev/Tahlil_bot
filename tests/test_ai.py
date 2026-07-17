"""AI moduli testlari — haqiqiy Anthropic API chaqirilmaydi (mock ishlatiladi)."""
import json
from unittest.mock import MagicMock, patch

from app.ai.service import analyze_request_text, predict_delay_risk


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


def _fake_response(payload: dict):
    resp = MagicMock()
    resp.content = [_FakeTextBlock(json.dumps(payload, ensure_ascii=False))]
    return resp


def test_analyze_request_text_no_api_key_returns_none(app, category):
    app.config["ANTHROPIC_API_KEY"] = ""
    with app.app_context():
        result = analyze_request_text("Kran buzilgan", [category])
    assert result is None


def test_analyze_request_text_parses_valid_response(app, category):
    app.config["ANTHROPIC_API_KEY"] = "fake-key-for-test"
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response({
        "category_name": category.name_uz,
        "priority": "yuqori",
        "summary": "Qisqa xulosa",
        "draft_reply": "Tez orada hal qilinadi",
    })

    with app.app_context():
        with patch("app.ai.service._get_client", return_value=fake_client):
            result = analyze_request_text("Kran buzilgan, suv oqyapti", [category])

    assert result["category_id"] == category.id
    assert result["priority"] == "yuqori"
    assert result["summary"] == "Qisqa xulosa"
    assert result["draft_reply"] == "Tez orada hal qilinadi"


def test_analyze_request_text_handles_malformed_json(app, category):
    app.config["ANTHROPIC_API_KEY"] = "fake-key-for-test"
    fake_client = MagicMock()
    fake_client.messages.create.return_value = MagicMock(
        content=[_FakeTextBlock("bu JSON emas, oddiy matn")]
    )

    with app.app_context():
        with patch("app.ai.service._get_client", return_value=fake_client):
            result = analyze_request_text("Test", [category])

    assert result is None


def test_analyze_request_text_handles_api_exception(app, category):
    app.config["ANTHROPIC_API_KEY"] = "fake-key-for-test"
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("API xatosi")

    with app.app_context():
        with patch("app.ai.service._get_client", return_value=fake_client):
            result = analyze_request_text("Test", [category])

    assert result is None


def test_analyze_request_text_unknown_category_name(app, category):
    app.config["ANTHROPIC_API_KEY"] = "fake-key-for-test"
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_response({
        "category_name": "Mavjud bo'lmagan kategoriya",
        "priority": "orta",
        "summary": "s", "draft_reply": "d",
    })

    with app.app_context():
        with patch("app.ai.service._get_client", return_value=fake_client):
            result = analyze_request_text("Test", [category])

    assert result["category_id"] is None
    assert result["priority"] == "orta"


def test_predict_delay_risk_low_load():
    result = predict_delay_risk(None, current_open_count=1, avg_completion_hours=2, sla_hours=24)
    assert result["risk_level"] == "past"
    assert result["risk_score"] < 40


def test_predict_delay_risk_high_load():
    result = predict_delay_risk(None, current_open_count=20, avg_completion_hours=48, sla_hours=24)
    assert result["risk_level"] == "yuqori"
    assert result["risk_score"] >= 70


def test_predict_delay_risk_handles_zero_sla():
    result = predict_delay_risk(None, current_open_count=5, avg_completion_hours=10, sla_hours=0)
    assert isinstance(result["risk_score"], float)
