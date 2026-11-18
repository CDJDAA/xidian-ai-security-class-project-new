from pipeline.analysis_service import _read_rows


def test_csv_limit_stops_before_malformed_tail(tmp_path):
    path = tmp_path / "large.csv"
    # The unneeded tail exceeds csv's field size limit. Reading it would fail.
    path.write_text('title,text\nfirst,"quoted, content"\n' + 'x' * 200000, encoding="utf-8-sig")
    assert _read_rows(path, 1) == [{"title": "first", "text": "quoted, content"}]


def test_nonpositive_limit_never_opens_input(tmp_path):
    assert _read_rows(tmp_path / "missing.csv", 0) == []
    assert _read_rows(tmp_path / "missing.csv", -1) == []
