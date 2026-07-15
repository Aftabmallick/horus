FROM rust:slim as builder

WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*
COPY . .

RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libssl3 ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/app/target/release/agent-tracer-proxy /usr/local/bin/

ENV RUST_LOG=info
EXPOSE 3001

CMD ["agent-tracer-proxy"]
