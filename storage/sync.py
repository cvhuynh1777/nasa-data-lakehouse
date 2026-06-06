import boto3
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
BUCKET           = os.getenv("MINIO_BUCKET", "nasa-lakehouse")

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
)


def sync_folder(local_path: Path, s3_prefix: str):
    """Upload all parquet files from a local folder to MinIO."""
    files = list(local_path.glob("**/*.parquet"))
    if not files:
        print(f"  no files in {local_path}")
        return

    for filepath in files:
        relative = filepath.relative_to(local_path.parent.parent)
        s3_key = str(relative)
        s3.upload_file(str(filepath), BUCKET, s3_key)
        print(f"  uploaded → {s3_key} ({filepath.stat().st_size:,} bytes)")


def sync_all():
    """Sync all storage layers to MinIO."""
    print("Syncing to MinIO...\n")

    layers = [
        (Path("storage/bronze"), "bronze"),
        (Path("storage/silver"), "silver"),
        (Path("storage/gold"),   "gold"),
    ]

    for local_path, prefix in layers:
        if local_path.exists():
            print(f"[{prefix}]")
            sync_folder(local_path, prefix)
        else:
            print(f"[{prefix}] skipping — folder does not exist")

    print("\nDone!")


if __name__ == "__main__":
    sync_all()