"""CLI commands for data export."""

import argparse
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


async def export_traces_async(backend_uri: str, format: str, output: str, limit: int = 1000) -> None:
    """Async implementation of export traces fetching from real backend."""
    print(f"Exporting up to {limit} traces from {backend_uri} to {output} in {format} format...")

    from agent_tracer_plus.core.tracer import AgentTracerPlus
    storage = AgentTracerPlus._storage_from_uri(backend_uri)

    chunk_size = min(100, limit)
    fetched = 0
    offset = 0

    if format == "jsonl":
        with open(output, "w") as f:
            while fetched < limit:
                traces = await storage.query_traces(limit=chunk_size, offset=offset)
                if not traces:
                    break
                for trace in traces:
                    f.write(json.dumps(trace) + "\n")
                    fetched += 1
                    if fetched >= limit:
                        break
                offset += chunk_size
    elif format == "csv":
        with open(output, "w") as f:
            header_written = False
            while fetched < limit:
                traces = await storage.query_traces(limit=chunk_size, offset=offset)
                if not traces:
                    break
                for trace in traces:
                    if not header_written:
                        f.write(",".join(trace.keys()) + "\n")
                        header_written = True
                    f.write(",".join(str(v) for v in trace.values()) + "\n")
                    fetched += 1
                    if fetched >= limit:
                        break
                offset += chunk_size
    elif format == "parquet":
        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            logger.error("pandas and pyarrow required for parquet export. Run `pip install pandas pyarrow`")
            return

        writer = None
        
        while fetched < limit:
            traces = await storage.query_traces(limit=chunk_size, offset=offset)
            if not traces:
                break
                
            df = pd.DataFrame(traces)
            table = pa.Table.from_pandas(df)
            
            if writer is None:
                # Initialize writer with schema from the first chunk
                writer = pq.ParquetWriter(output, table.schema)
                
            writer.write_table(table)
            
            fetched += len(traces)
            offset += chunk_size
            
            if fetched >= limit:
                break
                
        if writer:
            writer.close()

    else:
        logger.error(f"Unsupported export format: {format}")
        return

    print(f"Export complete. Total traces exported: {fetched}")


def export_traces(backend_uri: str, format: str, output: str, limit: int = 1000):
    """Sync wrapper for export traces."""
    asyncio.run(export_traces_async(backend_uri, format, output, limit))


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the export CLI command."""
    parser = subparsers.add_parser("export", help="Export traces to a file")
    parser.add_argument("--backend", type=str, default="sqlite://./agent_traces.db", help="Storage backend URI")
    parser.add_argument("--format", type=str, choices=["jsonl", "csv", "parquet"], default="jsonl", help="Export format")
    parser.add_argument("--output", type=str, required=True, help="Output file path")
    parser.add_argument("--limit", type=int, default=1000, help="Max number of traces to export")
    parser.set_defaults(func=lambda args: export_traces(args.backend, args.format, args.output, args.limit))
