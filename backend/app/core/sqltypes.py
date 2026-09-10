"""Portable column types for MySQL/MariaDB and SQLite."""

from sqlalchemy import JSON, Text
from sqlalchemy.dialects.mysql import LONGTEXT

# MySQL JSON / SQLite TEXT. Do not import dialects.mysql.JSON.
PortableJSON = JSON

# MySQL LONGTEXT (boxes / raw dumps); SQLite TEXT.
LongText = Text().with_variant(LONGTEXT, "mysql")
