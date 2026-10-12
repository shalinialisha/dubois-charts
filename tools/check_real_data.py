"""
Draw every chart from real public data, read the way a new user would read
it -- with pandas, reshaped as little as possible -- and report what each
one did: drew, warned, or stopped with an error.

    python tools/check_real_data.py [--out DIR] [name-fragment ...]

The data -- about 80 MB, from GitHub -- are downloaded into DIR/data the
first time and kept there; each chart is saved as DIR/<scenario>.png, with
everything that happened in DIR/results.json. DIR is real-data-check/ by
default. Look at the pictures, not only the summary: a chart that draws
without a word can still be wrong.

Run it before a release. Every problem it found in October 2026 has a test
of its own in tests/test_real_data.py, made from a few rows shaped like the
file that showed it, so the test suite needs neither the network nor these
files.

Sources (each under its own licence; nothing here is redistributed):
  Du Bois's data for the 1900 plates  github.com/rfordatascience/tidytuesday (2021-02-16)
  vega-datasets                       github.com/vega/vega-datasets
  plotly datasets                     github.com/plotly/datasets
  2020 presidential results by county github.com/tonmcg/US_County_Level_Election_Results_08-24
  FiveThirtyEight                     github.com/fivethirtyeight/data
  World Bank population, global temperature  github.com/datasets
  Census population by state          github.com/jakevdp/data-USstates
  COVID-19 deaths and cases           github.com/nytimes/covid-19-data
  Energy and CO2                      github.com/owid/energy-data, github.com/owid/co2-data
  COVID-19 cases by country, a column a day  github.com/CSSEGISandData/COVID-19
  Gapminder                           github.com/plotly/datasets
  GDP, country codes, world cities, gold, oil, gas, prices, monthly temperature
                                      github.com/datasets
  Stock prices, GitHub commits        github.com/vega/vega-datasets
  Two Excel workbooks of sales        github.com/chris1610/pbpython (read with openpyxl)
"""

import argparse
import json
import os
import sys
import time
import traceback
import urllib.request
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import matplotlib                                                # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                  # noqa: E402
import pandas as pd                                              # noqa: E402

import dubois_charts as dc                                       # noqa: E402

_GH = 'https://raw.githubusercontent.com'
_TT = f'{_GH}/rfordatascience/tidytuesday/main/data/2021/2021-02-16'
_VEGA = f'{_GH}/vega/vega-datasets/main/data'
DATASETS = {
    **{f'dubois_{n}.csv': f'{_TT}/{n}.csv' for n in ('georgia_pop', 'census', 'furniture', 'city_rural',
                                                    'income', 'freed_slaves', 'occupation', 'conjugal')},
    **{f'vega_{n}': f'{_VEGA}/{n}' for n in ('unemployment.tsv', 'population.json', 'iowa-electricity.csv',
                                            'co2-concentration.csv', 'unemployment-across-industries.json',
                                            'population_engineers_hurricanes.csv', 'seattle-weather.csv',
                                            'income.json')},
    'plotly_minoritymajority.csv': f'{_GH}/plotly/datasets/master/minoritymajority.csv',
    'plotly_2011_us_ag_exports.csv': f'{_GH}/plotly/datasets/master/2011_us_ag_exports.csv',
    'election_2020_county.csv': f'{_GH}/tonmcg/US_County_Level_Election_Results_08-24/master/'
                                f'2020_US_County_Level_Presidential_Results.csv',
    '538_recent-grads.csv': f'{_GH}/fivethirtyeight/data/master/college-majors/recent-grads.csv',
    '538_hate_crimes.csv': f'{_GH}/fivethirtyeight/data/master/hate-crimes/hate_crimes.csv',
    '538_births_2000-2014.csv': f'{_GH}/fivethirtyeight/data/master/births/US_births_2000-2014_SSA.csv',
    '538_drinks.csv': f'{_GH}/fivethirtyeight/data/master/alcohol-consumption/drinks.csv',
    'datahub_global-temp-annual.csv': f'{_GH}/datasets/global-temp/main/data/annual.csv',
    'datahub_population.csv': f'{_GH}/datasets/population/main/data/population.csv',
    'jakevdp_state-population.csv': f'{_GH}/jakevdp/data-USstates/master/state-population.csv',
    'nyt_us-states.csv': f'{_GH}/nytimes/covid-19-data/master/us-states.csv',
    'nyt_us-counties-2022.csv': f'{_GH}/nytimes/covid-19-data/master/us-counties-2022.csv',
    'owid_energy.csv': f'{_GH}/owid/energy-data/master/owid-energy-data.csv',
    'owid_co2.csv': f'{_GH}/owid/co2-data/master/owid-co2-data.csv',
    # Third round: shapes the first two didn't have -- a wide table (a
    # column a day), Excel workbooks, dates written other ways, places
    # outside the United States, and very many or very few rows.
    'jhu_confirmed_global.csv': f'{_GH}/CSSEGISandData/COVID-19/master/csse_covid_19_data/'
                                f'csse_covid_19_time_series/time_series_covid19_confirmed_global.csv',
    'plotly_gapminder.csv': f'{_GH}/plotly/datasets/master/gapminderDataFiveYear.csv',
    'datahub_gdp.csv': f'{_GH}/datasets/gdp/main/data/gdp.csv',
    'datahub_country-codes.csv': f'{_GH}/datasets/country-codes/main/data/country-codes.csv',
    'datahub_world-cities.csv': f'{_GH}/datasets/world-cities/main/data/world-cities.csv',
    'datahub_gold-monthly.csv': f'{_GH}/datasets/gold-prices/main/data/monthly.csv',
    'datahub_global-temp-monthly.csv': f'{_GH}/datasets/global-temp/main/data/monthly.csv',
    'datahub_cpi-us.csv': f'{_GH}/datasets/cpi-us/main/data/cpiai.csv',
    'datahub_brent-daily.csv': f'{_GH}/datasets/oil-prices/main/data/brent-daily.csv',
    'datahub_natural-gas-daily.csv': f'{_GH}/datasets/natural-gas/main/data/daily.csv',
    'vega_stocks.csv': f'{_VEGA}/stocks.csv',
    'vega_github.csv': f'{_VEGA}/github.csv',
    'pbpython_salesfunnel.xlsx': f'{_GH}/chris1610/pbpython/master/data/salesfunnel.xlsx',
    'pbpython_sample-salesv3.xlsx': f'{_GH}/chris1610/pbpython/master/data/sample-salesv3.xlsx',
}

