"""
Sentinel Cursor Pagination.

Uses cursor-based pagination instead of page/offset pagination.

Why cursor pagination:
- OFFSET-based pagination degrades as the offset grows (the DB must scan and skip N rows)
- The audit log will have millions of rows — OFFSET 1000000 is unacceptable
- Cursors are stable across inserts/deletes (OFFSET-based pagination can skip or repeat rows)
- Cursors scale to arbitrarily large datasets at constant query cost

The cursor encodes the `created_at` timestamp and `id` of the last seen record.
This produces a stable, efficient WHERE clause:
    WHERE (created_at, id) < (cursor_created_at, cursor_id)

Clients receive `next` and `previous` URLs in the response.
"""

from __future__ import annotations

from rest_framework.pagination import CursorPagination as DRFCursorPagination
from rest_framework.response import Response


class CursorPagination(DRFCursorPagination):
    """Default cursor pagination for Sentinel list endpoints."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = "-created_at"

    def get_paginated_response(self, data: list[object]) -> Response:
        return Response(
            {
                "pagination": {
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    "page_size": self.page_size,
                },
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema: dict[str, object]) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "pagination": {
                    "type": "object",
                    "properties": {
                        "next": {"type": "string", "nullable": True},
                        "previous": {"type": "string", "nullable": True},
                        "page_size": {"type": "integer"},
                    },
                },
                "results": schema,
            },
        }
