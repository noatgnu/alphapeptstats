import io
import os

import streamlit as st

try:
    from alphastats.DataSet import DataSet
    from alphastats.gui.utils.analysis_helper import (
        get_sample_names_from_software_file,
        read_uploaded_file_into_df,
    )
    from alphastats.gui.utils.software_options import software_options
    from alphastats.gui.utils.ui_helper import sidebar_info
    from alphastats.loader.MaxQuantLoader import MaxQuantLoader

except ModuleNotFoundError:
    from utils.ui_helper import sidebar_info
    from utils.analysis_helper import (
        get_sample_names_from_software_file,
        read_uploaded_file_into_df,
    )
    from utils.software_options import software_options
    from alphastats import MaxQuantLoader
    from alphastats import DataSet

import pandas as pd
import plotly.express as px
from streamlit.runtime import get_instance
from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

runtime = get_instance()
session_id = get_script_run_ctx().session_id
session_info = runtime._session_mgr.get_session_info(session_id)

user_session_id = session_id
st.session_state["user_session_id"] = user_session_id

if "loader" not in st.session_state:
    st.session_state["loader"] = None

if "gene_to_prot_id" not in st.session_state:
    st.session_state["gene_to_prot_id"] = {}

if "organism" not in st.session_state:
    st.session_state["organism"] = 9606


def load_options():
    from alphastats.gui.utils.options import plotting_options, statistic_options

    st.session_state["plotting_options"] = plotting_options
    st.session_state["statistic_options"] = statistic_options


def check_software_file(df, software):
    """
    check if software files are in right format
    can be fragile when different settings are used or software is updated
    """

    if software == "MaxQuant":
        expected_columns = ["Protein IDs", "Reverse", "Potential contaminant"]
        if not set(expected_columns).issubset(set(df.columns.to_list())):
            st.error(
                "This is not a valid MaxQuant file. Please check:"
                "http://www.coxdocs.org/doku.php?id=maxquant:table:proteingrouptable"
            )

    elif software == "AlphaPept":
        if "object" in df.iloc[:, 1:].dtypes.to_list():
            st.error("This is not a valid AlphaPept file.")

    elif software == "DIANN":
        expected_columns = [
            "Protein.Group",
        ]

        if not set(expected_columns).issubset(set(df.columns.to_list())):
            st.error("This is not a valid DIA-NN file.")

    elif software == "Spectronaut":
        expected_columns = [
            "PG.ProteinGroups",
        ]

        if not set(expected_columns).issubset(set(df.columns.to_list())):
            st.error("This is not a valid Spectronaut file.")

    elif software == "FragPipe":
        expected_columns = ["Protein"]
        if not set(expected_columns).issubset(set(df.columns.to_list())):
            st.error(
                "This is not a valid FragPipe file. Please check:"
                "https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_outputs.html#combined_proteintsv"
            )


def select_columns_for_loaders(software, software_df: None):
    """
    select intensity and index column depending on software
    will be saved in session state
    """
    st.write("\n\n")
    st.markdown("### 2. Select columns used for further analysis.")
    st.markdown("Select intensity columns for further analysis")

    if software != "Other":
        st.selectbox(
            "Intensity Column",
            options=software_options.get(software).get("intensity_column"),
            key="intensity_column",
        )

        st.markdown("Select index column (with ProteinGroups) for further analysis")

        st.selectbox(
            "Index Column",
            options=software_options.get(software).get("index_column"),
            key="index_column",
        )

    else:
        st.multiselect(
            "Intensity Columns",
            options=software_df.columns.to_list(),
            key="intensity_column",
        )

        st.markdown("Select index column (with ProteinGroups) for further analysis")

        st.selectbox(
            "Index Column",
            options=software_df.columns.to_list(),
            key="index_column",
        )


def load_proteomics_data(uploaded_file, intensity_column, index_column, software):
    """load software file into loader object from alphastats"""
    loader = software_options.get(software)["loader_function"](
        uploaded_file, intensity_column, index_column
    )
    return loader


