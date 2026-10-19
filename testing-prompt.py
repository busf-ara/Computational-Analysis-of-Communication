######## Inspect .RDS file to understand example data 

import pyreadr
import pandas as pd

# 1. Specify the path to  .rds file
file_path = "all_multi_paragraphs_2022_2026.RDS"

# 2. Read the .rds file
result = pyreadr.read_r(file_path)

# 3. Extract the actual data frame 
# (An .rds file contains a single object, mapped to the key `None`)
df = result[None]


# Print the first 5 rows to look at the data structure
print("--- First 5 Rows ---")
print(df.head())

# Print column names, non-null counts, and data types
print("\n--- DataFrame Info ---")
print(df.info())

########### Export the df to a CSV file

result = pyreadr.read_r(file_path)

print("Startting conversion to csv")
df = result[None]

print("3. Exporting to CSV file")C
output_filename = "all_multi_parapgraphs_2022_2026.csv"
df.to_csv(output_filename, index=False)

print("Done. Check file explorer")
