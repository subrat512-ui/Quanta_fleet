from greenfleet.pipeline.etl.extract import extract_csv

df = extract_csv("data/raw/data.csv")

print(df.shape)
print(df.head())
