import json

from typing import IO, Iterator, Dict, Any
from pymarc import Record, Field, Subfield


class MarcJsonReader:
    '''Class to read multiple newline delimited JSON files
    Combine this class with pymarc's Record class to parse each JSON object into a MARC record.

    '''
    def __init__(self, fh: IO[str]):
        self.fh = fh

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        '''Yields Record objects parsed from the MARC JSON input.'''
        for line in self.fh:
            if not (line := line.strip()):
                continue
            try:
                data = json.loads(line)

            except json.JSONDecodeError:
                continue
            yield data

def dict_to_pymarc_record(data: dict) -> Record:
    """
    Convert a dictionary representation of a MARC record
    into a pymarc Record object.
    """

    record = Record()

    # Set leader
    if 'leader' in data:
        record.leader = data['leader']

    for field_dict in data.get('fields', []):
        # Each field_dict has a single key (tag)
        tag, value = next(iter(field_dict.items()))

        # Control fields (no indicators or subfields)
        if isinstance(value, str):
            record.add_field(Field(tag=tag, data=value))
            continue

        # Data fields
        indicators = [
            value.get('ind1', ' '),
            value.get('ind2', ' ')
        ]

        # Flatten subfields: [{'a': 'x'}, {'b': 'y'}] → ['a', 'x', 'b', 'y']
        subfields = []
        raw_subfields = value.get("subfields", [])
        # Handle multiple possible formats
        if isinstance(raw_subfields, list):
            for sf in raw_subfields:
                # Case 1: dict {'a': 'value'}
                if isinstance(sf, dict):
                    for code, val in sf.items():
                        subfields.append(Subfield(code=str(code), value=str(val)))
                # Case 2: flat list ['a', 'value']
                # TODO: Check if the list could have more that 2 elements.
                elif isinstance(sf, list) and len(sf) == 2:
                    subfields.append(Subfield(code=str(sf[0]), value=str(sf[1])))
                # Case 3: stray string → skip or log
                else:
                    continue

        field = Field(
            tag,
            indicators=indicators,
            subfields=subfields
        )

        record.add_field(field)

    return record