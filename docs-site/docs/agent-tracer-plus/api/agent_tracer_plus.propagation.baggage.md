# Module: `agent_tracer_plus.propagation.baggage`

W3C Baggage propagation.

Carries application-defined key-value pairs across service boundaries.
See: https://www.w3.org/TR/baggage/

## Class `Baggage`
In-memory baggage container (key-value pairs).

### `def __init__(self, entries)`
### `def get(self, key)`
Get a baggage value by key.

### `def set(self, key, value)`
Set a baggage key-value pair.

### `def remove(self, key)`
Remove a baggage entry.

### `def entries(self)`
Get all baggage entries.

### `def __len__(self)`
### `def __repr__(self)`
## Class `BaggagePropagator`
Injects/extracts W3C Baggage headers.

### `def inject(self, baggage, carrier)`
Inject baggage into a carrier (e.g. HTTP headers).

### `def extract(self, carrier)`
Extract baggage from a carrier (e.g. HTTP headers).

## Function `inject_baggage(baggage, headers)`
Inject W3C Baggage into headers.

## Function `extract_baggage(headers)`
Extract W3C Baggage from headers.

