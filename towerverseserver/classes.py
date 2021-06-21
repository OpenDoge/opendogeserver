from dataclasses import dataclass

def check(items: dict):
    for item, type in items:
        assert isinstance(item, type)

@dataclass(frozen=True)
class Tower():
    """The base `Tower` instance. """
    tower_id: str
    tower_name: str
    tower_creator: str
    tower_visibility: bool = True

@dataclass(frozen=True)
class Traveller():
    """The base `Traveller` instance. """
    traveller_id: str
    traveller_name: str
    traveller_email: str
    traveller_password: str

@dataclass(frozen=True)
class TempTraveller(Traveller):
    """The base `TempTraveller` instance, used for a temporary account before verification. """
    traveller_code: str
