"""JOIN 语义校验 validate_join_path 的离线测试（无需 API）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.join_validator import validate_join_path


def test_cartesian_product_comma_rejected():
    r = validate_join_path("SELECT * FROM Customer, Invoice")
    assert not r["valid"]
    assert "笛卡尔积" in r["message"]


def test_wrong_join_key_rejected():
    sql = (
        "SELECT * FROM Customer JOIN Invoice "
        "ON Customer.City = Invoice.InvoiceDate"
    )
    r = validate_join_path(sql)
    assert not r["valid"]
    assert "关联键错误" in r["message"]


def test_comma_with_only_filter_rejected():
    sql = (
        "SELECT * FROM Customer, Invoice "
        "WHERE Customer.Country='USA'"
    )
    r = validate_join_path(sql)
    assert not r["valid"]


def test_correct_inner_join():
    sql = (
        "SELECT * FROM Customer JOIN Invoice "
        "ON Customer.CustomerId = Invoice.CustomerId"
    )
    assert validate_join_path(sql)["valid"]


def test_reversed_join_columns():
    sql = (
        "SELECT * FROM Customer JOIN Invoice "
        "ON Invoice.CustomerId = Customer.CustomerId"
    )
    assert validate_join_path(sql)["valid"]


def test_correct_left_join():
    sql = (
        "SELECT c.FirstName, i.Total FROM Customer c "
        "LEFT JOIN Invoice i ON c.CustomerId = i.CustomerId"
    )
    assert validate_join_path(sql)["valid"]


def test_join_with_table_aliases():
    sql = (
        "SELECT * FROM Customer c JOIN Invoice i "
        "ON c.CustomerId = i.CustomerId"
    )
    assert validate_join_path(sql)["valid"]


def test_multi_hop_join():
    sql = (
        "SELECT * FROM Customer "
        "JOIN Invoice ON Customer.CustomerId=Invoice.CustomerId "
        "JOIN InvoiceLine ON Invoice.InvoiceId=InvoiceLine.InvoiceId"
    )
    assert validate_join_path(sql)["valid"]


def test_album_artist_join():
    sql = (
        "SELECT * FROM Album JOIN Artist "
        "ON Album.ArtistId=Artist.ArtistId"
    )
    assert validate_join_path(sql)["valid"]


def test_track_invoiceline_join():
    sql = (
        "SELECT * FROM Track JOIN InvoiceLine "
        "ON Track.TrackId=InvoiceLine.TrackId"
    )
    assert validate_join_path(sql)["valid"]


def test_implicit_join_in_where_accepted():
    sql = (
        "SELECT * FROM Customer, Invoice "
        "WHERE Customer.CustomerId=Invoice.CustomerId"
    )
    assert validate_join_path(sql)["valid"]


def test_single_table_passes():
    assert validate_join_path("SELECT * FROM Customer")["valid"]


def test_subquery_passes():
    sql = (
        "SELECT MAX(q) FROM "
        "(SELECT SUM(Quantity) AS q FROM InvoiceLine GROUP BY TrackId)"
    )
    assert validate_join_path(sql)["valid"]
