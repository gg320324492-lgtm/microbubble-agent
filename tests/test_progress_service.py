import pytest
from app.services.progress_service import ProgressStage, STAGE_ORDER


def test_progress_stage_enum_values():
    assert ProgressStage.EXTRACTING_TRANSCRIPT.value == "extracting_transcript"
    assert ProgressStage.IDENTIFYING_SPEAKERS.value == "identifying_speakers"
    assert ProgressStage.GENERATING_TITLE.value == "generating_title"
    assert ProgressStage.GENERATING_MINUTES.value == "generating_minutes"
    assert ProgressStage.CREATING_TASKS.value == "creating_tasks"
    assert ProgressStage.LINKING_HISTORY.value == "linking_history"
    assert ProgressStage.DONE.value == "done"


def test_stage_order():
    assert STAGE_ORDER == [
        "extracting_transcript",
        "identifying_speakers",
        "generating_title",
        "generating_minutes",
        "creating_tasks",
        "linking_history",
        "done",
    ]
