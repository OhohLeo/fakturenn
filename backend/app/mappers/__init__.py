"""Mapper implementations for transforming Records to export format.

Mappers apply transformation rules to Records and send them to Exporters:
- Record2Paheko: Transform Record → Paheko accounting transaction
- Record2GDrive: Transform Record → Google Drive file upload
"""

from app.mappers.base import BaseMapper, MapperError

__all__ = [
    "BaseMapper",
    "MapperError",
]
