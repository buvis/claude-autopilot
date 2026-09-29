"""Tests for cli/wave_slots.py: the directory semaphore that caps concurrent
wave sessions. Slots are numbered dirs under the slots dir, each holding an
`owner` file with the claimant's pid. Liveness is faked by patching
`wave_slots._pid_alive`, and sleep/clock are injected, so nothing here
depends on real time or on real sleeping.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from cli import wave_slots
from cli.wave_slots import acquire, release

LIVE_PEER = 1111
DEAD_PEER = 2222
ME = 4242
PEER = 5353  # a second live claimant, racing ME for the same slot

WAITED = "waited for a slot"


class _WouldWait(Exception):
    """Raised by an injected sleep_fn instead of waiting for a slot."""


class _Ticker:
    """A clock that moves only when the injected sleep_fn is called, so the
    heartbeat sees elapsed time without any real waiting."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, secs: float) -> None:
        self.sleeps.append(secs)
        self.now += secs


def _fake_clock() -> float:
    return 0.0


def _no_sleep(secs: float) -> None:
    raise AssertionError(f"acquire slept {secs}s with a slot free")


def _wait_once(secs: float) -> None:
    raise _WouldWait(secs)


def _only_alive(monkeypatch, *alive: int, all_alive: bool = False) -> list[int]:
    """Patch the liveness oracle; return the list that records its calls.

    The recorded pids are the questions `acquire` actually asked, in order, so
    a test can pin that a slot's fate came from the oracle being asked about
    the pid parsed out of its `owner` file, rather than from a table of the
    pid constants above. `all_alive` answers yes to every pid, which leaves
    the owner text as the only thing that can free a slot.
    """
    asked: list[int] = []

    def pid_alive(pid: int) -> bool:
        asked.append(pid)
        return all_alive or pid in alive

    monkeypatch.setattr(wave_slots, "_pid_alive", pid_alive)
    return asked


def _hold(slots: Path, n: int, owner: str) -> Path:
    slot = slots / str(n)
    slot.mkdir(parents=True)
    (slot / "owner").write_text(owner)
    return slot


def _claim_or_wait(slots: Path, count: int, pid: int) -> Path | str:
    """One acquire for `pid`: the slot it claimed, or WAITED if it polled."""
    try:
        return acquire(slots, count, pid, sleep_fn=_wait_once, clock=_fake_clock)
    except _WouldWait:
        return WAITED


def _stderr_lines(capsys) -> list[str]:
    return [line for line in capsys.readouterr().err.splitlines() if line.strip()]


def _in_slots_dir(path, slots: Path) -> bool:
    """True when this mkdir creates an entry directly in the slots dir.

    The race tests hook on that instead of on a literal `<slots>/1`, so they
    stay blind to how a claim gets published: a bare `1` dir and a staged
    `1.tmp-<pid>` dir both pass through here, and either one lets the test
    drive the same interleaving.
    """
    return Path(os.fsdecode(path)).parent == slots


def _ownerless_slot_names(slots: Path) -> list[str]:
    """Names in the slots dir that any peer would read as a free-for-all slot.

    A slot is a digit-named entry, and the rule for a digit-named entry with
    no readable `owner` is that it gets reclaimed. So a digit-named entry
    without one is a slot that a peer in another process is entitled to take,
    whatever the process that made it intends to do next. Anything not named
    as a bare number is invisible to that rule and may sit there ownerless
    for as long as a claim needs.
    """
    try:
        names = sorted(child.name for child in slots.iterdir())
    except OSError:
        return []
    ownerless = []
    for name in names:
        if not name.isdigit():
            continue
        try:
            (slots / name / "owner").read_bytes()
        except OSError:
            ownerless.append(name)
    return ownerless


