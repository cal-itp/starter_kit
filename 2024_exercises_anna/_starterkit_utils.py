import pandas as pd
import numpy as np
import altair as alt
from calitp_data_analysis import calitp_color_palette
from IPython.display import HTML, Image, Markdown, display, display_html

def reverse_snakecase(df:pd.DataFrame)->pd.DataFrame:
    """
    Clean up columns to remove underscores and spaces.
    """
    df.columns = df.columns.str.replace("_", " ").str.strip().str.title()
    
    df.columns = (df.columns.str.replace("Dac", "DAC")
                  .str.replace("Vmt", "VMT")
                  .str.replace("Zev", "ZEV")
                  .str.replace("Lu", "Landuse")
                  .str.replace("Ct", "Caltrans")
                 )
    return df

def load_dataset()->pd.DataFrame:
    """
    Load the final dataframe.
    """
    GCS_FILE_PATH = "gs://calitp-analytics-data/data-analyses/starter_kit/"
    FILE = "starter_kit_example_categorized.parquet"
    
    # Read dataframe in
    df = pd.read_parquet(f"{GCS_FILE_PATH}{FILE}")
    
    # Capitalize the Scope of Work column again since it is all lowercase
    df.scope_of_work = df.scope_of_work.str.capitalize()
    
    # Clean up the column names
    df = reverse_snakecase(df)
    return df

def aggregate_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Find the median overall score and project cost 
    and total unique projects by category.
    """
    agg1 = (
        df.groupby(["Category"])
        .aggregate(
            {
                "Overall Score": "median",
                "Project Cost": "median",
                "Project Name": "nunique",
            }
        )
        .reset_index()
        .rename(
            columns={
                "Overall Score": "Median Score",
                "Project Cost": "Median Project Cost",
                "Project Name": "Total Projects",
            }
        )
    )
    
    # Format the Cost column properly
    agg1['Median Project Cost'] = agg1['Median Project Cost'].apply(lambda x: '${:,.0f}'.format(x))
    
    return agg1

def wide_to_long(df:pd.DataFrame)->pd.DataFrame:
    """
    Change the dataframe from wide to long based on the project name and
    Caltrans District.
    """
    df2 = pd.melt(
    df,
    id_vars=["Caltrans District","Project Name"],
    value_vars=[
        "Accessibility Score",
        "DAC Accessibility Score",
        "DAC Traffic Impacts Score",
        "Freight Efficiency Score",
        "Freight Sustainability Score",
        "Mode Shift Score",
        "Landuse Natural Resources Score",
        "Safety Score",
        "VMT Score",
        "ZEV Score",
        "Public Engagement Score",
        "Climate Resilience Score",
        "Program Fit Score",
    ])
    
    df2 = df2.rename(columns = {'variable':'Metric',
                                'value':'Score'})
    return df2

def style_df(df: pd.DataFrame):
    """
    Styles a dataframe and displays it.
    """
    display(
        df.style.hide(axis="index")
        .format(precision=0)  # Display only 2 decimal points
        .set_properties(**{
            "background-color": "white",
            "text-align": "center"
        })
    )

def create_metric_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Create a chart that displays metric scores
    for each project.
    """
    # Create dropdown
    metrics_list = df["Metric"].unique().tolist()

    metrics_dropdown = alt.binding_select(
        options=metrics_list,
        name="Metrics: ",
    )
    # Column that controls the bar charts
    xcol_param = alt.selection_point(
        fields=["Metric"], value=metrics_list[0], bind=metrics_dropdown
    )

    chart = (
        alt.Chart(df, title="Metric by Categories")
        .mark_circle(size=200)
        .encode(
            x=alt.X("Score", scale=alt.Scale(domain=[0, 10])),
            y=alt.Y("Project Name"),
            color=alt.Color(
                "Score",
                scale=alt.Scale(
                    range=calitp_color_palette.CALITP_CATEGORY_BRIGHT_COLORS
                ),
            ),
            tooltip=list(df.columns),
        )
        .properties(width=400, height=250)
    )
    
    chart = chart.add_params(xcol_param).transform_filter(xcol_param)
    
    return chart

