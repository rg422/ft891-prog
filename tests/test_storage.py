from ft891prog.memory import MemoryChannel
from ft891prog.model import MemoryModel, SettingsModel
from ft891prog.storage import export_csv, import_csv, load_profile, save_profile


def test_profile_round_trip(tmp_path):
    s = SettingsModel()
    s.load_defaults()
    s.set("0513", -7)
    m = MemoryModel()
    m.set("001", MemoryChannel("001", 7_074_000, "DATA-U", tag="FT8", tag_on=True))
    m.set("P1U", MemoryChannel("P1U", 7_300_000, "LSB", clar_on=True, clar_offset_hz=-30))
    path = tmp_path / "radio.json"
    save_profile(path, s, m, {"id": "0650"})

    s2, m2 = SettingsModel(), MemoryModel()
    warnings = load_profile(path, s2, m2)
    assert warnings == []
    assert s2.values["0513"] == -7
    assert s2.values["0101"] == 300
    assert m2.get("001") == m.get("001")
    assert m2.get("P1U") == m.get("P1U")
    # Nothing is known about the radio after loading a file, so everything is "to write".
    assert len(m2.changed_channels()) == 2
    assert len(s2.changed_items()) == len(s.all_items())


def test_csv_round_trip(tmp_path):
    m = MemoryModel()
    m.set("010", MemoryChannel("010", 29_620_000, "FM", ctcss="ENC", shift="MINUS", tag="10M RPT"))
    m.set("002", MemoryChannel("002", 14_074_000, "DATA-U", tag="FT8 20M", tag_on=True))
    path = tmp_path / "mem.csv"
    assert export_csv(path, m) == 2
    channels, warnings = import_csv(path)
    assert warnings == []
    assert channels["010"] == m.get("010")
    assert channels["002"] == m.get("002")


def test_csv_import_is_lenient_and_reports_bad_rows(tmp_path):
    path = tmp_path / "in.csv"
    path.write_text(
        "Channel,Frequency,Mode,Tag\n"
        "1,7.074,data-u,FT8\n"
        "P2L,3500 kHz,CW-L,\n"
        "3,144.2,USB,out of range\n"
        "4,14.2,XYZ,bad mode\n",
        encoding="utf-8",
    )
    channels, warnings = import_csv(path)
    assert set(channels) == {"001", "P2L"}
    assert channels["P2L"].freq_hz == 3_500_000
    assert len(warnings) == 2


def test_model_compare_mode():
    m = MemoryModel()
    mine = MemoryChannel("001", 7_074_000, "USB")
    m.set("001", mine)
    radio_data = {"001": MemoryChannel("001", 7_100_000, "USB"), "002": MemoryChannel("002", 1_000_000, "AM")}
    m.apply_radio(radio_data, keep_edits=True)
    assert m.get("001") == mine           # my edit kept
    assert m.status("001") == "modified"
    assert m.get("002") is None           # empty in my profile...
    assert m.status("002") == "cleared"   # ...but present on the radio
    assert [c.channel for c in m.changed_channels()] == ["001"]


def test_settings_compare_mode():
    s = SettingsModel()
    s.set("1601", 50)
    s.apply_radio({"1601": 100, "1602": 25}, keep_edits=True)
    assert s.values["1601"] == 50
    assert s.values["1602"] == 25
    assert [i.number for i, _ in s.changed_items()] == ["1601"]