def _lines_while_waiting(tmp_path, monkeypatch, capsys, *, poll, until) -> list[str]:
    """Wait `until` seconds of injected time for the one slot, then report the
    stderr lines acquire wrote while it waited.

    A live peer holds the only slot until the injected clock has moved `until`
    seconds, so the heartbeat sees elapsed time with nothing sleeping for
    real. `until` has to be a whole number of `poll`-second polls, and the
    count of lines is then a function of the clock alone: the poll size is
    free to divide the heartbeat interval or not.
    """
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    held = _hold(slots, 1, str(LIVE_PEER))
    ticker = _Ticker()

    def sleep_fn(secs: float) -> None:
        ticker.sleep(secs)
        if ticker.now >= until:
            release(held)

    slot = acquire(slots, 1, ME, sleep_fn=sleep_fn, clock=ticker.clock, poll_secs=poll)
    assert slot == slots / "1"
    assert ticker.now == until, f"waited {ticker.now}s, meant to wait {until}s"
    return _stderr_lines(capsys)


def test_acquire_creates_the_slots_dir(tmp_path, monkeypatch):
    _only_alive(monkeypatch)
    slots = tmp_path / "state" / "wave-slots"
    assert not slots.exists()
    slot = acquire(slots, 2, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slots.is_dir()
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_acquire_takes_the_first_free_slot(tmp_path, monkeypatch):
    asked = _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(LIVE_PEER))
    slot = acquire(slots, 3, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "2"
    assert (slot / "owner").read_text().strip() == str(ME)
    # The live peer's slot is untouched, and slot 3 was never claimed.
    assert (slots / "1" / "owner").read_text().strip() == str(LIVE_PEER)
    assert not (slots / "3").exists()
    # Slot 1 got skipped because the oracle was asked about the pid parsed out
    # of its owner file, not because of which pid that happens to be. Slot 2
    # holds no owner, so it takes no question to see that it is free.
    assert asked == [LIVE_PEER], f"asked the oracle {asked}"


def test_the_last_slot_of_three_is_claimed_when_the_others_are_held(
    tmp_path,
    monkeypatch,
):
    # Two live holders and count=3: the only free slot is the last one, so a
    # search that gives up before the count says to would poll for a slot
    # that is right there. _no_sleep turns that into a failure.
    _only_alive(monkeypatch, LIVE_PEER, PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(LIVE_PEER))
    _hold(slots, 2, str(PEER))
    slot = acquire(slots, 3, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "3"
    assert (slot / "owner").read_text().strip() == str(ME)
    # Both live holders keep their own slots, pid intact.
    assert (slots / "1" / "owner").read_text().strip() == str(LIVE_PEER)
    assert (slots / "2" / "owner").read_text().strip() == str(PEER)


def test_acquire_blocks_until_release(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    held = _hold(slots, 1, str(LIVE_PEER))
    sleeps: list[float] = []

    def sleep_fn(secs: float) -> None:
        sleeps.append(secs)
        if len(sleeps) == 2:
            release(held)

    slot = acquire(slots, 1, ME, sleep_fn=sleep_fn, clock=_fake_clock, poll_secs=7)
    assert sleeps == [7, 7]
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_dead_owner_slot_is_reclaimed(tmp_path, monkeypatch):
    asked = _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    stale = _hold(slots, 1, str(DEAD_PEER))
    # The dead session left a file nobody can name in advance and a subtree
    # under it, so the slot only comes back by clearing whatever is there
    # rather than by deleting a known list of names.
    junk = f"leftover-{os.urandom(6).hex()}"
    (stale / junk).write_text("junk from the dead session")
    (stale / "sub").mkdir()
    (stale / "sub" / "deep.txt").write_text("more junk, one level down")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    assert not (slot / junk).exists()  # cleared, though nothing knew its name
    assert not (slot / "sub").exists()  # and cleared right down the subtree
    # The slot came free because the oracle said its owner was gone: asked
    # once, about the pid read out of the owner file and parsed as an int.
    assert asked == [DEAD_PEER], f"asked the oracle {asked}"


def test_missing_owner_file_is_reclaimed(tmp_path, monkeypatch):
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    (slots / "1").mkdir(parents=True)
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_malformed_owner_is_reclaimed(tmp_path, monkeypatch):
    # Every pid reads as alive, so only the malformed content can free it.
    asked = _only_alive(monkeypatch, all_alive=True)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, "not-a-pid")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    # Text that is not a pid is rejected while it is parsed, so there is no
    # pid to ask the oracle about.
    assert asked == [], f"an unparseable owner needs no question, asked {asked}"


def test_owner_of_non_utf8_bytes_is_reclaimed(tmp_path, monkeypatch):
    # Every pid reads as alive, so only unreadable content can free the slot.
    # Decoding those bytes must not escape acquire and abort the launch.
    asked = _only_alive(monkeypatch, all_alive=True)
    slots = tmp_path / "wave-slots"
    (slots / "1").mkdir(parents=True)
    (slots / "1" / "owner").write_bytes(b"\xff\xfe\x00 not a pid")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    # Bytes that do not even decode yield no pid, so the oracle is not asked.
    assert asked == [], f"an unreadable owner needs no question, asked {asked}"


def test_a_non_decimal_digit_owner_is_reclaimed(tmp_path, monkeypatch):
    # Every pid reads as alive, so only the owner text can free the slot. "²"
    # is a digit to str.isdigit but not a literal int() will parse, so a guard
    # that trusts isdigit lets ValueError escape acquire and abort the launch
    # instead of reclaiming a slot whose owner is malformed.
    asked = _only_alive(monkeypatch, all_alive=True)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, "²")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    # No pid comes out of a digit int() rejects, so the oracle is not asked.
    assert asked == [], f"a digit int() rejects needs no question, asked {asked}"


def test_owner_pid_zero_is_reclaimed_not_taken_for_a_live_peer(tmp_path, monkeypatch):
    # "0" is digits but no claimant's pid: os.kill(0, 0) signals the caller's
    # own process group, so it has to be rejected while the owner text is
    # parsed and never handed to the oracle, which would call it alive
    # forever. _no_sleep fails the test if acquire polls instead of claiming.
    asked = _only_alive(monkeypatch, all_alive=True)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, "0")
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)
    assert asked == [], f"0 is no pid to ask a liveness question about: {asked}"