DATA = None          # set by main()


def raw(name):
    return os.path.join(DATA, name)


def read_json(name):
    with open(raw(name), encoding='utf-8') as f:
        return json.load(f)


SCENARIOS = []


def scenario(name, error=False):
    """A chart drawn from real data. error=True: the data as read can't be
    drawn -- a missing value, a word where a number belongs -- and the chart
    should stop with an error that says so."""
    def wrap(fn):
        SCENARIOS.append((name, fn, error))
        return fn
    return wrap


# ---------------------------------------------------------------- Du Bois's own data (#TidyTuesday 2021-02-16)

@scenario('dubois_occupation_pie')
def _():
    df = pd.read_csv(raw('dubois_occupation.csv'))
    negroes = df[df['Group'] == 'Negroes'].set_index('Occupation')['Percentage']
    return dc.pie_chart(negroes, title='Occupations of Negroes', subtitle='Du Bois, 1900')


@scenario('dubois_occupation_butterfly')
def _():
    df = pd.read_csv(raw('dubois_occupation.csv'))
    p = df.pivot(index='Occupation', columns='Group', values='Percentage')
    return dc.butterfly_chart(p.index, p['Negroes'], p['Whites'], left_label='Negroes',
                              right_label='Whites', title='Occupations of Negroes and Whites in Georgia')


@scenario('dubois_occupation_grouped_bars')
def _():
    df = pd.read_csv(raw('dubois_occupation.csv'))
    p = df.pivot(index='Occupation', columns='Group', values='Percentage')
    return dc.bar_chart(p.index, p, title='Occupations in Georgia', value_format='{:g}%')


@scenario('dubois_conjugal_grouped_bars')
def _():
    df = pd.read_csv(raw('dubois_conjugal.csv'))
    cats = df['Population'] + ', ' + df['Age']
    return dc.bar_chart(cats, df[['Single', 'Married', 'Divorced and Widowed']],
                        title='Conjugal condition', value_format='{:g}%')


@scenario('dubois_freed_slaves_area')
def _():
    df = pd.read_csv(raw('dubois_freed_slaves.csv'))
    return dc.stacked_area_chart(df['Year'], df[['Slave', 'Free']],
                                 title='Proportion of freemen and slaves among American Negroes')


@scenario('dubois_furniture_spiral')
def _():
    df = pd.read_csv(raw('dubois_furniture.csv'))
    return dc.spiral_chart(df['Year'], df['Houshold Value (Dollars)'],
                           title='Assessed value of household and kitchen furniture',
                           value_format='${:,.0f}')


@scenario('dubois_furniture_bars')
def _():
    df = pd.read_csv(raw('dubois_furniture.csv'))
    return dc.bar_chart(df['Year'], df['Houshold Value (Dollars)'],
                        title='Household and kitchen furniture owned by Georgia Negroes')


@scenario('dubois_city_rural_snake')
def _():
    df = pd.read_csv(raw('dubois_city_rural.csv'))
    return dc.snake_chart(df.set_index('Category')['Population'],
                          title='City and rural population, 1890')


@scenario('dubois_city_rural_pie')
def _():
    df = pd.read_csv(raw('dubois_city_rural.csv'))
    return dc.pie_chart(df.set_index('Category')['Population'], title='City and rural population, 1890')


@scenario('dubois_income_bars_with_missing_cell', error=True)
def _():
    # The first row of the file has one cell fewer than the header: pandas reads NaN.
    df = pd.read_csv(raw('dubois_income.csv'))
    return dc.bar_chart(df['Class'], df[['Rent', 'Food', 'Clothes', 'Tax', 'Other']],
                        title='Income and expenditure of 150 Negro families')


@scenario('dubois_income_bars_filled')
def _():
    df = pd.read_csv(raw('dubois_income.csv')).fillna(0)
    return dc.bar_chart(df['Class'], df['Actual Average'], title='Actual average income',
                        value_format='${:,.2f}')


@scenario('dubois_georgia_pop_grouped')
def _():
    df = pd.read_csv(raw('dubois_georgia_pop.csv'))
    return dc.bar_chart(df['Year'], df.set_index('Year')[['Colored', 'White']],
                        title='Comparative increase of white and colored population of Georgia',
                        value_format='{:.0f}%')


@scenario('dubois_census_usa_area_unsorted_years')
def _():
    df = pd.read_csv(raw('dubois_census.csv'))
    usa = df[df['region'] == 'USA Total']            # years run 1870 back to 1790
    return dc.stacked_area_chart(usa['year'], usa[['black_slaves', 'black_free']],
                                 title='Black Americans, enslaved and free, 1790-1870')


@scenario('dubois_census_south_area_filtered_rows')
def _():
    df = pd.read_csv(raw('dubois_census.csv'))
    south = df[(df['region'] == 'South') & df['division'].isna()]   # rows 26-34: index isn't 0, 1, 2...
    return dc.stacked_area_chart(south['year'], south[['white', 'black']],
                                 title='Population of the South, 1790-1870')


@scenario('dubois_census_regions_bars_1870')
def _():
    df = pd.read_csv(raw('dubois_census.csv'))
    regions = df[(df['year'] == 1870) & df['division'].isna() & (df['region'] != 'USA Total')]
    return dc.bar_chart(regions['region'], regions['black'], sort_descending=True,
                        title='Black population by region, 1870')


# ---------------------------------------------------------------- vega-datasets

@scenario('vega_unemployment_counties_int_fips')
def _():
    df = pd.read_csv(raw('vega_unemployment.tsv'), sep='\t')
    return dc.county_map_chart(df.set_index('id')['rate'], title='Unemployment rate by county, 2009',
                               value_format='{:.1%}')


