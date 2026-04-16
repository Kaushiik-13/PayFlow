import os
import sys

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'train_transaction.csv')

REQUIRED_COLUMNS = [
    'TransactionID', 'isFraud', 'TransactionDT', 'TransactionAmt',
    'ProductCD', 'card1', 'addr1', 'addr2'
]

def validate():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: File not found at {os.path.abspath(DATA_PATH)}")
        print("Place train_transaction.csv in the data/ folder and re-run.")
        sys.exit(1)

    import pandas as pd

    print(f"Loading {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    print()

    print(f"Records  : {len(df):,}")
    print(f"Columns  : {len(df.columns)} total")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"MISSING required columns: {missing}")
        sys.exit(1)

    print(f"Nulls    : {df.isnull().sum().sum():,}")

    fraud_pct = df['isFraud'].mean() * 100
    print(f"Fraud %  : {fraud_pct:.2f}%")

    if df['TransactionID'].is_unique:
        print("[OK] TransactionID is unique")
    else:
        print("[WARN] TransactionID has duplicates")

    if (df['TransactionAmt'] > 0).all():
        print("[OK] TransactionAmt has positive values")
    else:
        print("[WARN] TransactionAmt has non-positive values")

    print()
    print("Column list:")
    for i, col in enumerate(df.columns):
        print(f"  {i+1:3d}. {col}")

    print()
    print("=" * 50)
    print("VALIDATION PASSED - Dataset is ready for the pipeline")
    print("=" * 50)

if __name__ == '__main__':
    validate()