def test_nonpositive_count_is_rejected_instead_of_polling_forever(
    tmp_path,
    monkeypatch,
):
    _only_alive(monkeypatch)
    slots = tmp_path / "wave-slots"
    for bad in (0, -1):
        with pytest.raises(ValueError) as excinfo:
            acquire(slots, bad, ME, sleep_fn=_no_sleep, clock=_fake_clock)
        assert str(bad) in str(excinfo.value)  # the message names the count
        assert not slots.exists()  # rejected before the slots dir is created


def test_release_frees_the_slot(tmp_path, monkeypatch, capsys):
    _only_alive(monkeypatch, ME)
    slots = tmp_path / "wave-slots"
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    # A session leaves its own scratch inside the slot it holds, so freeing
    # the slot has to clear that too, and quietly: a removal that did not
    # happen is reported on stderr, so silence here means the slot is gone.
    (slot / "session.log").write_text("output from the finished session")
    release(slot)
    assert not slot.exists()
    assert _stderr_lines(capsys) == [], "freeing a slot it holds is not news"
    # With our own (live) claim gone, a second acquire gets slot 1 at once.
    again = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert again == slots / "1"


def test_release_of_a_missing_slot_is_a_noop(tmp_path, capsys):
    slot = tmp_path / "wave-slots" / "1"
    assert release(slot) is None
    assert not slot.exists()
    captured = capsys.readouterr()  # a slot already gone is not worth a word
    assert captured.err == ""
    assert captured.out == ""


def test_release_reports_a_removal_failure_on_one_stderr_line(
    tmp_path,
    monkeypatch,
    capsys,
):
    # The caller releases from a `finally:`, so a failed removal must be
    # reported rather than raised (a raise would mask the in-flight error)
    # and rather than swallowed (a silently held slot blocks the pool).
    slots = tmp_path / "wave-slots"
    slot = _hold(slots, 1, str(ME))
    real_rmdir = os.rmdir

    def failing_rmdir(path, *args, **kwargs):
        if not isinstance(path, int) and slots.name in os.fspath(path):
            raise PermissionError("Permission denied")  # no path in the text
        return real_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "rmdir", failing_rmdir)
    assert release(slot) is None
    lines = _stderr_lines(capsys)
    assert len(lines) == 1, f"expected one report of the failure, got {lines}"
    assert os.fspath(slot) in lines[0]  # the line names the slot it could not free
    assert slot.exists()  # still held: the failure was reported, not faked


