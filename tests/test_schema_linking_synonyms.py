import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nl2sql.schema_linking import schema_link


def test_synonym_singer():
    r = schema_link("哪个唱歌的人专辑最多")
    assert "Artist" in r["related_tables"]
    assert "Album" in r["related_tables"]


def test_typo_singer():
    r = schema_link("哪个哥手专辑最多")
    assert "Artist" in r["related_tables"]
    assert "Album" in r["related_tables"]