def select_sample_column_metadata(df, software):
    samples_proteomics_data = get_sample_names_from_software_file()
    valid_sample_columns = []

    for col in df.columns.to_list():
        if bool(set(samples_proteomics_data) & set(df[col].to_list())):
            valid_sample_columns.append(col)

    if len(valid_sample_columns) == 0:
        st.error(
            f"Metadata does not match Proteomics data."
            f"Information for the samples: {samples_proteomics_data} is required."
        )

    st.write(
        "Select column that contains sample IDs matching the sample names described "
        + f"in {software_options.get(software).get('import_file')}"
    )

    with st.form("sample_column"):
        st.selectbox("Sample Column", options=valid_sample_columns, key="sample_column")
        submitted = st.form_submit_button("Create DataSet")

    if submitted:
        if len(df[st.session_state.sample_column].to_list()) != len(
            df[st.session_state.sample_column].unique()
        ):
            st.error("Sample names have to be unique.")
            st.stop()
        return True


def upload_softwarefile(software):
    softwarefile = st.file_uploader(
        software_options.get(software).get("import_file"),
        type=["csv", "tsv", "txt", "hdf"],
    )

    if softwarefile is not None:
        softwarefile_df = read_uploaded_file_into_df(softwarefile)
        # display head a protein data

        check_software_file(softwarefile_df, software)

        st.write(
            f"File successfully uploaded. Number of rows: {softwarefile_df.shape[0]}"
            f", Number of columns: {softwarefile_df.shape[1]}.\nPreview:"
        )
        st.dataframe(softwarefile_df.head(5))

        select_columns_for_loaders(software=software, software_df=softwarefile_df)

        if (
            "intensity_column" in st.session_state
            and "index_column" in st.session_state
        ):
            loader = load_proteomics_data(
                softwarefile_df,
                intensity_column=st.session_state.intensity_column,
                index_column=st.session_state.index_column,
                software=software,
            )
            st.session_state["loader"] = loader


def create_metadata_file():
    dataset = DataSet(loader=st.session_state.loader)
    st.session_state["metadata_columns"] = ["sample"]
    metadata = dataset.metadata
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # Write each dataframe to a different worksheet.
        metadata.to_excel(writer, sheet_name="Sheet1", index=False)

        st.download_button(
            label="Download metadata template as Excel",
            data=buffer,
            file_name="metadata.xlsx",
            mime="application/vnd.ms-excel",
        )


def upload_metadatafile(software):
    st.write("\n\n")
    st.markdown("### 3. Prepare Metadata.")
    metadatafile_upload = st.file_uploader(
        "Upload metadata file. with information about your samples",
        key="metadatafile",
    )

    if metadatafile_upload is not None and st.session_state.loader is not None:
        metadatafile_df = read_uploaded_file_into_df(st.session_state.metadatafile)
        # display metadata
        st.write(
            f"File successfully uploaded. Number of rows: {metadatafile_df.shape[0]}"
            f", Number of columns: {metadatafile_df.shape[1]}. \nPreview:"
        )
        st.dataframe(metadatafile_df.head(5))
        # pick sample column

        if select_sample_column_metadata(metadatafile_df, software):
            # create dataset
            st.session_state["dataset"] = DataSet(
                loader=st.session_state.loader,
                metadata_path=metadatafile_df,
                sample_column=st.session_state.sample_column,
            )
            st.session_state["metadata_columns"] = metadatafile_df.columns.to_list()
            load_options()

    if st.session_state.loader is not None:
        create_metadata_file()
        st.write(
            "Download the template file and add additional information as "
            + "columns to your samples such as disease group. "
            + "Upload the updated metadata file."
        )

    if st.session_state.loader is not None:
        if st.button("Create a DataSet without metadata"):
            st.session_state["dataset"] = DataSet(loader=st.session_state.loader)
            st.session_state["metadata_columns"] = ["sample"]

            load_options()


def load_sample_data():
    _this_file = os.path.abspath(__file__)
    _this_directory = os.path.dirname(_this_file)
    _parent_directory = os.path.dirname(_this_directory)
    folder_to_load = os.path.join(_parent_directory, "sample_data")

    filepath = os.path.join(folder_to_load, "proteinGroups.txt")
    metadatapath = os.path.join(folder_to_load, "metadata.xlsx")

    loader = MaxQuantLoader(file=filepath)
    ds = DataSet(loader=loader, metadata_path=metadatapath, sample_column="sample")
    metadatapath = (
        os.path.join(_this_directory, "sample_data", "metadata.xlsx")
        .replace("pages/", "")
        .replace("pages\\", "")
    )

    loader = MaxQuantLoader(file=filepath)
    ds = DataSet(loader=loader, metadata_path=metadatapath, sample_column="sample")

    ds.metadata = ds.metadata[
        [
            "sample",
            "disease",
            "Drug therapy (procedure) (416608005)",
            "Lipid-lowering therapy (134350008)",
        ]
    ]
    ds.preprocess(subset=True)
    st.session_state["loader"] = loader
    st.session_state["metadata_columns"] = ds.metadata.columns.to_list()
    st.session_state["dataset"] = ds

    load_options()