@scenario('vega_population_pyramid_2000')
def _():
    df = pd.DataFrame(read_json('vega_population.json'))
    y = df[df['year'] == 2000]
    p = y.pivot(index='age', columns='sex', values='people').sort_index(ascending=False)
    labels = [f'{a}-{a + 4}' if a < 90 else '90+' for a in p.index]
    return dc.butterfly_chart(labels, p[1], p[2], left_label='Men', right_label='Women',
                              title='Population of the United States by age, 2000')


@scenario('vega_population_pyramid_ints_as_categories')
def _():
    df = pd.DataFrame(read_json('vega_population.json'))
    y = df[df['year'] == 1900]
    men = y[y['sex'] == 1].set_index('age')['people']
    women = y[y['sex'] == 2].set_index('age')['people']
    return dc.butterfly_chart(men.index, men, women, left_label='Men', right_label='Women',
                              title='United States, 1900, by age')


@scenario('vega_iowa_electricity_area_dates')
def _():
    df = pd.read_csv(raw('vega_iowa-electricity.csv'), parse_dates=['year'])
    p = df.pivot(index='year', columns='source', values='net_generation')
    return dc.stacked_area_chart(p.index, p, title='Iowa net electricity generation by source',
                                 subtitle='Thousand megawatt-hours')


@scenario('vega_iowa_electricity_snake_2017')
def _():
    df = pd.read_csv(raw('vega_iowa-electricity.csv'))
    last = df[df['year'] == '2017-01-01'].set_index('source')['net_generation']
    return dc.snake_chart(last, title="Iowa's electricity in 2017")


@scenario('vega_co2_monthly_spiral_741_points')
def _():
    df = pd.read_csv(raw('vega_co2-concentration.csv'), parse_dates=['Date'])
    return dc.spiral_chart(df['Date'], df['CO2'], title='CO2 at Mauna Loa, monthly',
                           show_value_labels=False)


@scenario('vega_co2_annual_spiral')
def _():
    df = pd.read_csv(raw('vega_co2-concentration.csv'), parse_dates=['Date'])
    annual = df.groupby(df['Date'].dt.year)['CO2'].mean()
    rise = annual - annual.iloc[0]
    return dc.spiral_chart(rise.index, rise, title='Rise in CO2 at Mauna Loa since 1958',
                           subtitle='Parts per million', value_format='{:.0f}')


@scenario('vega_industries_area_tz_dates_14_series')
def _():
    df = pd.DataFrame(read_json('vega_unemployment-across-industries.json'))
    df['date'] = pd.to_datetime(df['date'])          # "2000-01-01T08:00:00.000Z": time-zone aware
    p = df.pivot(index='date', columns='series', values='count')
    return dc.stacked_area_chart(p.index, p, title='Unemployed, by industry',
                                 subtitle='Thousands of people', show_value_labels=False)


@scenario('vega_industries_area_iso_strings')
def _():
    df = pd.DataFrame(read_json('vega_unemployment-across-industries.json'))
    p = df.pivot(index='date', columns='series', values='count')   # ISO strings, as read
    top = p[p.iloc[-1].sort_values(ascending=False).index[:5]]
    return dc.stacked_area_chart(top.index, top, title='Unemployed in the five largest industries')


@scenario('vega_engineers_state_map')
def _():
    df = pd.read_csv(raw('vega_population_engineers_hurricanes.csv'))
    return dc.state_map_chart(df.set_index('state')['engineers'], title='Engineers, share of population')


@scenario('vega_hurricanes_state_map_by_fips')
def _():
    df = pd.read_csv(raw('vega_population_engineers_hurricanes.csv'))
    return dc.state_map_chart(df.set_index('id')['hurricanes'], title='Hurricanes since 1851')


@scenario('vega_seattle_monthly_spiral')
def _():
    df = pd.read_csv(raw('vega_seattle-weather.csv'), parse_dates=['date'])
    monthly = df.set_index('date')['temp_max'].resample('MS').mean()
    return dc.spiral_chart(monthly.index, monthly, title='Seattle: average high, by month',
                           value_format='{:.0f}°C')


@scenario('vega_seattle_weather_value_counts_pie')
def _():
    df = pd.read_csv(raw('vega_seattle-weather.csv'))
    return dc.pie_chart(df['weather'].value_counts(), title='Seattle weather, 2012-2015')


@scenario('vega_income_state_map_top_bracket')
def _():
    df = pd.DataFrame(read_json('vega_income.json'))
    top = df[df['group'] == '200000+'].set_index('name')['pct']
    return dc.state_map_chart(top, title='Households earning $200,000 or more', value_format='{:.1%}')


# ---------------------------------------------------------------- plotly/datasets

@scenario('plotly_counties_percent_strings', error=True)
def _():
    df = pd.read_csv(raw('plotly_minoritymajority.csv'))
    return dc.county_map_chart(df.set_index('FIPS')['BlackPCT'], title='Black population, share')


@scenario('plotly_counties_named_with_state')
def _():
    df = pd.read_csv(raw('plotly_minoritymajority.csv'))
    df['HispanicPCT'] = df['HispanicPCT'].str.rstrip('%').astype(float)
    key = df['CTYNAME'] + ', ' + df['STNAME']
    return dc.county_map_chart(df.set_index(key)['HispanicPCT'], title='Hispanic population, share',
                               value_format='{:.0f}%')


@scenario('plotly_counties_one_state_by_name')
def _():
    df = pd.read_csv(raw('plotly_minoritymajority.csv'))
    tx = df[df['STNAME'] == 'Texas']
    return dc.county_map_chart(tx.set_index('CTYNAME')['TOT_POP'], state='TX',
                               title='Population of Texas by county')


@scenario('plotly_ag_exports_state_map_codes')
def _():
    df = pd.read_csv(raw('plotly_2011_us_ag_exports.csv'))
    return dc.state_map_chart(df.set_index('code')['total exports'], title='Agricultural exports, 2011',
                              colorbar_label='Millions of dollars')


@scenario('plotly_ag_exports_top10_bars')
def _():
    df = pd.read_csv(raw('plotly_2011_us_ag_exports.csv'))
    top = df.nlargest(10, 'total exports')
    return dc.bar_chart(top['state'], top['total exports'], title='Agricultural exports, 2011',
                        value_format='${:,.0f}M')


