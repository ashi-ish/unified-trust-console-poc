"""
Services Package
================

Business logic layer for the Unified Trust Console.

Services follow the Service Layer pattern:
- Encapsulate business logic
- Coordinate between models and APIs
- Handle transactions and complex operations
- Keep controllers thin (just routing)

Available services:
- QueueingService: Queueing theory calculations for load-based protection
"""

from utc.services.queueing import QueueingService, get_queueing_service

__all__ = [
    "QueueingService",
    "get_queueing_service",
]