def import_data():
    options = ["<select>"] + list(software_options.keys())

    st.selectbox(
        "Select your Proteomics Software",
        options=options,
        key="software",
    )

    if st.session_state.software != "<select>":
        upload_softwarefile(software=st.session_state.software)
    if "loader" not in st.session_state:
        st.session_state["loader"] = None
    if st.session_state.loader is not None:
        upload_metadatafile(st.session_state.software)


def display_loaded_dataset():
    st.info("Data was successfully imported")
    st.info("DataSet has been created")

    st.markdown(f"*Preview:* Raw data from {st.session_state.dataset.software}")
    st.dataframe(st.session_state.dataset.rawinput.head(5))

    st.markdown("*Preview:* Metadata")
    st.dataframe(st.session_state.dataset.metadata.head(5))

    st.markdown("*Preview:* Matrix")

    df = pd.DataFrame(
        st.session_state.dataset.mat.values,
        index=st.session_state.dataset.mat.index.to_list(),
    ).head(5)

    st.dataframe(df)


def save_plot_sampledistribution_rawdata():
    df = st.session_state.dataset.rawmat
    df = df.unstack().reset_index()
    df.rename(
        columns={"level_1": st.session_state.dataset.sample, 0: "Intensity"},
        inplace=True,
    )
    st.session_state["distribution_plot"] = px.violin(
        df, x=st.session_state.dataset.sample, y="Intensity"
    )


def empty_session_state():
    """
    remove all variables to avoid conflicts
    """
    for key in st.session_state.keys():
        del st.session_state[key]
    st.empty()
    st.session_state["software"] = "<select>"

    from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx

    user_session_id = get_script_run_ctx().session_id
    st.session_state["user_session_id"] = user_session_id


sidebar_info()


if "dataset" not in st.session_state:
    st.markdown("### Import Proteomics Data")

    st.markdown(
        "Create a DataSet with the output of your proteomics software package and the corresponding metadata (optional). "
    )

import_data()

if "dataset" in st.session_state:
    st.info("DataSet has been imported")

    if "distribution_plot" not in st.session_state:
        save_plot_sampledistribution_rawdata()

    display_loaded_dataset()

st.markdown("### Or Load sample Dataset")

if st.button("Load sample DataSet - PXD011839"):
    st.write(
        """

    ### Plasma proteome profiling discovers novel proteins associated with non-alcoholic fatty liver disease

    **Description**

    Non-alcoholic fatty liver disease (NAFLD) affects 25 percent of the population and can progress to cirrhosis, 
    where treatment options are limited. As the liver secrets most of the blood plasma proteins its diseases 
    should affect the plasma proteome. Plasma proteome profiling on 48 patients with cirrhosis or NAFLD with 
    normal glucose tolerance or diabetes, revealed 8 significantly changing (ALDOB, APOM, LGALS3BP, PIGR, VTN, 
    IGHD, FCGBP and AFM), two of which are already linked to liver disease. Polymeric immunoglobulin receptor (PIGR) 
    was significantly elevated in both cohorts with a 2.7-fold expression change in NAFLD and 4-fold change in 
    cirrhosis and was further validated in mouse models. Furthermore, a global correlation map of clinical and 
    proteomic data strongly associated DPP4, ANPEP, TGFBI, PIGR, and APOE to NAFLD and cirrhosis. DPP4 is a known 
    drug target in diabetes. ANPEP and TGFBI are of interest because of their potential role in extracellular matrix 
    remodeling in fibrosis.

    **Publication**

    Niu L, Geyer PE, Wewer Albrechtsen NJ, Gluud LL, Santos A, Doll S, Treit PV, Holst JJ, Knop FK, Vilsbøll T, Junker A, 
    Sachs S, Stemmer K, Müller TD, Tschöp MH, Hofmann SM, Mann M, Plasma proteome profiling discovers novel proteins 
    associated with non-alcoholic fatty liver disease. Mol Syst Biol, 15(3):e8793(2019)
    """
    )

    load_sample_data()


st.markdown("### To start a new session:")

if st.button("New Session: Import new dataset"):
    empty_session_state()
    st.rerun()