@scenario('plotly_ag_exports_grouped_top5')
def _():
    df = pd.read_csv(raw('plotly_2011_us_ag_exports.csv'))
    top = df.nlargest(5, 'total exports').set_index('state')
    return dc.bar_chart(top.index, top[['beef', 'pork', 'poultry', 'dairy', 'corn', 'wheat', 'cotton']],
                        title='What the five biggest exporters sold')


# ---------------------------------------------------------------- 2020 presidential election by county

@scenario('election_2020_margin_national_fips_read_as_int')
def _():
    df = pd.read_csv(raw('election_2020_county.csv'))        # 01001 becomes 1001
    margin = (df['per_gop'] - df['per_dem']) * 100
    return dc.county_map_chart(margin.set_axis(df['county_fips']), title='2020 margin by county',
                               value_format='{:+.0f}')


@scenario('election_2020_georgia_by_name')
def _():
    df = pd.read_csv(raw('election_2020_county.csv'), dtype={'county_fips': str})
    ga = df[df['state_name'] == 'Georgia']
    return dc.county_map_chart(ga.set_index('county_name')['per_dem'] * 100, state='Georgia',
                               title='Biden share of the vote, 2020', value_format='{:.0f}%')


@scenario('election_2020_total_votes_by_state_bars')
def _():
    df = pd.read_csv(raw('election_2020_county.csv'))
    by_state = df.groupby('state_name')['total_votes'].sum().nlargest(12)
    return dc.bar_chart(by_state.index, by_state, title='Votes cast in 2020, twelve largest states')


@scenario('election_2020_butterfly_largest_counties')
def _():
    df = pd.read_csv(raw('election_2020_county.csv'))
    big = df.nlargest(10, 'total_votes')
    names = big['county_name'] + ', ' + big['state_name']
    return dc.butterfly_chart(names, big['votes_dem'], big['votes_gop'], left_label='Biden',
                              right_label='Trump', title='The ten largest counties, 2020')


# ---------------------------------------------------------------- FiveThirtyEight

@scenario('538_majors_top15_all_caps')
def _():
    df = pd.read_csv(raw('538_recent-grads.csv'))
    top = df.nlargest(15, 'Median')
    return dc.bar_chart(top['Major'], top['Median'], title='Best-paid majors',
                        subtitle='Median earnings of recent graduates', value_format='${:,.0f}')


@scenario('538_majors_all_173')
def _():
    df = pd.read_csv(raw('538_recent-grads.csv'))
    return dc.bar_chart(df['Major'], df['Unemployment_rate'] * 100, title='Unemployment by major',
                        value_format='{:.1f}%', sort_descending=True)


@scenario('538_majors_category_pie_16_slices')
def _():
    df = pd.read_csv(raw('538_recent-grads.csv'))
    return dc.pie_chart(df.groupby('Major_category')['Total'].sum(), title='Recent graduates by field')


@scenario('538_majors_men_women_butterfly')
def _():
    df = pd.read_csv(raw('538_recent-grads.csv'))   # one major has no count of men and women
    cat = df.groupby('Major_category')[['Men', 'Women']].sum()
    return dc.butterfly_chart(cat.index, cat['Men'], cat['Women'], left_label='Men', right_label='Women',
                              title='Recent graduates by field and sex')


@scenario('538_hate_crimes_state_map_with_nans')
def _():
    df = pd.read_csv(raw('538_hate_crimes.csv'))
    return dc.state_map_chart(df.set_index('state')['hate_crimes_per_100k_splc'],
                              title='Hate incidents per 100,000, Nov. 2016')


@scenario('538_births_monthly_spiral_multiindex')
def _():
    df = pd.read_csv(raw('538_births_2000-2014.csv'))
    monthly = df.groupby(['year', 'month'])['births'].sum()
    return dc.spiral_chart(monthly.index, monthly, title='Births by month, 2000-2014',
                           show_value_labels=False)


@scenario('538_births_monthly_spiral_dates')
def _():
    df = pd.read_csv(raw('538_births_2000-2014.csv'))
    df['date'] = pd.to_datetime(dict(year=df['year'], month=df['month'], day=1))
    monthly = df.groupby('date')['births'].sum()
    return dc.spiral_chart(monthly.index, monthly / 1000, title='Births by month, 2000-2014',
                           subtitle='Thousands', show_value_labels=False)


@scenario('538_births_weekday_bars')
def _():
    df = pd.read_csv(raw('538_births_2000-2014.csv'))
    days = df.groupby('day_of_week')['births'].mean()
    days.index = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    return dc.bar_chart(days.index, days, title='Average births by day of the week')


@scenario('538_drinks_top10_bars')
def _():
    df = pd.read_csv(raw('538_drinks.csv'))
    top = df.nlargest(10, 'total_litres_of_pure_alcohol')
    return dc.bar_chart(top['country'], top['total_litres_of_pure_alcohol'],
                        title='Litres of pure alcohol per person, 2010')


@scenario('538_drinks_country_pie_row')
def _():
    df = pd.read_csv(raw('538_drinks.csv')).set_index('country')
    return dc.pie_chart(df.loc['France', ['beer_servings', 'spirit_servings', 'wine_servings']],
                        title='What France drinks')


@scenario('538_drinks_beer_wine_butterfly')
def _():
    df = pd.read_csv(raw('538_drinks.csv'))
    top = df.nlargest(12, 'total_litres_of_pure_alcohol')
    return dc.butterfly_chart(top['country'], top['beer_servings'], top['wine_servings'],
                              left_label='Beer', right_label='Wine', title='Beer or wine?')


# ---------------------------------------------------------------- datahub.io core datasets

@scenario('datahub_global_temp_bars_negative')
def _():
    df = pd.read_csv(raw('datahub_global-temp-annual.csv'))
    gis = df[df['Source'] == 'GISTEMP'].sort_values('Year').tail(30)
    return dc.bar_chart(gis['Year'], gis['Mean'], title='Global temperature anomaly',
                        value_format='{:+.2f}°C')


