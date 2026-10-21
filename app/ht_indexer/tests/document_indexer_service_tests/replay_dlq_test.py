import sys
from unittest.mock import MagicMock, patch

import pytest
from document_indexer_service import replay_dlq
from ht_queue_service.dead_letter_replay import ReplaySummary
from pika.exceptions import ChannelClosedByBroker


def _run_main(monkeypatch: pytest.MonkeyPatch, *argv: str, replay: MagicMock) -> MagicMock:
    """Run replay_dlq.main() with the broker and the replay function replaced.

    ChannelCreator is patched with autospec, so the test fails if main() calls it with
    arguments its real constructor does not accept (it did, after the heartbeat change).
    """
    monkeypatch.setattr(sys, "argv", ["replay_dlq", *argv])
    with (
        patch.object(replay_dlq, "ChannelCreator", autospec=True) as channel_creator_class,
        patch.object(replay_dlq, "replay_dead_letter_messages", replay),
    ):
        channel_creator = channel_creator_class.return_value
        channel_creator.get_channel.return_value = MagicMock(is_open=True)
        # An instance attribute set in the real __init__, so autospec does not know about it
        channel_creator.connection = MagicMock(queue_connection=None)
        replay_dlq.main()
    result: MagicMock = channel_creator_class
    return result


def test_main_passes_the_arguments_through_and_builds_the_channel_from_the_queue_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replay = MagicMock(return_value=ReplaySummary(3, 2, 2))

    channel_creator_class = _run_main(monkeypatch, "--max", "2", "--dry-run", replay=replay)

    assert replay.call_args.kwargs == {"max_messages": 2, "dry_run": True}
    # user, password and host come from the environment; the heartbeat from indexer_config.yml
    *connection_settings, heartbeat = channel_creator_class.call_args.args
    assert len(connection_settings) == 3
    assert heartbeat == 0


def test_main_exits_with_an_error_when_the_dead_letter_queue_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replay = MagicMock(side_effect=ChannelClosedByBroker(404, "NOT_FOUND - no queue"))

    with pytest.raises(SystemExit) as exit_info:
        _run_main(monkeypatch, replay=replay)

    assert exit_info.value.code == 1
