from pydantic import BaseModel


class ReencryptSecretsRequest(BaseModel):
    old_key: str
    new_key: str
    dry_run: bool = True


class ReencryptSecretsOut(BaseModel):
    dry_run: bool
    scanned: int
    updated: int