@scenario('datahub_global_temp_spiral_negative', error=True)
def _():
    df = pd.read_csv(raw('datahub_global-temp-annual.csv'))
    gis = df[df['Source'] == 'GISTEMP'].sort_values('Year')
    return dc.spiral_chart(gis['Year'], gis['Mean'], title='Global temperature anomaly')


@scenario('datahub_population_area_5_countries')
def _():
    df = pd.read_csv(raw('datahub_population.csv'))
    five = df[df['Country Name'].isin(['China', 'India', 'United States', 'Indonesia', 'Brazil'])]
    p = five.pivot(index='Year', columns='Country Name', values='Value') / 1e6
    return dc.stacked_area_chart(p.index, p, title='Population of the five largest countries',
                                 subtitle='Millions')


@scenario('datahub_population_bars_latest_with_aggregates')
def _():
    df = pd.read_csv(raw('datahub_population.csv'))
    latest = df[df['Year'] == df['Year'].max()].nlargest(15, 'Value')
    return dc.bar_chart(latest['Country Name'], latest['Value'],
                        title=f"Population, {df['Year'].max()}")


# ---------------------------------------------------------------- Census population estimates by state

@scenario('jakevdp_state_population_with_usa_total')
def _():
    df = pd.read_csv(raw('jakevdp_state-population.csv'))
    t = df[(df['ages'] == 'total') & (df['year'] == 2012)]
    return dc.state_map_chart(t.set_index('state/region')['population'], title='Population, 2012')


@scenario('jakevdp_under18_share_by_state')
def _():
    df = pd.read_csv(raw('jakevdp_state-population.csv'))
    p = df[df['year'] == 2012].pivot(index='state/region', columns='ages', values='population')
    share = (p['under18'] / p['total'] * 100).drop('USA')
    return dc.state_map_chart(share, title='Under 18, share of population, 2012', value_format='{:.0f}%')


# ---------------------------------------------------------------- New York Times COVID-19 data

@scenario('nyt_states_deaths_map_with_territories')
def _():
    df = pd.read_csv(raw('nyt_us-states.csv'))
    last = df[df['date'] == df['date'].max()]
    return dc.state_map_chart(last.set_index('state')['deaths'], title='COVID-19 deaths, to March 2023')


@scenario('nyt_states_area_daily_dates')
def _():
    df = pd.read_csv(raw('nyt_us-states.csv'), parse_dates=['date'])
    five = df[df['state'].isin(['California', 'Texas', 'Florida', 'New York', 'Pennsylvania'])]
    p = five.pivot(index='date', columns='state', values='deaths').fillna(0)
    return dc.stacked_area_chart(p.index, p, title='COVID-19 deaths, five largest states',
                                 show_value_labels=False)


@scenario('nyt_counties_fips_with_blanks')
def _():
    df = pd.read_csv(raw('nyt_us-counties-2022.csv'))
    last = df[df['date'] == df['date'].max()]
    return dc.county_map_chart(last.set_index('fips')['deaths'], title='COVID-19 deaths by county, 2022')


@scenario('nyt_counties_fips_as_strings')
def _():
    df = pd.read_csv(raw('nyt_us-counties-2022.csv'), dtype={'fips': str})
    last = df[df['date'] == df['date'].max()].dropna(subset=['fips'])
    return dc.county_map_chart(last.set_index('fips')['deaths'], title='COVID-19 deaths by county, 2022')


@scenario('nyt_counties_names_with_state')
def _():
    df = pd.read_csv(raw('nyt_us-counties-2022.csv'))
    last = df[df['date'] == df['date'].max()]
    key = last['county'] + ', ' + last['state']
    return dc.county_map_chart(last.set_index(key)['cases'], title='COVID-19 cases by county, 2022')


@scenario('nyt_counties_georgia_names')
def _():
    df = pd.read_csv(raw('nyt_us-counties-2022.csv'))
    ga = df[(df['state'] == 'Georgia') & (df['date'] == df['date'].max())]
    return dc.county_map_chart(ga.set_index('county')['deaths'], title='COVID-19 deaths in Georgia, 2022')


# ---------------------------------------------------------------- Our World in Data

@scenario('owid_usa_energy_area_with_nans', error=True)
def _():
    df = pd.read_csv(raw('owid_energy.csv'))
    us = df[(df['country'] == 'United States') & (df['year'] >= 1965)].set_index('year')
    cols = ['coal_consumption', 'oil_consumption', 'gas_consumption', 'nuclear_consumption',
            'hydro_consumption', 'wind_consumption', 'solar_consumption']
    return dc.stacked_area_chart(us.index, us[cols], title='Energy used in the United States',
                                 subtitle='Terawatt-hours')


@scenario('owid_usa_energy_area_clean')
def _():
    df = pd.read_csv(raw('owid_energy.csv'))
    us = df[(df['country'] == 'United States') & (df['year'] >= 1965)].set_index('year')
    cols = {'coal_consumption': 'Coal', 'oil_consumption': 'Oil', 'gas_consumption': 'Gas',
            'nuclear_consumption': 'Nuclear', 'hydro_consumption': 'Hydro', 'wind_consumption': 'Wind',
            'solar_consumption': 'Solar'}
    data = us[list(cols)].rename(columns=cols).dropna()
    return dc.stacked_area_chart(data.index, data, title='Energy used in the United States',
                                 subtitle='Terawatt-hours')


@scenario('owid_world_electricity_mix_snake')
def _():
    df = pd.read_csv(raw('owid_energy.csv'))
    w = df[(df['country'] == 'World')].dropna(subset=['coal_share_elec']).iloc[-1]
    shares = w[['coal_share_elec', 'gas_share_elec', 'hydro_share_elec', 'nuclear_share_elec',
                'wind_share_elec', 'solar_share_elec', 'oil_share_elec', 'biofuel_share_elec',
                'other_renewables_share_elec_exc_biofuel']]
    shares.index = ['Coal', 'Gas', 'Hydro', 'Nuclear', 'Wind', 'Solar', 'Oil', 'Bioenergy', 'Other renewables']
    return dc.snake_chart(shares, title=f"The world's electricity, {int(w['year'])}")


