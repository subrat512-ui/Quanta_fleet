"""Idempotent MongoDB ingestion for processed vessel telemetry."""

import argparse
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReplaceOne
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from greenfleet.logging.logger import logger
from greenfleet.pipeline.etl.extract import extract_data


@dataclass(frozen=True)
class MongoLoadResult:
    database: str
    collection: str
    source_rows: int
    inserted: int
    updated: int

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def _to_bson_value(value: Any) -> Any:
    """Convert pandas/numpy values to BSON-safe Python values."""
    if value is None or value is pd.NA or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def dataframe_to_documents(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to MongoDB-compatible documents."""
    return [
        {str(key): _to_bson_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _batches(records: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(records), size):
        yield records[start : start + size]


def load_dataframe_to_mongodb(
    frame: pd.DataFrame,
    *,
    uri: str | None = None,
    database: str | None = None,
    collection: str | None = None,
    key_field: str = "record_id",
    batch_size: int = 1_000,
) -> MongoLoadResult:
    """Upsert telemetry rows into MongoDB in batches.

    A unique index on ``key_field`` protects against duplicate observations;
    repeated loads replace existing documents instead of inserting duplicates.
    """
    if frame.empty:
        raise ValueError("Cannot load an empty DataFrame into MongoDB")
    if key_field not in frame.columns:
        raise ValueError(f"MongoDB key field is missing from data: {key_field}")
    if frame[key_field].isna().any() or frame[key_field].duplicated().any():
        raise ValueError(f"MongoDB key field must be non-null and unique: {key_field}")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    load_dotenv()
    mongo_uri = uri or os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise ValueError("Set MONGODB_URI or pass uri= to load data into MongoDB")
    database_name = database or os.getenv("MONGODB_DATABASE", "greenfleet")
    collection_name = collection or os.getenv("MONGODB_COLLECTION", "vessel_telemetry")
    records = dataframe_to_documents(frame)

    try:
        with MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000) as client:
            client.admin.command("ping")
            target: Collection = client[database_name][collection_name]
            target.create_index([(key_field, ASCENDING)], unique=True, name=f"unique_{key_field}")

            inserted = updated = 0
            for batch in _batches(records, batch_size):
                operations = [ReplaceOne({key_field: row[key_field]}, row, upsert=True) for row in batch]
                outcome = target.bulk_write(operations, ordered=False)
                inserted += outcome.upserted_count
                updated += outcome.modified_count
    except PyMongoError as exc:
        logger.exception("MongoDB load failed for %s.%s", database_name, collection_name)
        raise RuntimeError("MongoDB load failed; verify MONGODB_URI and database access") from exc

    result = MongoLoadResult(
        database=database_name,
        collection=collection_name,
        source_rows=len(records),
        inserted=inserted,
        updated=updated,
    )
    logger.info("MongoDB load completed: %s", result.to_dict())
    return result


def load_dataset_to_mongodb(
    source_path: str | Path,
    **options: Any,
) -> MongoLoadResult:
    """Read a processed CSV dataset and load it into MongoDB."""
    return load_dataframe_to_mongodb(extract_data(source_path), **options)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load GreenFleet telemetry into MongoDB.")
    parser.add_argument("source", help="Processed CSV dataset")
    parser.add_argument("--database", help="MongoDB database; defaults to MONGODB_DATABASE or greenfleet")
    parser.add_argument("--collection", help="MongoDB collection; defaults to MONGODB_COLLECTION")
    parser.add_argument("--key-field", default="record_id", help="Unique observation field (default: record_id)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Bulk upsert batch size")
    arguments = parser.parse_args()

    result = load_dataset_to_mongodb(
        arguments.source,
        database=arguments.database,
        collection=arguments.collection,
        key_field=arguments.key_field,
        batch_size=arguments.batch_size,
    )
    print(result.to_dict())


if __name__ == "__main__":
    main()
