"""Phase 8: CSV export content and error-handling tests.

Verifies the fixed, documented column schema with consistent units (V, A, W,
Wh) and ISO-8601 timestamps; that exported records match the selected data and
filters; and that empty datasets, invalid paths, and file permission errors
are handled honestly.
"""

from __future__ import annotations

import os
import stat

import pytest
from PySide6.QtWidgets import QApplication

from solar_monitor.core.measurement import Measurement
from solar_monitor.core.validation import validate_reading
from solar_monitor.database.connection import open_db
from solar_monitor.database.dao import create_session, insert_measurement, list_measurements
from solar_monitor.services.csv_export import CSV_COLUMNS, export_measurements


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


def _make_conn(tmp_path):
    db_path = os.path.join(str(tmp_path), "csv.db")
    return open_db(db_path), db_path


def _insert_readings(conn, sid, base, count=5, spacing_s=3600):
    from datetime import datetime, timedelta
    base_dt = datetime.fromisoformat(base)
    for i in range(count):
        ts = base_dt + timedelta(seconds=spacing_s * i)
        m = validate_reading(
            5.0 + i * 0.1, 0.1 + i * 0.01, 0.5 + i * 0.05,
            mode="simulated", status="ok",
        )
        m = Measurement(
            timestamp=ts.isoformat(),
            voltage_v=m.voltage_v, current_ma=m.current_ma, current_a=m.current_a,
            power_w=m.power_w, sensor_mode=m.sensor_mode, sensor_status=m.sensor_status,
        )
        insert_measurement(conn, sid, m,
                           energy_increment_wh=0.001 * i,
                           daily_energy_wh=0.001 * i,
                           total_energy_wh=0.001 * i)


def _read_csv(path):
    with open(path, encoding="utf-8-sig") as fh:
        lines = fh.read().strip().splitlines()
    return [line.split(",") for line in lines]


def test_csv_content_matches_measurements(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="csv", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-07-01T08:00:00+00:00", count=3, spacing_s=3600)

    rows = list(list_measurements(conn, limit=1000))
    out = os.path.join(str(tmp_path), "out.csv")
    n = export_measurements(out, rows)
    assert n == 3

    lines = _read_csv(out)
    assert lines[0] == CSV_COLUMNS
    assert len(lines) == 4  # header + 3 records

    # Verify first record values (newest first due to ORDER BY timestamp DESC).
    first = lines[1]
    assert first[0] == "2026-07-01T10:00:00+00:00"  # newest record, ISO-8601 UTC
    assert first[1] == str(sid)  # session_id
    assert first[2] == "simulated"  # sensor_mode
    assert first[3] == "ok"  # sensor_status
    assert abs(float(first[4]) - 5.2) < 1e-6  # voltage_v (index 2: 5.0 + 2*0.1)
    assert abs(float(first[5]) - 0.12) < 1e-6  # current_a (index 2: 0.1 + 2*0.01)
    assert abs(float(first[6]) - 0.6) < 1e-6  # power_w = V x I (5.2 * 0.12 = 0.624... wait)
    # Actually power_register_w = 0.5 + 2*0.05 = 0.6, and V*I = 5.2*0.12 = 0.624
    # compute_power uses register if consistent: |0.6 - 0.624| = 0.024 <= 0.10*0.624 = 0.0624, so uses register 0.6
    assert abs(float(first[6]) - 0.6) < 1e-6
    assert abs(float(first[9]) - 0.002) < 1e-9  # total_energy_wh (index 2: 0.001*2)
    conn.close()


def test_csv_empty_dataset_raises_valueerror(tmp_path):
    out = os.path.join(str(tmp_path), "empty.csv")
    with pytest.raises(ValueError, match="No measurements"):
        export_measurements(out, [])


def test_csv_invalid_path_raises_oserror(tmp_path):
    # A path with an invalid filename character cannot be created.
    out = os.path.join(str(tmp_path), "inva<lid.csv")
    with pytest.raises(OSError):
        export_measurements(out, [object()])


def test_csv_export_matches_start_filter(tmp_path):
    """Exported records match the start filter: only records on/after the
    start timestamp appear in the CSV."""
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="filter", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-08-01T08:00:00+00:00", count=5, spacing_s=3600)

    # Filter: only records from 10:00 onward (indices 2,3,4).
    rows = list(list_measurements(
        conn, start="2026-08-01T10:00:00+00:00", limit=1000
    ))
    assert len(rows) == 3
    out = os.path.join(str(tmp_path), "filtered.csv")
    n = export_measurements(out, rows)
    assert n == 3

    lines = _read_csv(out)
    assert len(lines) == 4  # header + 3
    # Newest first: lines[1] is 12:00, lines[2] is 11:00, lines[3] is 10:00.
    assert all(r[0] >= "2026-08-01T10:00:00+00:00" for r in lines[1:])
    assert lines[1][0] == "2026-08-01T12:00:00+00:00"
    assert lines[3][0] == "2026-08-01T10:00:00+00:00"
    conn.close()


def test_csv_export_matches_end_filter(tmp_path):
    """Exported records match the end filter: only records on/before the end
    timestamp appear in the CSV."""
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="end", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-08-01T08:00:00+00:00", count=5, spacing_s=3600)

    rows = list(list_measurements(
        conn, end="2026-08-01T10:00:00+00:00", limit=1000
    ))
    assert len(rows) == 3
    out = os.path.join(str(tmp_path), "filtered_end.csv")
    n = export_measurements(out, rows)
    assert n == 3

    lines = _read_csv(out)
    assert len(lines) == 4
    assert all(r[0] <= "2026-08-01T10:00:00+00:00" for r in lines[1:])
    conn.close()


def test_csv_export_creates_parent_directory(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="dir", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-09-01T08:00:00+00:00", count=1, spacing_s=3600)
    rows = list(list_measurements(conn, limit=1000))

    out = os.path.join(str(tmp_path), "sub", "deep", "out.csv")
    n = export_measurements(out, rows)
    assert n == 1
    assert os.path.exists(out)
    conn.close()


def test_csv_permission_error_on_readonly_dir(tmp_path):
    if os.name == "nt":
        pytest.skip("Permission model differs on Windows; covered by invalid-path test.")
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="ro", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-10-01T08:00:00+00:00", count=1, spacing_s=3600)
    rows = list(list_measurements(conn, limit=1000))

    ro_dir = os.path.join(str(tmp_path), "readonly")
    os.makedirs(ro_dir)
    os.chmod(ro_dir, stat.S_IRUSR | stat.S_IXUSR)  # read+execute only, no write
    out = os.path.join(ro_dir, "out.csv")
    try:
        with pytest.raises((OSError, PermissionError)):
            export_measurements(out, rows)
    finally:
        os.chmod(ro_dir, stat.S_IRWXU)
        conn.close()


def test_csv_utf8_bom_encoding(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="bom", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-11-01T08:00:00+00:00", count=1, spacing_s=3600)
    rows = list(list_measurements(conn, limit=1000))

    out = os.path.join(str(tmp_path), "bom.csv")
    export_measurements(out, rows)
    with open(out, "rb") as fh:
        raw = fh.read(3)
    assert raw == b"\xef\xbb\xbf"  # UTF-8 BOM
    conn.close()
