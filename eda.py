"""
Exploratory data analysis for the three cleaned datasets and the two
joined datasets. For each dataset, prints and saves to results/:
    - its size (rows x columns)
    - missing values per column (count and percent)
    - a seven-number summary of each quantitative variable of interest
    - value counts for each categorical variable of interest

Run clean_data.py and join_data.py first.
"""
import os

import pandas as pd

RESULTS = 'results/'

INCOME = 'MEDIAN_HH_INCOME_2023'
HEALTH = ['DIABETES', 'OBESITY']
FOOD = ['PCT_LACCESS_POP19', 'GROCPTH20', 'FFRPTH20']

# name: (path, quantitative variables, categorical variables)
DATASETS = {
    'census_income': ('data/core/census_income.csv', [INCOME], []),
    'places_health': ('data/core/places_health.csv', HEALTH, []),
    'food_atlas': ('data/core/food_atlas.csv', FOOD, ['METRO23']),
    'census_places': ('data/joined/census_places.csv',
                      [INCOME] + HEALTH, ['region']),
    'census_places_food': ('data/joined/census_places_food.csv',
                           [INCOME] + HEALTH + FOOD,
                           ['region', 'METRO23']),
}

# Food Atlas codes METRO23 as 1 for metro counties and 0 otherwise.
METRO_LABELS = {1: 'Metro', 0: 'Nonmetro'}


def load_dataset(path):
    """Reads a cleaned CSV, keeping FIPS codes as 5-character strings."""
    df = pd.read_csv(path, dtype={'FIPS': str})
    if 'METRO23' in df.columns:
        df['METRO23'] = df['METRO23'].map(METRO_LABELS)
    return df


def missing_summary(df):
    """
    Returns a DataFrame with the number and percent of missing values in
    each column of df, sorted from most to least missing.
    """
    counts = df.isna().sum()
    summary = pd.DataFrame({
        'missing': counts,
        'percent_missing': (counts / len(df) * 100).round(2),
    })
    return summary.sort_values('missing', ascending=False)


def seven_number_summary(df, columns):
    """
    Returns the mean, standard deviation, minimum, first quartile, median,
    third quartile, and maximum of each column in columns, one row per
    column. Missing values are ignored.
    """
    summary = df[columns].describe().drop('count').T
    summary = summary.rename(columns={'std': 'std_dev', '25%': 'Q1',
                                      '50%': 'median', '75%': 'Q3'})
    return summary.round(2)


def category_counts(df, column):
    """
    Returns the count of each unique value in column, including missing
    values, as a DataFrame.
    """
    counts = df[column].value_counts(dropna=False)
    return counts.rename_axis(column).reset_index(name='count')


def describe_dataset(name, df, quantitative, categorical):
    """Prints and saves the EDA tables for one dataset."""
    print(f'\n===== {name} =====')
    print(f'Size: {df.shape[0]} rows x {df.shape[1]} columns')

    missing = missing_summary(df)
    rows_missing = df.isna().any(axis=1).sum()
    print(f'Rows with any missing value: {rows_missing} '
          f'({rows_missing / len(df) * 100:.2f}%)')
    print('Columns with missing values:')
    print(missing[missing['missing'] > 0].to_string())
    missing.to_csv(f'{RESULTS}{name}_missing.csv')

    summary = seven_number_summary(df, quantitative)
    print('Seven-number summary:')
    print(summary.to_string())
    summary.to_csv(f'{RESULTS}{name}_summary.csv')

    for column in categorical:
        counts = category_counts(df, column)
        print(f'Counts of {column}:')
        print(counts.to_string(index=False))
        counts.to_csv(f'{RESULTS}{name}_counts_{column}.csv', index=False)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    for name, (path, quantitative, categorical) in DATASETS.items():
        df = load_dataset(path)
        describe_dataset(name, df, quantitative, categorical)


if __name__ == '__main__':
    main()
