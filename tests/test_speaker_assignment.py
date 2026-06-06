import numpy as np

from app.services.speaker_assignment import (
    SpeakerMatch,
    correct_speaker_name,
    finalize_cluster_speakers,
    should_force_split,
)


def test_finalize_cluster_speakers_keeps_only_best_duplicate_known_name():
    """多个聚类命中同一个成员时，只保留最可信的一簇，其余标为未知发言人。"""
    result = finalize_cluster_speakers(
        cluster_ids=[0, 1],
        cluster_votes={0: ["杜同贺", "杜同贺"], 1: ["杜同贺"]},
        representative_matches={
            0: SpeakerMatch(name="杜同贺", member_id=7, confidence=0.64),
            1: SpeakerMatch(name="杜同贺", member_id=7, confidence=0.49),
        },
    )

    assert result.cluster_to_name[0] == "杜同贺"
    assert result.cluster_to_name[1].startswith("发言人")
    assert result.known_member_ids == {7}
    assert result.ambiguous_clusters[1]["reason"] == "duplicate_known_name"
    assert result.ambiguous_clusters[1]["duplicate_of"] == "杜同贺"


def test_finalize_cluster_speakers_unknown_labels_do_not_collide_with_known_names():
    result = finalize_cluster_speakers(
        cluster_ids=[0, 1, 2],
        cluster_votes={0: ["杜同贺"], 1: [], 2: []},
        representative_matches={},
    )

    assert result.cluster_to_name[0] == "杜同贺"
    assert len(set(result.cluster_to_name.values())) == 3
    assert all(result.cluster_to_name[cid] for cid in [1, 2])


def test_should_force_split_detects_distributed_single_cluster_embeddings():
    embeddings = [
        np.array([1.0, 0.0, 0.0], dtype=np.float32),
        np.array([0.95, 0.05, 0.0], dtype=np.float32),
        np.array([0.35, 0.94, 0.0], dtype=np.float32),
    ]

    assert should_force_split(embeddings, std_threshold=0.15, min_similarity_threshold=0.55)


def test_correct_speaker_name_uses_phonetic_then_fuzzy_member_match():
    members = {"杜同贺": 1, "吴孟铨": 2, "王天志": 3}

    assert correct_speaker_name("吴孟全", members) == "吴孟铨"
    assert correct_speaker_name("王天之", members) == "王天志"
    assert correct_speaker_name("杜同鹤", members) == "杜同贺"
    assert correct_speaker_name("发言人A", members) == "发言人A"
