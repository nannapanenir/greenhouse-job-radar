"""Base model: snake_case in Python, camelCase on the wire (matches the
Resume Tailor / Job Radar JSON contracts)."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    def dump(self) -> dict:
        return self.model_dump(by_alias=True)
