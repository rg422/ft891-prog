"""End-to-end tests of the CAT + radio layers against the built-in simulator."""

import threading

import pytest

from ft891prog.cat import CatConnection, CatRejected, CatTimeout, SerialOptions, probe_baud
from ft891prog.memory import ALL_CHANNELS, MemoryChannel
from ft891prog.menu_defs import CAT_RATE, MENU_BY_NUMBER, MENU_ITEMS
from ft891prog.radio import FT891, OperationCancelled
from ft891prog.simulator import RadioState, SimulatedRadio


@pytest.fixture
def state():
    return RadioState()


@pytest.fixture
def radio(state):
    cat = CatConnection(SimulatedRadio(4800, state=state), timeout=0.5)
    r = FT891(cat)
    assert r.identify() == "0650"
    r.prepare()
    return r


def test_read_all_menus(radio):
    values, problems = radio.read_menus(MENU_ITEMS)
    assert problems == []
    assert len(values) == len(MENU_ITEMS)
    assert values["0101"] == 300
    assert values["1202"] == -15


def test_write_menu_and_verify(radio, state):
    item = MENU_BY_NUMBER["0803"]
    radio.write_menu(item, -1230)
    assert state.menu["0803"] == "-1230"


def test_write_menus_reports_failures(radio, state):
    # 18-01 is read only in the simulator -> rejected by write_menu validation
    results = radio.write_menus([(MENU_BY_NUMBER["1601"], 42), (MENU_BY_NUMBER["0201"], 99)])
    assert results[0].ok
    assert not results[1].ok  # 99 is outside 1..15
    assert state.menu["1601"] == "042"


def test_cat_rate_change_reconnects(radio, state):
    results = radio.write_menus([(MENU_BY_NUMBER[CAT_RATE], 3), (MENU_BY_NUMBER["0504"], 77)])
    assert all(r.ok for r in results)
    assert results[-1].key == CAT_RATE  # always written last
    assert radio.cat.baudrate == 38400
    assert state.cat_baud == 38400
    assert radio.read_menu(MENU_BY_NUMBER["0504"]) == 77


def test_read_memories(radio):
    data, problems = radio.read_memories(ALL_CHANNELS)
    assert problems == []
    assert data["001"].tag == "FT8 40M"
    assert data["003"].tag == ""
    assert data["050"] is None
    assert data["501"].freq_hz == 5_330_500
    assert radio.tag_read_supported is True


def test_write_memories_with_tag(radio, state):
    mems = [
        MemoryChannel("050", 50_313_000, "DATA-U", tag="FT8 6M", tag_on=True),
        MemoryChannel("P2L", 3_500_000, "CW-L", clar_on=True, clar_offset_hz=-50),
    ]
    results = radio.write_memories(mems)
    assert all(r.ok for r in results), results
    assert state.memories["050"].tag == "FT8 6M"
    assert state.memories["P2L"].clar_offset_hz == -50


def test_radio_without_tag_read_support(state):
    state.mt_read_supported = False
    r = FT891(CatConnection(SimulatedRadio(4800, state=state), timeout=0.3))
    data, _ = r.read_memories(["001", "002"])
    assert r.tag_read_supported is False
    assert data["001"].tag == ""
    # Without a tag, MW is used so an existing tag on the radio is preserved.
    r.write_memory(MemoryChannel("001", 7_075_000, "DATA-U"))
    assert state.memories["001"].tag == "FT8 40M"
    assert state.memories["001"].freq_hz == 7_075_000


def test_readonly_channel_write_is_refused(radio):
    results = radio.write_memories([MemoryChannel("501", 5_330_500, "USB")])
    assert not results[0].ok


def test_rejected_and_timeout(state):
    cat = CatConnection(SimulatedRadio(4800, state=state), timeout=0.2)
    with pytest.raises(CatRejected):
        cat.query("ZZ;")
    cat_wrong_baud = CatConnection(SimulatedRadio(9600, state=state), timeout=0.2)
    with pytest.raises(CatTimeout):
        cat_wrong_baud.query("ID;")


def test_probe_baud(monkeypatch, state):
    import ft891prog.simulator as sim

    monkeypatch.setattr(sim, "_shared_state", state)
    state.menu[CAT_RATE] = "2"  # radio set to 19200
    assert probe_baud(SerialOptions("SIMULATOR", 4800)) == (19200, "0650")


def test_cancel(radio):
    ev = threading.Event()
    ev.set()
    with pytest.raises(OperationCancelled):
        radio.read_menus(MENU_ITEMS, cancel=ev)
