from greenfleet.pipeline.etl.extract import extract_parquet

df = extract_parquet("data/raw/CPS_Poseidon.parquet")

print(df.shape)
print(df.head())