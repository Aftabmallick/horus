# Module: `agent_tracer_plus.storage.telemetry_pb2_grpc`

Client and server classes corresponding to protobuf-defined services.

## Class `IngestionServiceStub`
Missing associated documentation comment in .proto file.

### `def __init__(self, channel)`
Constructor.

Args:
    channel: A grpc.Channel.

## Class `IngestionServiceServicer`
Missing associated documentation comment in .proto file.

### `def IngestTrace(self, request, context)`
Missing associated documentation comment in .proto file.

### `def IngestSpan(self, request, context)`
Missing associated documentation comment in .proto file.

## Function `add_IngestionServiceServicer_to_server(servicer, server)`
## Class `IngestionService`
Missing associated documentation comment in .proto file.

### `def IngestTrace(request, target, options, channel_credentials, call_credentials, insecure, compression, wait_for_ready, timeout, metadata)`
### `def IngestSpan(request, target, options, channel_credentials, call_credentials, insecure, compression, wait_for_ready, timeout, metadata)`
