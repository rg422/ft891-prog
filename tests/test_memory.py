import pytest

from ft891prog.memory import (
    ALL_CHANNELS,
    MemoryChannel,
    channel_from_label,
    channel_label,
    format_answer,
    format_freq,
    format_mt,
    format_mw,
    parse_freq,
    parse_memory_answer,
)


def test_parse_mr_answer_layout():
    # MR + ch + 9-digit freq + clar(+0000) + P4 P5 P6 P7 P8 + 00 + P10  = 28 chars incl ';'
    # P4=1 (clar on) P5=0 P6=2 (USB) P7=1 P8=1 (ENC/DEC) P9=00 P10=2 (minus)
    ans = "MR001014250000-0120" + "1021" + "1" + "00" + "2" + ";"
    assert len(ans) == 28
    m = parse_memory_answer(ans)
    assert m.channel == "001"
    assert m.freq_hz == 14_250_000
    assert m.clar_offset_hz == -120
    assert m.clar_on is True
    assert m.mode == "USB"
    assert m.ctcss == "ENC/DEC"
    assert m.shift == "MINUS"


def test_parse_mt_answer_with_tag():
    # P4=0 P5=0 P6=8 (DATA-L) P7=1 P8=0 P9=00 P10=0 P11=1 (show tag) P12=12 chars
    ans = "MTP1L007074000+0000" + "0081" + "0" + "00" + "0" + "1" + "FT8 40M     " + ";"
    assert len(ans) == 41
    m = parse_memory_answer(ans)
    assert m.channel == "P1L"
    assert m.mode == "DATA-L"
    assert m.tag == "FT8 40M"
    assert m.tag_on is True


def test_format_mw_and_mt():
    m = MemoryChannel("012", 7_200_000, "LSB", clar_on=False, clar_offset_hz=250,
                      ctcss="OFF", shift="SIMPLEX", tag="NET", tag_on=True)
    assert format_mw(m) == "MW012007200000+025000100000;"
    mt = format_mt(m)
    assert mt == "MT012007200000+0250" + "00100000" + "1" + "NET         " + ";"
    assert len(mt) == 41


def test_round_trip_through_answers():
    for mode in ("LSB", "USB", "CW-U", "CW-L", "AM", "AM-N", "FM", "FM-N",
                 "RTTY-L", "RTTY-U", "DATA-L", "DATA-U"):
        m = MemoryChannel("P9U", 50_313_000, mode, clar_on=True, clar_offset_hz=-9999,
                          ctcss="ENC", shift="PLUS", tag="a~z!", tag_on=True)
        assert parse_memory_answer(format_answer(m, "MT")).same_radio_data(m)
        assert parse_memory_answer(format_answer(m, "MR")).same_radio_data(m, compare_tag=False)


def test_readonly_channels_cannot_be_written():
    with pytest.raises(ValueError):
        format_mw(MemoryChannel("501", 5_330_500, "USB"))
    with pytest.raises(ValueError):
        format_mt(MemoryChannel("EMG", 5_167_500, "USB"))


@pytest.mark.parametrize("bad", [
    MemoryChannel("001", 20_000, "USB"),
    MemoryChannel("001", 60_000_000, "USB"),
    MemoryChannel("001", 7_000_000, "USB", clar_offset_hz=10_000),
    MemoryChannel("001", 7_000_000, "USB", tag="x" * 13),
    MemoryChannel("001", 7_000_000, "USB", tag="semi;colon"),
])
def test_validation(bad):
    assert bad.validate()
    with pytest.raises(ValueError):
        format_mt(bad)


@pytest.mark.parametrize("text,hz", [
    ("14.250", 14_250_000),
    ("14.250.000", 14_250_000),
    ("7.0745", 7_074_500),
    ("7074.5 kHz", 7_074_500),
    ("7074", 7_074_000),
    ("14250000", 14_250_000),
    ("28", 28_000_000),
    ("0.530", 530_000),
])
def test_parse_freq(text, hz):
    assert parse_freq(text) == hz


def test_parse_freq_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_freq("144.200")


def test_format_freq():
    assert format_freq(7_074_000) == "7.074000"
    assert format_freq(530_000) == "0.530000"


def test_channel_labels_round_trip():
    for ch in ALL_CHANNELS:
        assert channel_from_label(channel_label(ch)) == ch
    assert channel_from_label("5") == "005"
    assert channel_from_label("p3u") == "P3U"
    assert len(ALL_CHANNELS) == 99 + 18 + 10 + 1