def create_district_summary(df: pd.DataFrame, caltrans_district: int):
    """
    Create a summary of CSIS metrics for one Caltrans District.
    """
    filtered_df = df.loc[df["Caltrans District"] == caltrans_district].reset_index(
        drop=True
    )
    # Finding the values referenced in the narrative
    median_score = filtered_df["Overall Score"].median()
    total_projects = filtered_df["Project Name"].nunique()
    max_project = filtered_df["Project Cost"].max()
    max_project = f"${max_project:,.2f}"

    # Aggregate the dataframe
    aggregated_df = aggregate_by_category(filtered_df)

    # Change the dataframe from wide to long
    df2 = wide_to_long(filtered_df)

    # Create narrative
    display(
        Markdown(
            f"""The median score for projects in District {caltrans_district} is <b>{median_score}</b><br> 
        The total number of projects is <b>{total_projects}</b><br>
        The most expensive project costs <b>{max_project}</b>
        """
        )
    )
    display(
        Markdown(
            f"""<h4>Metrics aggregated by Categories</h4>
        """
        )
    )
    style_df(aggregated_df)

    display(
        Markdown(
            f"""<h4>Overview of Projects</h4>
        """
        )
    )
    style_df(filtered_df[["Project Name", "Overall Score", "Scope Of Work"]])
    display(
        Markdown(
            f"""<h4>Metric Scores by Project</h4>
        """
        )
    )
    display(create_metric_chart(df2))    
    
    
OTHER = "Other"

def add_and(s: str) -> str:
        """Replace empty strings with OTHER, otherwise replace the last ', ' with ', and' or 'and' where correct"""
        last_pos = s.rfind(", ")
        if last_pos == -1:
            return OTHER if s == "" else s
        count_commas = s.count(", ")
        if count_commas > 1:
            return f"{s[:last_pos]}, and {s[last_pos+2:]}"
        else: 
            return f"{s[:last_pos]} and {s[last_pos+2:]}"
    
def format_int_as_cost(val):
    return f"${val:,.2f}"
    
def create_category_summary(project_scores_with_category: pd.DataFrame, category: list[str]):
    """
    Create a summary of how CSIS metrics for projects within a specified category differe in each district
    """
    # Filter projects for only the selected category
    project_scores_filtered = project_scores_with_category.loc[
        project_scores_with_category[category].replace({
            "Y": True, "N": False
        }).all(axis=1)
    ]
    # Finding the values referenced in the narrative
    median_score = project_scores_filtered["Overall Score"].median()
    total_projects = project_scores_filtered["Project Name"].nunique()
    max_project_cost = project_scores_filtered["Project Cost"].max()
    max_project_cost_str = format_int_as_cost(max_project_cost)
    
    # Aggregate the relevant values in the DataFrame by district
    aggregated_df = project_scores_filtered.groupby("Caltrans District").agg({
        "Overall Score": "median",s
        "Project Name": "nunique",
        "Project Cost": "max",
    }).rename(columns={
        "Overall Score": "Median Overall Score",
        "Project Name": "# Projects",
        "Project Cost": "Max Project Cost",
    }).reset_index()
    aggregated_df["Max Project Cost"] = aggregated_df["Max Project Cost"].map(format_int_as_cost).astype(str)
    df_long = wide_to_long(project_scores_filtered)
    
    category_string = add_and(", ".join(category))
    
    # Create narrative
    display(
        Markdown(
            f"""The median score for projects in category {category_string} is <b>{int(median_score)}</b><br>
            There are {total_projects} projects.<br>
            The most expensive project costs {max_project_cost_str}<br>
            """
        )
    )
    display(
        Markdown(
            "### Metrics Aggregated by Districts"
        )
    )
    style_df(aggregated_df)
    display(
        Markdown(
            "### Overview of Projects"
        )
    )
    style_df(project_scores_filtered[["Project Name", "Overall Score", "Scope Of Work"]])
    display(
        Markdown(
            "### Metric Scores by Projects"
        )
    )
    display(create_metric_chart(df_long))
    
    