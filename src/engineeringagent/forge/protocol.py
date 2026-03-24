"""Protocol boundaries for forge adapters."""

from typing import Protocol

from engineeringagent.orchestrators.publication.protocols import PublicationForgePort


class ForgeProtocol(PublicationForgePort, Protocol):
    """Hosting platform operations for publication."""
