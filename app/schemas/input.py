"""Input schemas for the REITool API."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict
from pydantic.types import StringConstraints

StrippedNonEmpty = Annotated[
    str, StringConstraints(min_length=1, strip_whitespace=True)
]


class AddressInput(BaseModel):
    """Validated address input from the API consumer."""

    model_config = ConfigDict(populate_by_name=True)

    address: StrippedNonEmpty
