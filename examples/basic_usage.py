"""
Example: Using dubois-charts to create Du Bois-inspired
data visualizations.

This script demonstrates all eight chart types the package provides,
each with a short, illustrative dataset in the spirit of the subjects
Du Bois himself charted (occupations, population, literacy, land) --
none of the numbers below are claimed to be historically accurate; they
exist to show what each chart type looks like with realistic-shaped
data, not to document real 1900 statistics. (The state map's are the
2020 census's, rounded.) For the one chart in this
package that IS a historically verified recreation of a specific
original plate, see `dubois_charts.charts.plate51` instead of this file.

Run this directly to regenerate every image in examples/:

    python3 examples/basic_usage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import dubois_charts as dc


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))


def example_bar_chart():
    """A single-series horizontal bar chart, sorted descending."""
    print("1. bar_chart: single series")
    fig = dc.bar_chart(
        categories=['Agriculture', 'Domestic Service', 'Manufacturing',
                    'Trade', 'Professions'],
        values=[45, 25, 12, 10, 8],
        title='Occupations of Negroes in Georgia',
        value_format='{:.0f}%',  # the data are percentages; the default prints plain numbers
        sort_descending=True,
        save_path=os.path.join(OUT, 'example_bar_chart.png'),
    )
    plt.close(fig)


def example_bar_chart_grouped():
    """A grouped (multi-series) bar chart, comparing categories across
    several series side by side."""
    print("2. bar_chart: grouped series")
    fig = dc.bar_chart(
        categories=['Agriculture', 'Domestic Service', 'Manufacturing', 'Trade'],
        values={
            'Urban': [15, 30, 22, 20],
            'Rural': [65, 15, 5, 8],
        },
        title='Occupations by Community Type',
        value_format='{:.0f}%',
        save_path=os.path.join(OUT, 'example_bar_chart_grouped.png'),
    )
    plt.close(fig)


def example_stacked_area_chart():
    """A stacked area chart over a time axis -- values don't need to
    sum to 100 or to anything in particular."""
    print("3. stacked_area_chart")
    fig = dc.stacked_area_chart(
        x=[1890, 1900, 1910, 1920, 1930],
        series={
            'Farm Ownership': [8, 13, 18, 22, 25],
            'Tenant Farming': [55, 52, 48, 44, 40],
            'Wage Labor': [37, 35, 34, 34, 35],
        },
        title='Land Tenure Status Over Time',
        subtitle='Percentage of surveyed agricultural households',
        save_path=os.path.join(OUT, 'example_stacked_area_chart.png'),
    )
    plt.close(fig)


def example_butterfly_chart():
    """A mirrored two-sided comparison: two groups, category by category."""
    print("4. butterfly_chart")
    fig = dc.butterfly_chart(
        categories=['Agriculture', 'Domestic Service', 'Trade', 'Professions'],
        left_values=[52, 38, 6, 4],
        right_values=[31, 55, 8, 6],
        left_label='Male',
        right_label='Female',
        title='Occupations by Sex',
        save_path=os.path.join(OUT, 'example_butterfly_chart.png'),
    )
    plt.close(fig)


def example_spiral_chart():
    """A growing series wound into a spiral: each point's place sets its
    angle, its value its distance from the centre."""
    print("5. spiral_chart")
    fig = dc.spiral_chart(
        categories=[1870, 1880, 1890, 1900, 1910, 1920],
        values=[45, 62, 89, 140, 210, 305],
        title='Population Growth Over Time',
        subtitle='Estimated population, in thousands',
        save_path=os.path.join(OUT, 'example_spiral_chart.png'),
    )
    plt.close(fig)


def example_snake_chart():
    """One long scale, folded into rows -- useful when a single
    100%-style breakdown is too wide to read as one thin bar."""
    print("6. snake_chart")
    fig = dc.snake_chart(
        segments={
            'Agriculture': 45, 'Domestic Service': 25, 'Manufacturing': 12,
            'Trade': 10, 'Professions': 8,
        },
        n_rows=4,
        title='Occupations, Folded to Fit',
        save_path=os.path.join(OUT, 'example_snake_chart.png'),
    )
    plt.close(fig)


def example_pie_chart():
    """A proportional circle, with automatic external labels (and
    leader lines) for slices too thin to hold their own text."""
    print("7. pie_chart")
    fig = dc.pie_chart(
        segments={'Married': 52, 'Single': 31, 'Widowed': 12, 'Divorced': 5},
        title='Conjugal Condition',
        save_path=os.path.join(OUT, 'example_pie_chart.png'),
    )
    plt.close(fig)


def example_county_map_chart():
    """A choropleth map of Georgia's 159 counties -- the one chart type
    that renders real geographic boundaries rather than a computed
    shape."""
    print("8. county_map_chart")
    fig = dc.county_map_chart(
        data={
            'Fulton': 82, 'DeKalb': 74, 'Chatham': 55, 'Bibb': 61,
            'Cobb': 70, 'Richmond': 48, 'Muscogee': 58, 'Clarke': 66,
        },
        title='Percentage Reporting Literacy, By County',
        colorbar_label='Percentage literate',
        save_path=os.path.join(OUT, 'example_county_map_chart.png'),
    )
    plt.close(fig)


def example_state_map_chart():
    """The whole country, state by state -- as Du Bois mapped it for the
    1900 exhibition -- with Alaska and Hawaii inset below."""
    print("9. state_map_chart")
    population = {   # 2020 census, millions, rounded
        'CA': 39.5, 'TX': 29.1, 'FL': 21.5, 'NY': 20.2, 'PA': 13.0, 'IL': 12.8, 'OH': 11.8,
        'GA': 10.7, 'NC': 10.4, 'MI': 10.1, 'NJ': 9.3, 'VA': 8.6, 'WA': 7.7, 'AZ': 7.2,
        'MA': 7.0, 'TN': 6.9, 'IN': 6.8, 'MD': 6.2, 'MO': 6.2, 'WI': 5.9, 'CO': 5.8,
        'MN': 5.7, 'SC': 5.1, 'AL': 5.0, 'LA': 4.7, 'KY': 4.5, 'OR': 4.2, 'OK': 4.0,
        'CT': 3.6, 'UT': 3.3, 'IA': 3.2, 'NV': 3.1, 'AR': 3.0, 'MS': 2.96, 'KS': 2.9,
        'NM': 2.1, 'NE': 1.96, 'ID': 1.84, 'WV': 1.79, 'HI': 1.46, 'NH': 1.38, 'ME': 1.36,
        'RI': 1.10, 'MT': 1.08, 'DE': 0.99, 'SD': 0.89, 'ND': 0.78, 'AK': 0.73, 'DC': 0.69,
        'VT': 0.64, 'WY': 0.58,
    }
    fig = dc.state_map_chart(
        data=population,
        title='Population by State, 2020',
        colorbar_label='Millions of residents',
        save_path=os.path.join(OUT, 'example_state_map_chart.png'),
    )
    plt.close(fig)


def example_colors_and_themes():
    """The lower-level pieces every chart above is built on -- useful
    directly if you're building a custom matplotlib chart in the same
    visual language rather than using one of the eight chart functions."""
    print("10. dubois_charts.colors + dubois_charts.set_theme: direct matplotlib use")

    dc.set_theme('classic')
    colors = dc.get_categorical(4)

    fig, ax = plt.subplots(figsize=(8, 5))
    categories = ['Agriculture', 'Manufacturing', 'Trade', 'Professions']
    values = [45, 20, 15, 8]
    ax.barh(categories, values, color=colors, edgecolor='black', linewidth=1.2)
    ax.set_xlabel('Percentage')
    ax.set_title('Direct Matplotlib Use With Du Bois Colors and Theme')
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'example_colors_and_themes.png'),
                dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    dc.reset_theme()


def main():
    print("=" * 60)
    print("dubois-charts: example gallery")
    print("=" * 60)
    example_bar_chart()
    example_bar_chart_grouped()
    example_stacked_area_chart()
    example_butterfly_chart()
    example_spiral_chart()
    example_snake_chart()
    example_pie_chart()
    example_county_map_chart()
    example_state_map_chart()
    example_colors_and_themes()
    print()
    print("Done -- see examples/ for the generated images.")


if __name__ == '__main__':
    main()