@scenario('owid_world_electricity_mix_pie_object_series')
def _():
    df = pd.read_csv(raw('owid_energy.csv'))
    w = df[(df['country'] == 'World')].dropna(subset=['coal_share_elec']).iloc[-1]   # mixed row: object dtype
    shares = w[['coal_share_elec', 'gas_share_elec', 'hydro_share_elec', 'nuclear_share_elec',
                'wind_share_elec', 'solar_share_elec']]
    return dc.pie_chart(shares, title="The world's electricity")


@scenario('owid_co2_top10_emitters_bars')
def _():
    df = pd.read_csv(raw('owid_co2.csv'))
    countries = df[df['iso_code'].notna() & (df['year'] == 2022)]
    top = countries.nlargest(10, 'co2')
    return dc.bar_chart(top['country'], top['co2'], title='CO2 emissions, 2022',
                        subtitle='Million tonnes')


@scenario('owid_world_co2_spiral_annual')
def _():
    df = pd.read_csv(raw('owid_co2.csv'))
    w = df[(df['country'] == 'World') & (df['year'] >= 1900)]
    return dc.spiral_chart(w['year'], w['co2'], title="The world's CO2 emissions since 1900",
                           show_value_labels=False)


@scenario('owid_co2_share_pie_13_slices')
def _():
    df = pd.read_csv(raw('owid_co2.csv'))
    countries = df[df['iso_code'].notna() & (df['year'] == 2022)].set_index('country')['co2'].dropna()
    top = countries.nlargest(12)
    top['Everyone else'] = countries.sum() - top.sum()
    return dc.pie_chart(top, title='Who emits the CO2', subtitle='2022')


# ---------------------------------------------------------------- second round: data left exactly as read

@scenario('nyt_counties_fips_float_after_dropna')
def _():
    df = pd.read_csv(raw('nyt_us-counties-2022.csv'))          # fips becomes float: 1001.0
    last = df[df['date'] == df['date'].max()].dropna(subset=['fips'])
    return dc.county_map_chart(last.set_index('fips')['deaths'], title='COVID-19 deaths by county, 2022')


@scenario('vega_iowa_area_iso_strings')
def _():
    df = pd.read_csv(raw('vega_iowa-electricity.csv'))           # 'year' left as "2001-01-01"
    p = df.pivot(index='year', columns='source', values='net_generation')
    return dc.stacked_area_chart(p.index, p, title='Iowa net electricity generation by source')


@scenario('nyt_states_area_daily_iso_strings')
def _():
    df = pd.read_csv(raw('nyt_us-states.csv'))                   # dates left as text
    five = df[df['state'].isin(['California', 'Texas', 'Florida', 'New York', 'Pennsylvania'])]
    p = five.pivot(index='date', columns='state', values='deaths').fillna(0)
    return dc.stacked_area_chart(p.index, p, title='COVID-19 deaths, five largest states')


@scenario('dubois_conjugal_multiindex_bars')
def _():
    df = pd.read_csv(raw('dubois_conjugal.csv')).set_index(['Population', 'Age'])
    return dc.bar_chart(df.index, df['Married'], title='Married, by age', value_format='{:g}%')


@scenario('seattle_monthly_spiral_iso_strings')
def _():
    df = pd.read_csv(raw('vega_seattle-weather.csv'))
    df['month'] = df['date'].str[:7]                             # "2012-01"
    monthly = df.groupby('month')['precipitation'].sum()
    return dc.spiral_chart(monthly.index, monthly, title='Seattle rain by month', value_format='{:.0f} mm')


# ---------------------------------------------------------------- third round: other shapes (October 2026, macOS)

def _jhu_by_country():
    df = pd.read_csv(raw('jhu_confirmed_global.csv'))     # one column a day, "1/22/20"
    return df.groupby('Country/Region').sum(numeric_only=True).drop(columns=['Lat', 'Long'])


@scenario('jhu_wide_dates_as_columns_area')
def _():
    by = _jhu_by_country()
    top = by.loc[by.iloc[:, -1].nlargest(5).index].T / 1e6   # dates become the index, as text
    return dc.stacked_area_chart(top.index, top, title='COVID-19 cases, five countries',
                                 subtitle='Millions')


@scenario('jhu_wide_last_column_bars')
def _():
    by = _jhu_by_country()
    last = by.iloc[:, -1].nlargest(15)
    return dc.bar_chart(last.index, last, title=f'COVID-19 cases to {by.columns[-1]}')


@scenario('jhu_one_row_as_series_spiral')
def _():
    df = pd.read_csv(raw('jhu_confirmed_global.csv'))
    italy = df[df['Country/Region'] == 'Italy'].iloc[0, 4:]          # a row: object dtype
    weekly = italy.iloc[::7]
    return dc.spiral_chart(weekly.index, weekly, title='COVID-19 cases in Italy, weekly',
                           show_value_labels=False)


@scenario('jhu_provinces_pie')
def _():
    df = pd.read_csv(raw('jhu_confirmed_global.csv'))
    china = df[df['Country/Region'] == 'China'].set_index('Province/State').iloc[:, -1].nlargest(10)
    return dc.pie_chart(china, title='COVID-19 cases in China, ten provinces')


@scenario('jhu_countries_on_state_map', error=True)
def _():
    by = _jhu_by_country()
    return dc.state_map_chart(by.iloc[:, -1], title='COVID-19 cases by country')


@scenario('gapminder_long_continents_area')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    p = df.groupby(['year', 'continent'])['pop'].sum().unstack() / 1e6
    return dc.stacked_area_chart(p.index, p, title='Population by continent', subtitle='Millions')


@scenario('gapminder_life_expectancy_butterfly')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    p = df.pivot(index='country', columns='year', values='lifeExp')
    big = df[df['year'] == 2007].nlargest(12, 'pop')['country']
    return dc.butterfly_chart(big, p.loc[big, 1952], p.loc[big, 2007], left_label='1952',
                              right_label='2007', title='Life expectancy')


@scenario('gapminder_142_countries_bars')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    y = df[df['year'] == 2007]
    return dc.bar_chart(y['country'], y['gdpPercap'], sort_descending=True,
                        title='GDP per person, 2007', value_format='${:,.0f}')


@scenario('gapminder_142_countries_pie')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    y = df[df['year'] == 2007].set_index('country')['pop']
    return dc.pie_chart(y, title='Population, 2007')


