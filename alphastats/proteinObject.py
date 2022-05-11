from random import sample
import re
import pandas as pd
import seaborn as sn
from data_cache import pandas_cache
import os
import warnings
from sklearn.preprocessing import StandardScaler
import plotly.express as px
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
import scipy.stats
import dash_bio
import numpy as np
import logging
from sklearn.impute import SimpleImputer

def check_param(par):
    pass


class proteinObject:
    """_summary_
    """
    def __init__(self, 
        loader, 
        metadata_path: str=None, 
       # intensity_column =  "LFQ intensity ", 
        sample_column = "sample",
       # proteinID_column = "Protein IDs"
        filter_contamination = True):
        """Create a Protein Object containing the protein intensity and the corresponding metadata of the samples,
        ready for analyis 

        Parameters
        ----------
        rawfile_path : str
            path to Protein Intensity file
        metadata_path : str, optional
            path to metadata file (xlsx, csv or tsv), by default None
        intensity_column : str, optional
            , by default None
        software : str, optional
            _description_, by default None
        """
        
        # load data from loader object
        self.rawdata = loader.data
        self.software = loader.software

        # include filtering before 
        self.mat = self.create_matrix()
        self.metadata = None

        if metadata_path:
            self.metadata = self.load_metadata()
        
        self.experiment_type = None
        self.data_format = None
        # save preprocessing settings 
        self.preprocessing = None
        # update normalization when self.matrix is normalized, filtered
        self.normalization = None
        self.removed_protein_groups = None
        self.imputation = None
    

    @pandas_cache
    def create_matrix(self):
        """Creates a matrix out of the MaxQuant ProteinGroup Outputfile, with columns displaying samples and
        row the protein IDs.

        Parameters
        ----------
        df : df
        Pandas Dataframe of the MaxQuant Output ProteinGroup file
        intensity_col : str, optional
        columns , by default "LFQ intensity "
        proteinID_col : str, optional
        column in Dataframe containg the Protein IDs, must be unique, by default "Protein IDs"

        Returns
        -------
        _type_
        _description_
        """
        df = self.rawdata.set_index(self.proteinID_col)
        # check whether column is present print error 
        df = df[df.columns[pd.Series(df.columns).str.startswith(self.intensity_col)]]
        # remove prefix
        df.columns = df.columns.str.lstrip(self.intensity_col)
        self.mat = df
        self.normalization = None
        self.imputation = None
        self.removed_protein_groups = None


    @pandas_cache
    def preprocess(self, 
        normalization = None, 
        contamination_columns = ["Only identified by site", "Reverse", "Potential contaminant"], # needs to be changed when using different loaders
        remove_samples = None,
        impute = False):
        # main function which calls all subfunction to clean according to cleaning "standards"
        # Creates a matrix out of the MS Outputfile, with columns displaying samples androw the protein IDs.
        # intensity_col : str, optional
        #columns , by default "LFQ intensity "
     
        #column in Dataframe containg the Protein IDs, must be unique, by default "Protein IDs"
        if len(contamination_columns) > 0:
            # + == contamination
            protein_groups_to_remove = self.rawdata[(self.rawdata[contamination_columns] != "+").any(1)][self.proteinID_col].tolist()
            self.mat = self.drop(protein_groups_to_remove)
            self.removed_protein_groups = protein_groups_to_remove
            logging.info(len(protein_groups_to_remove), " observations have been removed.")
 
        if normalization is not None:
            self.mat = normalization.normalize_data(self.mat, method=normalization, normalize='samples', max_iterations=250, linear_method='l1')
            self.normalization = normalization

        if impute:
            imp = SimpleImputer(missing_values=np.nan, strategy='mean')
            imp.fit(self.mat.values)
            imputation_array = imp.transform(self.mat.values)
            # https://scikit-learn.org/stable/modules/impute.html
            self.mat = pd.DataFrame(imputation_array, index=self.mat.index, columns=self.mat.columns)
            self.imputation = "Missing values were imputed using the mean."


    def load_metadata(file_path, sample_column = None):
        # loading file needs to be more beautiful
        if file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
            # find robust way to detect file format
            # else give file separation as variable
        elif file_path.endswith(".txt")  or  file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, delimiter = "\t")
        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = None
            logging.warn("WARNING: Metadata could not be read. \nMetadata has to be a .xslx, .tsv, .csv or .txt file")
            return
            
        df.columns = df.columns.str.replace(sample_column, 'sample')
            # check whether sample labeling matches protein data
            #  warnings.warn("WARNING: Sample names do not match sample labelling in protein data")
        return df   


    def summary(self):
        """_summary_

        Returns
        -------
        _type_
            _description_
        """
        # print summary
        # look at keras model.summary()
        pass


    def calculate_ttest_fc(self, column, group1, group2):
        """_summary_

        Args:
            column (_type_): _description_
            group1 (_type_): _description_
            group2 (_type_): _description_

        Returns:
            _type_: _description_
        """
        # get samples names of two groupes
        group1_samples = self.metadata[self.metadata[column] == group1]["sample"].tolist()
        group2_samples = self.metadata[self.metadata[column] == group2]["sample"].tolist()
        # calculate fold change (if its is not logarithimic normalized)
        if self.normalization != "log":
            fc = self.mat[group1_samples].T.mean().values/self.mat[group2_samples].T.mean().values
    
        # calculate p-values 
        # output needs to be checked
        p_values = self.mat.apply(lambda row: scipy.stats.ttest_ind(row[group1_samples].values.flatten(), row[group2_samples].values.flatten())[1], axis = 1)
        df = pd.DataFrame()
        df["Protein IDs"] = p_values.index.tolist()
        df["fc"] = fc
        df["fc_log2"] = np.log2(fc)
        df["pvalue"] = p_values.values
        return df.dropna()


    def plot_pca(self, group = None):
        """plot PCA

        Parameters
        ----------
        group : _type_, optional
            _description_, by default None
        """
        if group: 
            mat = self.mat[self.metadata["sample"].tolist()]
        else:
            mat = self.mat

        # needs to be checked with publications
        # depends on normalization whether NA can be replaced with 0  
        if self.imputation is None and self.mat.isna().values.any():
            logging.warn("Data contains missing values. Consider Imputation ")
        mat = mat.fillna(0) # print warning depending on imputatio
        pipeline = Pipeline([('scaling', StandardScaler()), ('pca', PCA(n_components=2))])
        components = pipeline.fit_transform(mat.transpose())
    
        if group:
            fig = px.scatter(components, x=0, y=1, color = self.metadata[group])
        else:
            fig = px.scatter(components, x=0, y=1)
        return fig


    def plot_correlation_matrix(self, corr_method = "pearson", save_figure=False):
        """_summary_

        Parameters
        ----------
        corr_method : str, optional
            _description_, by default "pearson"
        save_figure : bool, optional
            _description_, by default False

        Returns
        -------
        _type_
            _description_
        """
        corr_matrix = self.mat.corr(method=corr_method)
        plot = px.imshow(corr_matrix)
        return plot
    

    def plot_volcano(self, column, group1, group2):
        result = self.calculate_ttest_fc(column, group1, group2)
        volcano_plot = dash_bio.VolcanoPlot(dataframe = result, 
            effect_size = "fc_log2", 
            p = "pvalue", 
            gene = None, snp = None, annotation = "Protein IDs")
        return volcano_plot













