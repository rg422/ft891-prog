import pytest

from ft891prog.menu_defs import CAT_RATE, MENU_BY_NUMBER, MENU_ITEMS, WRITABLE_ITEMS


def test_menu_numbers_unique_and_ordered():
    numbers = [i.number for i in MENU_ITEMS]
    assert len(numbers) == len(set(numbers))
    assert numbers == sorted(numbers)


def test_reset_menu_is_never_exposed():
    # 17-01 RESET would wipe the radio; it must not be in the table at all.
    assert "1701" not in MENU_BY_NUMBER


def test_every_default_is_legal_and_round_trips():
    for item in WRITABLE_ITEMS:
        assert item.default is not None, item.label
        assert item.is_valid(item.default), item.label
        p2 = item.encode(item.default)
        assert len(p2) == item.digits, item.label
        assert item.decode(p2) == item.default
        assert item.parse_display(item.display(item.default)) == item.default, item.label


def test_every_legal_value_fits_its_width():
    for item in WRITABLE_ITEMS:
        for raw in item.legal_values():
            assert len(item.encode(raw)) == item.digits, (item.label, raw)


@pytest.mark.parametrize("number,raw,p2", [
    ("0513", -5, "-05"),
    ("0513", 20, "+20"),
    ("0513", 0, "+00"),
    ("0803", -3000, "-3000"),
    ("0803", 1250, "+1250"),
    ("1202", -15, "-15"),
    ("0101", 300, "0300"),
    ("0403", 30, "30"),
    ("0905", 1000, "1000"),
    ("0601", 0, "00"),
    ("1302", 4, "04"),
    ("1601", 5, "005"),
])
def test_encode(number, raw, p2):
    assert MENU_BY_NUMBER[number].encode(raw) == p2


def test_encode_uses_radio_width_when_given():
    assert MENU_BY_NUMBER["0905"].encode(250, width=4) == "0250"


def test_decode_negative_zero():
    assert MENU_BY_NUMBER["0513"].decode("-00") == 0


@pytest.mark.parametrize("number,raw,text", [
    ("0403", 25, "2.5"),
    ("0601", 1, "100 Hz"),
    ("0601", 19, "1000 Hz"),
    ("0603", 1, "700 Hz"),
    ("0603", 67, "4000 Hz"),
    ("1504", 9, "1500 Hz"),
    ("1507", 18, "3200 Hz"),
    ("0404", 0, "OFF"),
    ("0514", 0, "OFF"),
    ("0514", 10, "10 min"),
    ("0513", 5, "+5 kHz"),
    ("0710", 2, "4 msec"),
])
def test_display(number, raw, text):
    assert MENU_BY_NUMBER[number].display(raw) == text


def test_parse_display_accepts_numbers_and_rejects_out_of_range():
    agc = MENU_BY_NUMBER["0101"]
    assert agc.parse_display("320") == 320
    assert agc.parse_display("320 msec") == 320
    with pytest.raises(ValueError):
        agc.parse_display("310")    # not on the 20 ms step
    with pytest.raises(ValueError):
        agc.parse_display("5000")
    weight = MENU_BY_NUMBER["0403"]
    assert weight.parse_display("3.7") == 37


def test_beacon_interval_steps():
    beacon = MENU_BY_NUMBER["0404"]
    assert beacon.is_valid(240)
    assert not beacon.is_valid(250)
    assert beacon.is_valid(270)
    assert beacon.is_valid(690)
    assert not beacon.is_valid(700)


def test_every_menu_item_has_help_text():
    from ft891prog.menu_help import MENU_HELP

    assert set(MENU_HELP) == set(MENU_BY_NUMBER)
    for number, text in MENU_HELP.items():
        assert len(text) >= 40, number
        assert "  " not in text, number          # no doubled spaces from string joins
        assert text.rstrip()[-1] in ".)", number  # complete sentences


def test_cat_rate_item():
    item = MENU_BY_NUMBER[CAT_RATE]
    assert item.display(3) == "38400 bps"
