import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget
from ipyleaflet import Map, basemaps, Marker, Popup
import ipywidgets as widgets
import os
from dotenv import load_dotenv
from map import station_locations

# -----------------------------------------------------------------------
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
syn_token = os.getenv("syn_token")
# The GitHub owner (user/organization) and repository name
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")

# Add theme from the _brand.yml file
theme = ui.Theme.from_brand(__file__)

# UI Definition
# -----------------------------------------------------------------------
app_ui = ui.page_fluid(
    ui.page_navbar(
        ui.nav_panel(
            "Dashboard",
            ui.row(
                ui.layout_columns(
                    # Sidebar in its own card (left column)
                    ui.card(
                        ui.h6(
                            "(Placeholder text) The Roaring Fork Observation Network (iRON) is a network of soil moisture monitoring \
                            stations in the Roaring Fork Valley"
                        ),
                        ui.input_selectize(
                            "station",
                            "Select a station:",
                            [
                                "",
                                "RFBRC",
                                "RFSMM",
                                "RFSPV",
                                "RFNSA",
                                "RFNST",
                                "RFGLS",
                                "RFSKM",
                                "RFGLR",
                                "ASEC2",
                            ],
                            selected="RFBRC",
                        ),
                        ui.input_selectize(
                            "vars",
                            "Select a variable:",
                            [
                                "",
                                "air_temp",
                                "dew_point_temperature",
                                "relative_humidity",
                                "soil_temp",
                                "precip_accum",
                                "soil_moisture",
                                "wind_speed",
                                "wind_direction",
                                "solar_radiation",
                                "snow_depth",
                                "snow_water_equiv",
                            ],
                            selected="air_temp",
                            multiple=True,
                        ),
                        ui.input_date_range(
                            "date_range",
                            "Date Range",
                            start="2025-02-06",
                            end="2025-02-07",
                            format="yyyy-mm-dd",
                        ),
                    ),
                    # Main content in the middle and right columns
                    ui.layout_columns(
                        ui.card(ui.output_plot("weather_plot")),
                        ui.card(ui.output_data_frame("variable_data_output")),
                        col_widths=(6, 6),
                    ),
                    col_widths=(2, 9),  # Sidebar takes 2 columns, main content takes 9
                ),
            ),
            ui.row(
                ui.layout_columns(
                    ui.card(
                        ui.input_text(
                            "feedback_text",
                            "Please share your feedback on current features and wanted features",
                            "Input your feedback here",
                        ),
                        ui.input_action_button("submit_feedback", "Submit Feedback"),
                        ui.output_text_verbatim("feedback_status_output"),
                    ),
                    ui.card(
                        ui.card_header("About this app", class_="bg_light"),
                        ui.markdown(
                            """
                            This app uses data from the Roaring Fork Observation Network in 
                            the Roaring Fork Valley Watershed. Locations of the stations can 
                            be found in the Map tab. Here's more on data usage and how to use it.
                            """
                        ),
                    ),
                    col_widths=(6, 6),
                ),
            ),
        ),
        ui.nav_panel(
            "Map",
            ui.row(
                ui.card(
                    output_widget("station_map_output", height="100%", width="100%"),
                    style="padding: 0px; height: 800px; overflow: hidden;",
                ),
                style="width: 100%;",
            ),
        ),
        theme=theme,  # Ensure `theme` is properly defined elsewhere
    ),
)


