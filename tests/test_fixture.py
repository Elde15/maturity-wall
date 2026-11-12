"""Gate 6: the committed fixture rebuilds from scratch and matches its stored outputs."""
from mwall import fixture


def test_fixture_rebuild_matches_stored_outputs():
    assert fixture.build(update=False, log=lambda *_: None)
