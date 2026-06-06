from app.services.transcript_editor import update_transcript_speaker


def test_update_transcript_speaker_updates_polished_and_raw_same_index():
    transcript = [
        {"speaker": "杜同贺", "speaker_label": "speaker_0", "text": "开始"},
        {"speaker": "发言人B", "speaker_label": "speaker_1", "text": "实验异常"},
    ]
    polished = [
        {"speaker": "杜同贺", "text": "开始。", "ts": 1.0},
        {"speaker": "发言人B", "text": "实验异常。", "ts": 12.0},
    ]
    mapping = {"speaker_0": "杜同贺", "speaker_1": "发言人B"}

    result = update_transcript_speaker(
        transcript=transcript,
        transcript_polished=polished,
        speaker_mapping=mapping,
        entry_index=1,
        speaker="吴孟铨",
    )

    assert result.transcript[1]["speaker"] == "吴孟铨"
    assert result.transcript_polished[1]["speaker"] == "吴孟铨"
    assert result.speaker_mapping["speaker_1"] == "吴孟铨"


def test_update_transcript_speaker_can_update_only_polished_when_raw_missing():
    result = update_transcript_speaker(
        transcript=[],
        transcript_polished=[{"speaker": "发言人B", "text": "继续测试", "ts": 46.0}],
        speaker_mapping=None,
        entry_index=0,
        speaker="杜同贺",
    )

    assert result.transcript == []
    assert result.transcript_polished[0]["speaker"] == "杜同贺"
    assert result.speaker_mapping == {}


def test_update_transcript_speaker_rejects_invalid_index():
    try:
        update_transcript_speaker(
            transcript=[],
            transcript_polished=[],
            speaker_mapping={},
            entry_index=0,
            speaker="杜同贺",
        )
    except IndexError as exc:
        assert "entry_index" in str(exc)
    else:
        raise AssertionError("expected IndexError")
