import re


AMOUNT_KEYWORDS = ['amt', 'amount', 'price', 'total', 'value', 'sum']
TXN_ID_KEYWORDS = ['id', 'txn', 'trans']
TIMESTAMP_KEYWORDS = ['date', 'time', 'dt', 'timestamp']
CARD_KEYWORDS = ['card', 'pan', 'account']
ADDRESS_KEYWORDS = {
    'address_1': ['addr1', 'address1', 'city', 'state'],
    'address_2': ['addr2', 'address2', 'zip', 'postal']
}
PRODUCT_KEYWORDS = ['product', 'category', 'merchant', 'type']


def detect_format(filepath):
    ext = filepath.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        return 'csv'
    elif ext in ('parquet', 'pq'):
        return 'parquet'
    elif ext == 'json':
        return 'json'
    raise ValueError(f"Unsupported format: {ext}")


def _find_by_keywords(columns, keywords, used):
    for col in columns:
        if col in used:
            continue
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


def infer_column_roles(df, override=None):
    override = override or {}
    cols = list(df.columns)
    roles = {}
    used = set()

    if 'transaction_id' in override:
        roles['transaction_id'] = override['transaction_id']
        used.add(override['transaction_id'])
    else:
        tid = _find_by_keywords(cols, TXN_ID_KEYWORDS, used)
        if tid:
            roles['transaction_id'] = tid
            used.add(tid)
        else:
            for col in cols:
                if col not in used and df[col].is_unique:
                    roles['transaction_id'] = col
                    used.add(col)
                    break

    if 'amount' in override:
        roles['amount'] = override['amount']
        used.add(override['amount'])
    else:
        amt = _find_by_keywords(cols, AMOUNT_KEYWORDS, used)
        if amt:
            roles['amount'] = amt
            used.add(amt)
        else:
            for col in cols:
                if col not in used and df[col].dtype in ['float64', 'int64']:
                    if (df[col] > 0).sum() > len(df) * 0.9:
                        roles['amount'] = col
                        used.add(col)
                        break

    if 'timestamp' in override:
        roles['timestamp'] = override['timestamp']
        used.add(override['timestamp'])
    else:
        ts = _find_by_keywords(cols, TIMESTAMP_KEYWORDS, used)
        if ts:
            roles['timestamp'] = ts
            used.add(ts)

    if 'card_number' in override:
        roles['card_number'] = override['card_number']
        used.add(override['card_number'])
    else:
        card = _find_by_keywords(cols, CARD_KEYWORDS, used)
        if card:
            roles['card_number'] = card
            used.add(card)

    for canon, keywords in ADDRESS_KEYWORDS.items():
        if canon in override:
            roles[canon] = override[canon]
            used.add(override[canon])
        else:
            addr = _find_by_keywords(cols, keywords, used)
            if addr:
                roles[canon] = addr
                used.add(addr)

    if 'product_code' in override:
        roles['product_code'] = override['product_code']
        used.add(override['product_code'])
    else:
        prod = _find_by_keywords(cols, PRODUCT_KEYWORDS, used)
        if prod and df[prod].nunique() < min(100, len(df) * 0.1):
            roles['product_code'] = prod
            used.add(prod)

    return roles


def validate_minimum_columns(roles):
    missing = []
    if 'transaction_id' not in roles:
        missing.append('transaction_id (unique ID column)')
    if 'amount' not in roles:
        missing.append('amount (positive numeric column)')
    if missing:
        raise ValueError(
            f"Could not detect required columns: {missing}. "
            f"Detected: {roles}. Pass --OVERRIDE_MAPPINGS to specify manually."
        )
    return True