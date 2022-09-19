import pandas as pd
import logging
import streamlit as st
import datetime


def read_uploaded_file_into_df(file):
    filename = file.name

    if filename.endswith(".xlsx"):
        df = pd.read_excel(file)

    elif filename.endswith(".txt") or filename.endswith(".tsv"):
        df = pd.read_csv(file, delimiter="\t")

    elif filename.endswith(".csv"):
        df = pd.read_csv(file)

    else:
        df = None
        logging.warning(
            "WARNING: File could not be read. \nFile has to be a .xslx, .tsv, .csv or .txt file"
        )
        return

    return df


def get_unique_values_from_column(column):
    unique_values = st.session_state.dataset.metadata[column].unique().tolist()
    return unique_values


def get_analysis_options_from_dict(method, options_dict):
    # extract plotting options from dict amd display as selectbox or checkbox
    # give selceted options to plotting function
    method_dict = options_dict.get(method)

    if "settings" not in method_dict.keys():

        if "between_two_groups" in method_dict.keys():
            return between_two_groups(method=method, options_dict=options_dict)

        else:
            return method_dict["function"]()

    settings_dict = method_dict.get("settings")
    chosen_parameter_dict = {}

    for parameter in settings_dict:

        parameter_dict = settings_dict[parameter]

        if "options" in parameter_dict.keys():
            chosen_parameter = st.selectbox(
                parameter_dict.get("label"),
                options=parameter_dict.get("options")  # ,
                # key=method + parameter  + str(datetime.datetime.now()),
            )
        else:
            chosen_parameter = st.checkbox(parameter_dict.get("label"))  # ,
            # key = method + parameter  + str(datetime.datetime.now()))

        chosen_parameter_dict[parameter] = chosen_parameter

    submitted = st.button("Submit")

    if submitted:
        return method_dict["function"](**chosen_parameter_dict)


def between_two_groups(method, options_dict):
    """
    for Volcano Plot, Differetial Expression Analysis and t-test
    selectbox based on selected column
    """

    chosen_parameter_dict = {}
    group = st.selectbox(
        "Grouping variable",
        options=st.session_state.dataset.metadata.columns.to_list(),
    )
    if group is not None:

        unique_values = get_unique_values_from_column(group)

        group1 = st.selectbox("Group 1", options=unique_values)

        group2 = st.selectbox("Group 2", options=unique_values)

    if method == "Volcano":
        analysis_method = st.selectbox(
            "Differential Analysis using:", options=["anova", "wald", "ttest"],
        )
        chosen_parameter_dict.update({"method": analysis_method})

    chosen_parameter_dict.update({"column": group, "group1": group1, "group2": group2})

    submitted = st.button("Submit")

    if submitted:
        return options_dict.get(method)["function"](**chosen_parameter_dict)


def remove_misc_session_state():
    pass


def get_analysis(method, options_dict):

    if method in options_dict.keys():
        obj = get_analysis_options_from_dict(method, options_dict=options_dict)
        return obj