@scenario('gapminder_continents_snake')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    y = df[df['year'] == 2007].groupby('continent')['pop'].sum()
    return dc.snake_chart(y, title='Population by continent, 2007')


@scenario('gapminder_one_row_bar')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    one = df[(df['country'] == 'Norway') & (df['year'] == 2007)]
    return dc.bar_chart(one['country'], one['lifeExp'], title='Life expectancy, 2007')


@scenario('gapminder_one_row_butterfly')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    one = df[(df['country'] == 'Norway') & (df['year'] == 2007)]
    return dc.butterfly_chart(one['country'], one['lifeExp'], one['gdpPercap'] / 1000,
                              left_label='Life expectancy', right_label='GDP per person, $1000s')


@scenario('gapminder_one_slice_pie')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    one = df[(df['continent'] == 'Oceania') & (df['year'] == 2007)].groupby('continent')['pop'].sum()
    return dc.pie_chart(one, title='Population of Oceania')


@scenario('gapminder_one_part_snake')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    one = df[(df['country'] == 'Norway') & (df['year'] == 2007)].set_index('country')['pop']
    return dc.snake_chart(one, title='Population of Norway')


@scenario('gapminder_one_year_area', error=True)
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    p = df[df['year'] == 2007].groupby(['year', 'continent'])['pop'].sum().unstack() / 1e6
    return dc.stacked_area_chart(p.index, p, title='Population by continent, 2007')


@scenario('gapminder_two_points_spiral')
def _():
    df = pd.read_csv(raw('plotly_gapminder.csv'))
    n = df[(df['country'] == 'Norway') & df['year'].isin([1952, 2007])]
    return dc.spiral_chart(n['year'], n['pop'], title='Population of Norway')


@scenario('gdp_world_long_spiral')
def _():
    df = pd.read_csv(raw('datahub_gdp.csv'))
    w = df[df['Country Name'] == 'World']
    return dc.spiral_chart(w['Year'], w['Value'] / 1e12, title='World GDP',
                           subtitle='Trillions of dollars')


@scenario('excel_salesfunnel_pie_by_rep')
def _():
    df = pd.read_excel(raw('pbpython_salesfunnel.xlsx'))
    return dc.pie_chart(df.groupby('Rep')['Price'].sum(), title='Sales by rep')


@scenario('excel_salesfunnel_pivot_table_bars')
def _():
    df = pd.read_excel(raw('pbpython_salesfunnel.xlsx'))
    p = pd.pivot_table(df, index='Manager', columns='Status', values='Price', aggfunc='sum', fill_value=0)
    return dc.bar_chart(p.index, p, title='Sales by manager and status')


@scenario('excel_salesfunnel_butterfly')
def _():
    df = pd.read_excel(raw('pbpython_salesfunnel.xlsx'))
    g = df.groupby('Name')[['Quantity', 'Price']].sum()
    return dc.butterfly_chart(g.index, g['Quantity'], g['Price'], left_label='Units',
                              right_label='Price', title='Accounts')


@scenario('excel_sales_customers_bars')
def _():
    df = pd.read_excel(raw('pbpython_sample-salesv3.xlsx'))
    s = df.groupby('name')['ext price'].sum()
    return dc.bar_chart(s.index, s, title='Sales by customer, 2014', sort_descending=True)


@scenario('excel_sales_months_as_text_area')
def _():
    df = pd.read_excel(raw('pbpython_sample-salesv3.xlsx'))
    month = df['date'].astype(str).str[:7]                        # "2014-01"
    p = df.groupby([month, df['sku'].str[:2]])['ext price'].sum().unstack()
    return dc.stacked_area_chart(p.index, p, title='Sales by month and product line')


@scenario('excel_sales_every_sale_area_returns_negative', error=True)
def _():
    df = pd.read_excel(raw('pbpython_sample-salesv3.xlsx'))
    return dc.stacked_area_chart(df['date'], df['ext price'], title='Every sale, 2014')


@scenario('excel_sales_monthly_spiral')
def _():
    df = pd.read_excel(raw('pbpython_sample-salesv3.xlsx'), parse_dates=['date'])
    m = df.set_index('date')['ext price'].resample('MS').sum()
    return dc.spiral_chart(m.index, m, title='Sales by month, 2014', value_format='${:,.0f}')


@scenario('gold_monthly_yyyy_mm_area')
def _():
    df = pd.read_csv(raw('datahub_gold-monthly.csv'))             # "1833-01", 2,300 months
    return dc.stacked_area_chart(df['Date'], df[['Price']], title='Gold, dollars an ounce')


@scenario('gold_monthly_bars_last_year')
def _():
    df = pd.read_csv(raw('datahub_gold-monthly.csv')).tail(12)
    return dc.bar_chart(df['Date'], df['Price'], title='Gold, the last twelve months',
                        value_format='${:,.0f}')


@scenario('stocks_mon_d_yyyy_pivot_area')
def _():
    df = pd.read_csv(raw('vega_stocks.csv'))                      # "Jan 1 2000"
    p = df.pivot(index='date', columns='symbol', values='price')   # sorts the text: Apr, Aug, Dec...
    return dc.stacked_area_chart(p.index, p.fillna(0), title='Five stocks, 2000-2010')


@scenario('stocks_mon_d_yyyy_spiral')
def _():
    df = pd.read_csv(raw('vega_stocks.csv'))
    msft = df[df['symbol'] == 'MSFT']
    return dc.spiral_chart(msft['date'], msft['price'], title='Microsoft', value_format='${:.0f}')


@scenario('github_slashed_datetimes_area')
def _():
    df = pd.read_csv(raw('vega_github.csv'))                      # "2015/01/01 01:00:00"
    return dc.stacked_area_chart(df['time'], df[['count']], title='Commits per hour')


@scenario('global_temp_monthly_negative_area')
def _():
    df = pd.read_csv(raw('datahub_global-temp-monthly.csv'))
    g = df[(df['Source'] == 'GISTEMP')].sort_values('Year').tail(120)
    return dc.stacked_area_chart(g['Year'], g[['Mean']], title='Global temperature anomaly, by month')


