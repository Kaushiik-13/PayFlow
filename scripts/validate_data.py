import os
import sys


def find_data_file():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    if not os.path.exists(data_dir):
        return None
    for f in os.listdir(data_dir):
        ext = f.rsplit('.', 1)[-1].lower()
        if ext in ('csv', 'parquet', 'json'):
            return os.path.join(data_dir, f)
    return None


def validate():
    data_path = find_data_file()
    if data_path is None:
        print("ERROR: No data file found in data/ folder.")
        print("Place a CSV, Parquet, or JSON file in the data/ folder and re-run.")
        sys.exit(1)

    file_ext = data_path.rsplit('.', 1)[-1].lower()
    print(f"Found data file: {os.path.basename(data_path)} (format: {file_ext})")

    import pandas as pd

    if file_ext == 'csv':
        df = pd.read_csv(data_path)
    elif file_ext == 'parquet':
        df = pd.read_parquet(data_path)
    elif file_ext == 'json':
        df = pd.read_json(data_path)
    else:
        print(f"ERROR: Unsupported format: {file_ext}")
        sys.exit(1)

    print(f"\nRecords  : {len(df):,}")
    print(f"Columns  : {len(df.columns)} total")
    print(f"Nulls    : {df.isnull().sum().sum():,}")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from schema_utils import infer_column_roles, validate_minimum_columns

    roles = infer_column_roles(df)
    print(f"\nDetected column roles:")
    for canonical, source in roles.items():
        print(f"  {canonical:20s} -> {source}")

    try:
        validate_minimum_columns(roles)
        print("\n[OK] Minimum requirements met (transaction_id + amount)")
    except ValueError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)

    optional_features = {
        'card_masked': 'card_number' in roles,
        'transaction_hour': 'timestamp' in roles,
        'is_weekend': 'timestamp' in roles,
        'txn_velocity': 'transaction_id' in roles and 'timestamp' in roles,
        'merchant_avg_amount': 'product_code' in roles,
        'amount_deviation': 'product_code' in roles,
        'geo_flag': 'address_1' in roles and 'address_2' in roles
    }
    print(f"\nFeature availability:")
    for feature, available in optional_features.items():
        status = '[OK]' if available else '[SKIP]'
        print(f"  {feature:25s} {status}")

    print()
    print("=" * 50)
    print("VALIDATION PASSED - Dataset is ready for the pipeline")
    print("=" * 50)


if __name__ == '__main__':
    validate()