def test_docs_name_the_two_variables():
    waves_md = Path(__file__).parent.parent / "references" / "waves.md"
    text = waves_md.read_text()
    assert "_AUTOPILOT_REVIEW_SLOTS_DIR" in text
    # The count variable is a prefix of the _DIR one, so a plain substring
    # check cannot fail on its own: require a boundary _DIR does not satisfy.
    count_hits = list(re.finditer(r"_AUTOPILOT_REVIEW_SLOTS(?!_DIR)", text))
    assert count_hits, "waves.md never names the slot-count variable"
    # Its default belongs beside the name, not paragraphs away.
    assert any("3" in text[hit.start() : hit.end() + 100] for hit in count_hits), (
        "waves.md does not state the default slot count of 3"
    )


def test_claim_is_exclusive_when_a_peer_wins_the_race(tmp_path, monkeypatch):
    # A live peer publishes a whole claim on slot 1 in the gap after acquire
    # found it free and before acquire's own claim lands. A claim is
    # exclusive: the loser of that race moves on to the next slot instead of
    # overwriting the winner or carrying on as if it had won.
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    real_mkdir = os.mkdir
    peer_won: list[str] = []

    def racing_mkdir(path, *args, **kwargs):
        if not peer_won and _in_slots_dir(path, slots):
            peer_won.append(os.fspath(path))
            real_mkdir(os.fspath(slots / "1"))  # the peer's claim lands first
            (slots / "1" / "owner").write_text(str(LIVE_PEER))
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", racing_mkdir)
    slot = acquire(slots, 2, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert peer_won, "acquire never created a directory in the slots dir"
    assert slot == slots / "2"
    assert (slot / "owner").read_text().strip() == str(ME)
    # The peer keeps slot 1, holding the peer's own pid.
    assert (slots / "1" / "owner").read_text().strip() == str(LIVE_PEER)


def test_a_leftover_staging_dir_does_not_abort_acquire(tmp_path, monkeypatch):
    # A staging dir outlives a lost race whenever the cleanup after it fails,
    # because that failure gets reported rather than raised. The next poll of
    # the same acquire then meets the leftover, so staging under a name that
    # can already be there aborts the launch over a directory no code path and
    # no peer ever reads. A free slot is still claimable with one sitting
    # there, and _no_sleep fails the test if acquire polls instead.
    _only_alive(monkeypatch)
    slots = tmp_path / "wave-slots"
    leftover = slots / f"1.tmp-{ME}"
    leftover.mkdir(parents=True)
    (leftover / "owner").write_text(str(ME))
    slot = acquire(slots, 1, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "1"
    assert (slot / "owner").read_text().strip() == str(ME)


def test_one_slot_is_never_handed_to_two_holders(tmp_path, monkeypatch):
    # A whole peer acquire runs inside the window ME opens by creating its
    # first directory in the slots dir, so the peer meets a claim that is
    # under way and not yet published. With count=1 exactly one of the two
    # may come back holding slots/1 and the other has to wait; nothing but
    # the test's own sleep signal may escape either acquire.
    _only_alive(monkeypatch, ME, PEER)
    slots = tmp_path / "wave-slots"
    real_mkdir = os.mkdir
    raced: list[str] = []
    outcomes: list[tuple[int, Path | str]] = []

    def racing_mkdir(path, *args, **kwargs):
        made = real_mkdir(path, *args, **kwargs)
        if not raced and _in_slots_dir(path, slots):
            raced.append(os.fspath(path))  # ME's claim is under way
            outcomes.append((PEER, _claim_or_wait(slots, 1, PEER)))
        return made

    monkeypatch.setattr(os, "mkdir", racing_mkdir)
    outcomes.append((ME, _claim_or_wait(slots, 1, ME)))
    assert raced, "acquire never created a directory in the slots dir"
    holders = [pid for pid, out in outcomes if out == slots / "1"]
    waiters = [pid for pid, out in outcomes if out == WAITED]
    assert len(holders) == 1, f"count=1 handed slot 1 to {len(holders)} holders"
    assert len(waiters) == 1, f"one acquirer had to wait, got {outcomes}"
    # The winner's own pid, intact: not the loser's, not both appended.
    assert (slots / "1" / "owner").read_text().strip() == str(holders[0])


def test_a_reclaim_never_steals_a_claim_that_went_live_first(tmp_path, monkeypatch):
    # Slot 1 holds a killed loop's leftover owner, so both acquirers read it
    # as stale. A whole peer acquire runs inside the window ME opens by moving
    # that stale slot aside: the peer reclaims it and publishes a live claim
    # of its own, which ME's rename then carries off. Moving a claim aside is
    # not owning it, so with count=1 exactly one of the two may come back
    # holding slots/1 and the other has to wait.
    _only_alive(monkeypatch, ME, PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(DEAD_PEER))
    real_rename = os.rename
    raced: list[str] = []
    outcomes: list[tuple[int, Path | str]] = []

    def racing_rename(src, dst, *args, **kwargs):
        if not raced and ".stale-" in os.fspath(dst):
            raced.append(os.fspath(dst))  # ME's reclaim is under way
            outcomes.append((PEER, _claim_or_wait(slots, 1, PEER)))
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "rename", racing_rename)
    outcomes.append((ME, _claim_or_wait(slots, 1, ME)))
    assert raced, "acquire never moved the stale slot aside"
    holders = [pid for pid, out in outcomes if out == slots / "1"]
    waiters = [pid for pid, out in outcomes if out == WAITED]
    assert len(holders) == 1, f"count=1 handed slot 1 to {len(holders)} holders"
    assert len(waiters) == 1, f"one acquirer had to wait, got {outcomes}"
    # The slot names whoever actually holds it: the reclaim that lost the race
    # put the winner's claim back rather than replacing it with its own.
    assert (slots / "1" / "owner").read_text().strip() == str(holders[0])


def test_a_reclaim_compares_the_owner_it_judged_not_a_later_read(tmp_path, monkeypatch):
    # Slot 1 holds a killed loop's leftover owner, so ME reads it as stale. A
    # whole peer acquire then runs in the window ME opens by reading that
    # owner: the peer reclaims slot 1 and publishes a live claim of its own,
    # which is what ME's reclaim then moves aside. Seeing that takes comparing
    # the moved owner against the text ME judged; a reclaim that re-reads the
    # owner instead reads the peer's live pid, finds it unchanged, and deletes
    # a claim in use. With count=1 exactly one of the two may come back
    # holding slots/1 and the other has to wait.
    _only_alive(monkeypatch, ME, PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(DEAD_PEER))
    real_owner = wave_slots._owner
    raced: list[str] = []
    outcomes: list[tuple[int, Path | str]] = []

    def racing_owner(slot: Path) -> str:
        judged = real_owner(slot)
        if not raced and slot == slots / "1":
            raced.append(judged)  # the owner text ME's staleness check saw
            outcomes.append((PEER, _claim_or_wait(slots, 1, PEER)))
        return judged

    monkeypatch.setattr(wave_slots, "_owner", racing_owner)
    outcomes.append((ME, _claim_or_wait(slots, 1, ME)))
    assert raced == [str(DEAD_PEER)], f"ME judged slot 1's owner as {raced}"
    holders = [pid for pid, out in outcomes if out == slots / "1"]
    waiters = [pid for pid, out in outcomes if out == WAITED]
    assert len(holders) == 1, f"count=1 handed slot 1 to {len(holders)} holders"
    assert len(waiters) == 1, f"one acquirer had to wait, got {outcomes}"
    # The slot names whoever actually holds it: the reclaim that lost the race
    # put the winner's claim back rather than replacing it with its own.
    assert (slots / "1" / "owner").read_text().strip() == str(holders[0])


def test_a_slot_never_appears_in_the_slots_dir_without_its_owner(
    tmp_path,
    monkeypatch,
):
    # A peer in another process sees nothing of a claim but the slots dir, so
    # the moment a numbered slot is visible there without a readable `owner`,
    # that peer is entitled to reclaim it and the pool can hand one slot to
    # two holders. The invariant is checked either side of every call that
    # can publish an entry - a directory appearing (mkdir) or moving into
    # place (rename) - so no in-process bookkeeping can stand in for it.
    _only_alive(monkeypatch, LIVE_PEER)
    slots = tmp_path / "wave-slots"
    _hold(slots, 1, str(LIVE_PEER))
    # A control, so the check below cannot pass for lack of looking: while an
    # ownerless number is there, the probe says so.
    (slots / "9").mkdir()
    assert _ownerless_slot_names(slots) == ["9"], "the probe sees nothing"
    (slots / "9").rmdir()

    seen: list[str] = []
    probed: list[str] = []
    real_mkdir, real_rename = os.mkdir, os.rename

    def check(when: str) -> None:
        probed.append(when)
        seen.extend(f"{when} {name}" for name in _ownerless_slot_names(slots))

    def watched_mkdir(path, *args, **kwargs):
        check("before mkdir:")
        try:
            return real_mkdir(path, *args, **kwargs)
        finally:
            check("after mkdir:")

    def watched_rename(src, dst, *args, **kwargs):
        check("before rename:")
        try:
            return real_rename(src, dst, *args, **kwargs)
        finally:
            check("after rename:")

    monkeypatch.setattr(os, "mkdir", watched_mkdir)
    monkeypatch.setattr(os, "rename", watched_rename)
    slot = acquire(slots, 2, ME, sleep_fn=_no_sleep, clock=_fake_clock)
    assert slot == slots / "2"
    assert (slot / "owner").read_text().strip() == str(ME)
    assert probed, "acquire claimed a slot without creating or moving anything"
    assert not seen, f"a numbered slot was visible with no owner: {seen}"


def test_waiting_prints_one_stderr_line_per_five_minutes(
    tmp_path,
    monkeypatch,
    capsys,
):
    # 70s polls do not divide HEARTBEAT_SECS, so counting polls cannot pass
    # for reading the clock: 770s of waiting is eleven polls and two full
    # five-minute periods, and one line per third poll would be three lines.
    assert wave_slots.HEARTBEAT_SECS == 300
    lines = _lines_while_waiting(tmp_path, monkeypatch, capsys, poll=70, until=770)
    assert len(lines) == 2, f"expected one line per 300s of waiting, got {lines}"
    for line in lines:
        assert os.fspath(tmp_path / "wave-slots") in line  # the line names the dir


def test_a_long_wait_keeps_a_line_coming_every_five_minutes(
    tmp_path,
    monkeypatch,
    capsys,
):
    # Thirty-five minutes of waiting is seven five-minute periods and thirty
    # 70s polls. The count of lines has to come from dividing the elapsed
    # clock: a fixed list of the first one or two marks goes quiet here, and
    # so does anything that stops announcing once the wait gets long.
    lines = _lines_while_waiting(tmp_path, monkeypatch, capsys, poll=70, until=2100)
    assert len(lines) == 7, f"expected one line per 300s of waiting, got {lines}"
    for line in lines:
        assert os.fspath(tmp_path / "wave-slots") in line  # each line names the dir


def test_waiting_under_five_minutes_prints_nothing(tmp_path, monkeypatch, capsys):
    # One second short of HEARTBEAT_SECS, polled every second so the clock is
    # read either side of the mark: an interval shorter than 300s would have
    # spoken by now, so this silence is what makes the interval exact instead
    # of merely bounded from above.
    lines = _lines_while_waiting(tmp_path, monkeypatch, capsys, poll=1, until=299)
    assert not lines, f"nothing is due before 300s of waiting, got {len(lines)} lines"


def test_the_first_line_is_due_at_the_five_minute_mark(tmp_path, monkeypatch, capsys):
    # One second past HEARTBEAT_SECS, polled every second: exactly one line,
    # which bounds the interval from below too (a 350s interval would still
    # be silent here, and a 150s one would already be on its second line).
    # 301s rather than 300s so the test stays blind to whether the waiter
    # reads the clock before or after its last sleep; both orders have spoken
    # once by 301s, and an acquirer that stops waiting on the mark itself has
    # nothing left to announce.
    lines = _lines_while_waiting(tmp_path, monkeypatch, capsys, poll=1, until=301)
    assert len(lines) == 1, f"one line is due by 301s of waiting, got {len(lines)}"
    assert os.fspath(tmp_path / "wave-slots") in lines[0]