@scenario('cpi_monthly_first_value_missing', error=True)
def _():
    df = pd.read_csv(raw('datahub_cpi-us.csv'))
    return dc.stacked_area_chart(df['Date'], df[['Inflation']], title='Inflation, by month')


@scenario('cpi_monthly_index_spiral')
def _():
    df = pd.read_csv(raw('datahub_cpi-us.csv'))
    annual = df.groupby(df['Date'].str[:4])['Index'].mean()
    return dc.spiral_chart(annual.index, annual, title='Consumer prices since 1913')


@scenario('brent_daily_9000_rows_area')
def _():
    df = pd.read_csv(raw('datahub_brent-daily.csv'))
    return dc.stacked_area_chart(df['Date'], df['Price'],                 # one column: a Series
                                 title='Brent crude, dollars a barrel')


@scenario('natural_gas_daily_5700_rows_spiral', error=True)
def _():
    df = pd.read_csv(raw('datahub_natural-gas-daily.csv'))
    return dc.spiral_chart(df['Date'], df['Price'], title='Natural gas, daily', show_value_labels=False)


@scenario('world_cities_by_country_bars')
def _():
    df = pd.read_csv(raw('datahub_world-cities.csv'))
    top = df['country'].value_counts().head(15)
    return dc.bar_chart(top.index, top, title='Cities in the GeoNames list, by country')


@scenario('world_cities_vietnamese_names_pie')
def _():
    df = pd.read_csv(raw('datahub_world-cities.csv'))
    vn = df[df['country'] == 'Viet Nam']['name'].str.split().str[0].value_counts().head(8)  # "Thị", "Bắc", "Ấp"
    return dc.pie_chart(vn, title='Towns of Viet Nam, by the first word of their names')


@scenario('world_cities_persian_names_snake')
def _():
    df = pd.read_csv(raw('datahub_world-cities.csv'))
    ir = df[df['country'] == 'Iran, Islamic Republic of']['name'].str.split().str[-1].value_counts().head(6)
    return dc.snake_chart(ir, title='Towns of Iran, by the last word of their names')   # "Āb", "Shahr"


@scenario('world_cities_provinces_on_state_map', error=True)
def _():
    df = pd.read_csv(raw('datahub_world-cities.csv'))
    canada = df[df['country'] == 'Canada']['subcountry'].value_counts()
    return dc.state_map_chart(canada, title='Cities of Canada')


def _gdp_with_names(column):
    gdp = pd.read_csv(raw('datahub_gdp.csv'))
    codes = pd.read_csv(raw('datahub_country-codes.csv'))
    names = codes.set_index('ISO3166-1-Alpha-3')[column]
    last = gdp[gdp['Year'] == gdp['Year'].max()]
    last = last[last['Country Code'].isin(names.index)].nlargest(10, 'Value')
    return names.loc[last['Country Code']].to_numpy(), last['Value'].to_numpy() / 1e12


@scenario('country_codes_chinese_names_bars')
def _():
    names, gdp = _gdp_with_names('UNTERM Chinese Short')
    return dc.bar_chart(names, gdp, title='国内生产总值', subtitle='万亿美元')


@scenario('country_codes_arabic_names_pie')
def _():
    names, gdp = _gdp_with_names('official_name_ar')
    return dc.pie_chart(dict(zip(names, gdp)), title='الناتج المحلي الإجمالي')


@scenario('country_codes_russian_names_butterfly')
def _():
    names, gdp = _gdp_with_names('UNTERM Russian Short')
    return dc.butterfly_chart(names, gdp, gdp / 2, left_label='ВВП', right_label='Половина',
                              title='Валовой внутренний продукт')


def download(out):
    os.makedirs(out, exist_ok=True)
    for name, url in DATASETS.items():
        path = os.path.join(out, name)
        if os.path.exists(path):
            continue
        print(f'downloading {name}', flush=True)
        with urllib.request.urlopen(url, timeout=300) as response, open(path + '.part', 'wb') as f:
            f.write(response.read())
        os.replace(path + '.part', path)


def main():
    global DATA
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--out', default='real-data-check', help='where the pictures and data go')
    parser.add_argument('only', nargs='*', help='run only scenarios whose names contain these')
    args = parser.parse_args()
    DATA = os.path.join(args.out, 'data')
    download(DATA)

    results, surprises = [], 0
    for name, fn, error_expected in SCENARIOS:
        if args.only and not any(o in name for o in args.only):
            continue
        record = {'name': name, 'error_expected': error_expected}
        stale = os.path.join(args.out, f'{name}.png')
        if os.path.exists(stale):
            os.remove(stale)          # left by an earlier run: this one may not draw
        start = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                fig = fn()
                record['png'] = os.path.join(args.out, f'{name}.png')
                fig.savefig(record['png'])
                record['ok'] = True
            except Exception as e:
                record['ok'] = False
                record['error'] = f'{type(e).__name__}: {e}'
                record['where'] = traceback.format_exc(limit=-3)
        record['warnings'] = [str(w.message) for w in caught]
        record['seconds'] = round(time.perf_counter() - start, 2)
        plt.close('all')
        results.append(record)
        surprise = record['ok'] == error_expected
        surprises += surprise
        status = ('drew' if record['ok'] else 'error (expected)' if error_expected else 'ERROR')
        print(f"{'!! ' if surprise else '   '}{status:17}{record['seconds']:6.1f}s  {name}"
              f"{'  ' + str(len(record['warnings'])) + ' warning(s)' if record['warnings'] else ''}",
              flush=True)
        for text in ([record.get('error')] if not record['ok'] else []) + record['warnings']:
            print(f"      {text[:300]}{'...' if len(text) > 300 else ''}")

    with open(os.path.join(args.out, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump({'versions': {'dubois_charts': dc.__version__, 'matplotlib': matplotlib.__version__,
                                'pandas': pd.__version__, 'python': sys.version.split()[0]},
                   'results': results}, f, indent=1)
    print(f"\n{len(results)} scenarios; {surprises} unexpected. Pictures in {args.out}/.")
    return 1 if surprises else 0


if __name__ == '__main__':
    sys.exit(main())