# ------------------------------------------------------------------------
# Server Logic
# ------------------------------------------------------------------------
def server(input, output, session):
    feedback_status = reactive.Value("")

    @reactive.Effect
    @reactive.event(input.submit_feedback)
    def submit_feedback_issue():
        """
        When the user clicks 'Submit Feedback', create a new GitHub issue
        and display a notification.
        """
        feedback = input.feedback_text().strip()

        if not feedback:
            feedback_status.set("Feedback is empty. Please type something first.")
            ui.notification_show(
                "Feedback is empty. Please type something first.",
                type="warning",
                duration=4000,
            )
            return  # Ensure the function exits

        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {"title": "User Feedback from Shiny App", "body": feedback}

        try:
            r = requests.post(api_url, headers=headers, json=payload, timeout=10)
            if r.status_code == 201:
                feedback_status.set("Thank you! Your feedback has been submitted.")
                ui.notification_show(
                    "Thank you! Your feedback has been submitted as a GitHub issue.",
                    type="message",
                    duration=5000,
                )
            else:
                feedback_status.set(f"Error creating issue: {r.status_code}\n{r.text}")
                ui.notification_show(
                    f"Error creating issue: {r.status_code}\n{r.text}", type="error"
                )
        except Exception as e:
            feedback_status.set(f"Error: {e}")
            ui.notification_show(f"Error: {e}", type="error")

        finally:
            # Reset the button to remove the spinner
            ui.update_action_button(
                "submit_feedback", label="Submit Feedback", disabled=False
            )

        print("Feedback submission completed.")  # Debugging step

    @output
    @render.text
    def feedback_status_output():
        return feedback_status.get()

    def get_vars_str():
        """
        Ensure vars is always a properly formatted string without parentheses.
        """
        raw_vars = input.vars()

        if not raw_vars:
            return "air_temp"  # Default value

        if isinstance(raw_vars, tuple):  # Convert tuple to list if needed
            raw_vars = list(raw_vars)

        if isinstance(raw_vars, list):
            return ",".join(map(str, raw_vars))

        return str(raw_vars)  # If it's a single string, return as is

    def value():
        return input.text()

    @reactive.calc
    def url():
        try:
            date_range = input.date_range()
            station = input.station()

            if (
                not date_range
                or len(date_range) != 2
                or None in date_range
                or not station
            ):
                print("Invalid date range or station missing.")
                return ""

            start, end = date_range

            formatted_start = (
                start.strftime("%Y%m%d%H%M") if hasattr(start, "strftime") else ""
            )
            formatted_end = (
                end.strftime("%Y%m%d%H%M") if hasattr(end, "strftime") else ""
            )

            if not formatted_start or not formatted_end:
                print("Invalid date formatting.")
                return ""
            # if staion = RF the use this url
            request_url = (
                f"https://api.synopticdata.com/v2/stations/timeseries?"
                f"stid={station}"
                f"&start={formatted_start}"
                f"&end={formatted_end}"
                f"&vars={get_vars_str()}"
                f"&token={syn_token}"
            )
            # elif station = NWIS then use this url

            print(f"Generated URL: {request_url}")
            return request_url

        except Exception as e:
            print(f"Error constructing URL: {e}")
            return ""

    @reactive.calc
    def weather_data():
        request_url = url()

        if not request_url:
            print("No valid URL generated.")
            return {"Error": "Invalid API URL."}

        try:
            response = requests.get(request_url)
            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.reason}")
                return {
                    "Error": f"API Error: {response.status_code} - {response.reason}"
                }

            data = response.json()

            if "STATION" not in data or not isinstance(data["STATION"], list):
                print("Unexpected API response format:", data)
                return {"Error": "Unexpected API response format."}

            return data

        except requests.exceptions.RequestException as e:
            print(f"Error fetching API data: {e}")
            return {"Error": f"Error fetching API data: {e}"}

    @reactive.calc
    def parsed_data():
        """
        Retrieve and parse the API data, then return a suitable Pandas DataFrame.
        """
        data = weather_data()
        if not data or "Error" in data:
            return None

        station_list = data.get("STATION", [{}])
        if not station_list or not isinstance(station_list, list):
            print("Invalid 'STATION' data structure:", data)
            return None

        station_data = station_list[0]
        observations = station_data.get("OBSERVATIONS", {})

        # Convert the ISO8601 date strings to datetime
        times = pd.to_datetime(observations.get("date_time", []))

        # Build a DataFrame for each variable we want to plot
        selected_vars = get_vars_str().split(",")
        df = pd.DataFrame({"Time": times})

        for var_name in selected_vars:
            variable_key = f"{var_name}_set_1"
            if variable_key in observations:
                df[var_name] = observations[variable_key]

        return df

    @output
    @render.plot
    def weather_plot():
        """
        Render a Seaborn line plot of each selected variable vs. time.
        If exactly two variables are selected, use a double (secondary) Y-axis.
        If only one variable is selected, use a single axis.
        If more than two variables, plot only the first two on the dual-axis.
        """
        df = parsed_data()
        if df is None or df.empty:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "No data available", ha="center", va="center")
            return fig

        # Identify columns other than Time
        selected_vars = [col for col in df.columns if col != "Time"]

        if len(selected_vars) == 0:
            # No variables to plot
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "No variables selected", ha="center", va="center")
            return fig

        elif len(selected_vars) == 1:
            # Only one variable selected => single axis
            fig, ax = plt.subplots(figsize=(6, 4))
            var = selected_vars[0]
            sns.lineplot(data=df, x="Time", y=var, ax=ax, label=var)

            ax.set_xlabel("Time")
            ax.set_ylabel("Value")
            ax.set_title(f"Weather Observations ({var})")
            fig.autofmt_xdate()  # Rotate/format date ticks
            return fig

        else:
            # Two or more variables => dual-axis for the first two
            fig, ax = plt.subplots(figsize=(6, 4))
            ax2 = ax.twinx()  # secondary y-axis

            var1, var2 = selected_vars[0], selected_vars[1]

            # Plot first variable on the primary y-axis
            sns.lineplot(data=df, x="Time", y=var1, ax=ax, label=var1, color="C0")
            ax.set_ylabel(var1, color="C0")

            # Plot second variable on the secondary y-axis
            sns.lineplot(data=df, x="Time", y=var2, ax=ax2, label=var2, color="C1")
            ax2.set_ylabel(var2, color="C1")

            # Additional aesthetic adjustments
            ax.set_xlabel("Time")
            ax.set_title(f"Weather Observations ({var1} & {var2})")

            # Rotate/format date ticks
            fig.autofmt_xdate()

            # If you want separate legends, you can manage them manually, but
            # often a combined legend is simpler.
            lines_1, labels_1 = ax.get_legend_handles_labels()
            lines_2, labels_2 = ax2.get_legend_handles_labels()
            ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

            return fig

    @render.data_frame
    def variable_data_output():
        # Fetch data from API
        data = weather_data()

        # Handle cases where API call fails or data is missing
        if not data or "Error" in data:
            print("Error: No valid data received")
            return render.DataGrid(pd.DataFrame({"Error": ["No data available."]}))

        try:
            station_data = data.get("STATION", [{}])

            if (
                not station_data
                or not isinstance(station_data, list)
                or not station_data[0].get("OBSERVATIONS")
            ):
                print("Error: Unexpected API response format")
                return render.DataGrid(
                    pd.DataFrame({"Error": ["Unexpected API response format."]})
                )

            station_data = station_data[0]
            observations = station_data.get("OBSERVATIONS", {})

            df_master = pd.DataFrame()
            for var_name in get_vars_str().split(","):
                variable_key = f"{var_name}_set_1"
                if variable_key not in observations:
                    print(f"Warning: {variable_key} not found in API response")
                    return render.DataGrid(
                        pd.DataFrame(
                            {
                                "Error": [
                                    f"Variable '{variable_key}' not found in API response."
                                ]
                            }
                        )
                    )

                df_var = pd.DataFrame(
                    {
                        "Time": pd.to_datetime(
                            observations.get("date_time", []), errors="coerce"
                        ),
                        var_name: observations.get(variable_key, []),
                    }
                )

                if df_var.empty:
                    print("Warning: DataFrame is empty")
                    return render.DataGrid(
                        pd.DataFrame({"Error": ["No valid data available."]})
                    )

                # Merge each variable's data into a master DataFrame on Time
                if df_master.empty:
                    df_master = df_var
                else:
                    df_master = pd.merge(df_master, df_var, on="Time", how="outer")

            print("Data table successfully loaded")
            return render.DataGrid(df_master)

        except Exception as e:
            print(f"Error processing data: {e}")
            return render.DataGrid(
                pd.DataFrame({"Error": [f"Error processing data: {e}"]})
            )

    @output
    @render_widget
    def station_map_output():
        # Create the map with layout to fit the container
        m = Map(
            center=(39.336, -107.0439),
            zoom=10,
            basemap=basemaps.CartoDB.Positron,
            layout=widgets.Layout(height="100%", width="100%"),
        )

        # Add markers for each station
        for idx, station in station_locations.iterrows():
            # Create HTML content for the popup
            popup_content = f"""
            <div style="min-width: 150px;">
                <h4>{station["name"]}</h4>
                <p><b>Elevation:</b> {station["elevation"]} ft</p>
                <p><b>Status:</b> {station["status"]}</p>
                <p><b>Coordinates:</b> {station["lat"]:.4f}, {station["lon"]:.4f}</p>
            </div>
            """

            # Create a marker with an attached popup
            marker = Marker(
                location=(station["lat"], station["lon"]),
                draggable=False,
                title=station["name"],  # Shows as tooltip on hover
                popup=widgets.HTML(popup_content),  # This will show when clicked
            )

            # Add marker to the map
            m.add_layer(marker)

        return m


app = App(app_ui, server)

if __name__ == "__main__":
    app.run()
