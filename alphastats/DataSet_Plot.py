from audioop import add
import sklearn
import logging
import plotly.express as px
import plotly
import scipy
import sklearn.manifold
from alphastats.utils import ignore_warning, check_for_missing_values
import plotly.graph_objects as go
import numpy as np
import plotly.figure_factory as ff
import seaborn as sns
import pandas as pd
from scipy.spatial.distance import pdist, squareform
import random

# make own alphastats theme
plotly.io.templates["alphastats_colors"] = plotly.graph_objects.layout.Template(
    layout=plotly.graph_objects.Layout(
        colorway=[
            "#009599",
            "#005358",
            "#772173",
            "#B65EAF",  # pink
            "#A73A00",
            "#6490C1",
            "#FF894F",
            "#2B5E8B",
            "#A87F32",
        ]
    )
)

plotly.io.templates.default = "simple_white+alphastats_colors"


class plotly_object(plotly.graph_objs._figure.Figure):
    plotting_data = None
    preprocessing = None
    method = None


class seaborn_object(plotly.graph_objs._figure.Figure):
    plotting_data = None
    preprocessing = None
    method = None


class Plot:
    @staticmethod
    def _update_colors_plotly(fig, color_dict):
        #  plotly doesnt allow to assign color to certain group
        # update instead the figure in form of a dict
        # color_dict with group_variable/legendgroup as key, and corresponding color as value
        fig_dict = fig.to_plotly_json()
        data_dict_list = fig_dict.get("data")
        for count, group in enumerate(data_dict_list):
            group_variable = group.get("legendgroup")
            group_color = color_dict.get(group_variable)
            fig_dict["data"][count]["marker"]["color"] = group_color
        # convert dict back to plotly figure
        return go.Figure(fig_dict)

    @staticmethod
    def _add_circles_to_scatterplot(fig):
        # called by _plot_dimensionality_reduction()
        # convert figure to dict and extract information
        fig_dict = fig.to_plotly_json().get("data")
        for group in fig_dict:
            # get coordinates for the group
            x_vector = group.get("x")
            y_vector = group.get("y")
            # get color of the group to color circle in the same color
            group_color = group.get("marker").get("color")
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=min(x_vector),
                y0=min(y_vector),
                x1=max(x_vector),
                y1=max(y_vector),
                opacity=0.2,
                fillcolor=group_color,
                line_color=group_color,
            )
        return fig

    def _update_figure_attributes(self, figure_object, plotting_data, method=None):
        setattr(figure_object, "plotting_data", plotting_data)
        setattr(figure_object, "preprocessing", self.preprocessing_info)
        setattr(figure_object, "method", method)
        return figure_object

    @check_for_missing_values
    def _plot_dimensionality_reduction(self, group, method, circle, **kwargs):
        # function for plot_pca and plot_tsne
        # subset matrix so it matches with metadata
        if group:
            mat = self._subset()
            self.metadata[group] = self.metadata[group].apply(str)
            group_color = self.metadata[group]
        else:
            mat = self.mat
            group_color = group
        mat = mat.fillna(0)

        if method == "pca":
            pca = sklearn.decomposition.PCA(n_components=2)
            components = pca.fit_transform(mat)
            labels = {
                "0": "PC 1 (%.2f%%)" % (pca.explained_variance_ratio_[0] * 100),
                "1": "PC 2 (%.2f%%)" % (pca.explained_variance_ratio_[1] * 100),
            }

        elif method == "tsne":
            tsne = sklearn.manifold.TSNE(n_components=2, verbose=1, **kwargs)
            components = tsne.fit_transform(mat)
            labels = {
                "0": "Dimension 1",
                "1": "Dimension 2",
            }

        else:
            # TODO implement UMAP??
            return

        fig = px.scatter(components, x=0, y=1, labels=labels, color=group_color,)
        #  save plotting data in figure object
        fig = plotly_object(fig)
        fig = self._update_figure_attributes(
            figure_object=fig, plotting_data=pd.DataFrame(components), method=method
        )

        # draw circles around plotted groups
        if circle is True and group is not None:
            fig = self._add_circles_to_scatterplot(fig)

        return fig

    def plot_pca(self, group=None, circle=False):
        """Plot Principal Component Analysis (PCA)

        Args:
            group (str, optional): column in metadata that should be used for coloring. Defaults to None.
            circle (bool, optional): draw circle around each group. Defaults to False.

        Returns:
            plotly.graph_objects._figure.Figure: PCA plot
        """
        return self._plot_dimensionality_reduction(
            group=group, method="pca", circle=circle
        )

    def plot_tsne(self, group=None, circle=False, perplexity=30, n_iter=1000):
        """Plot t-distributed stochastic neighbor embedding (t-SNE)

        Args:
            group (str, optional): column in metadata that should be used for coloring. Defaults to None.
            circle (bool, optional): draw circle around each group. Defaults to False.

        Returns:
            plotly.graph_objects._figure.Figure: t-SNE plot
        """
        return self._plot_dimensionality_reduction(
            group=group,
            method="tsne",
            circle=circle,
            perplexity=perplexity,
            n_iter=n_iter,
        )

    def plot_correlation_matrix(self, method="pearson"):
        """Plot Correlation Matrix

        Args:
            method (str, optional): orrelation coefficient "pearson", "kendall" (Kendall Tau correlation) 
            or "spearman" (Spearman rank correlation). Defaults to "pearson".

        Returns:
            plotly.graph_objects._figure.Figure: Correlation matrix
        """
        corr_matrix = self.mat.transpose().corr(method=method)
        plot = px.imshow(corr_matrix)
        return plot

    def plot_sampledistribution(self, method="violin", color=None, log_scale=False):
        """Plot Intensity Distribution for each sample. Either Violin or Boxplot

        Args:
            method (str, optional): Violinplot = "violin", Boxplot = "box". Defaults to "violin".
            color (_type_, optional): A metadata column used to color the boxes. Defaults to None.
            log_scale (bool, optional): yaxis in logarithmic scale. Defaults to False.

        Returns:
             plotly.graph_objects._figure.Figure: Plotly Sample Distribution Plot
        """

        # create long df
        df = self.mat.unstack().reset_index()
        df.rename(columns={"level_1": "sample", 0: "Intensity"}, inplace=True)

        if color is not None:
            df = df.merge(self.metadata, how="inner", on=["sample"])

        if method == "violin":
            fig = px.violin(df, x="sample", y="Intensity", color=color)

        elif method == "box":
            fig = px.box(df, x="sample", y="Intensity", color=color)

        else:
            raise ValueError(
                f"{method} is not available."
                + "Please select from 'violin' for Violinplot or 'box' for Boxplot."
            )

        if log_scale:
            fig.update_layout(yaxis=dict(type="log"))
        return fig

    def plot_intensity(self, id, group=None, method="violin", log_scale=False):
        """Plot Intensity of individual Protein/ProteinGroup 

        Args:
            id (str): ProteinGroup ID
            group (str, optional): A metadata column used for grouping. Defaults to None.
            method (str, optional):  Violinplot = "violin", Boxplot = "box", Scatterplot = "scatter". Defaults to "violin".
            log_scale (bool, optional): yaxis in logarithmic scale. Defaults to False.

        Returns:
            plotly.graph_objects._figure.Figure: Plotly Plot
        """
        #  TODO use difflib to find similar ProteinId if ProteinGroup is not present
        df = self.mat[[id]].reset_index().rename(columns={"index": "sample"})
        df = df.merge(self.metadata, how="inner", on=["sample"])

        if method == "violin":
            fig = px.violin(df, x=id, y=group, color=group)

        elif method == "box":
            fig = px.box(df, x=id, y=group, color=group)

        elif method == "scatter":
            fig = px.scatter(df, x=id, y=group, color=group)

        else:
            raise ValueError(
                f"{method} is not available."
                + "Please select from 'violin' for Violinplot, 'box' for Boxplot and 'scatter' for Scatterplot."
            )

        if log_scale:
            fig.update_layout(yaxis=dict(type="log"))

        return fig

    @ignore_warning(RuntimeWarning)
    def plot_volcano(self, column, group1, group2, method="anova"):
        """Plot Volcano Plot

        Args:
            column (str): column name in the metadata file with the two groups to compare
            group1 (str): name of group to compare needs to be present in column
            group2 (str): name of group to compare needs to be present in column
            method: "anova", "wald", "ttest"

        Returns:
            plotly.graph_objects._figure.Figure: Volcano Plot
        """
        if method == "wald":
            print(
                "Calculating differential expression analysis using wald test. Fitting generalized linear model..."
            )
            result = self.perform_diff_expression_analysis(column, group1, group2)
            pvalue_column = "qval"

        elif method == "ttest":
            print("Calculating t-test...")
            result = self.calculate_ttest_fc(column, group1, group2)
            pvalue_column = "pvalue"

        elif method == "anova":
            print("Calculating ANOVA with follow-up tukey test...")
            result = self.anova(column=column, protein_ids="all", tukey=True)
            group1_samples = self.metadata[self.metadata[column] == group1][
                "sample"
            ].tolist()
            group2_samples = self.metadata[self.metadata[column] == group2][
                "sample"
            ].tolist()
            mat_transpose = self.mat.transpose()
            fc = self._calculate_foldchange(
                mat_transpose, group1_samples, group2_samples
            )

            #  check how column is ordered
            pvalue_column = group1 + " vs. " + group2 + " Tukey Test"
            if pvalue_column not in fc.columns:
                pvalue_column = group2 + " vs. " + group1 + " Tukey Test"

            result = result.reset_index().merge(fc.reset_index(), on=self.index_column)

        else:
            raise ValueError(
                f"{method} is not available."
                + "Please select from 'ttest' or 'anova' for anova with follow up tukey or 'wald' for wald-test using."
            )

        result = result[(result["log2fc"] < 10) & (result["log2fc"] > -10)]
        result["-log10(p-value)"] = -np.log10(result[pvalue_column])

        # add color variable to plot
        condition = [
            (result["log2fc"] < -1) & (result["-log10(p-value)"] > 1),
            (result["log2fc"] > 1) & (result["-log10(p-value)"] > 1),
        ]
        value = ["down", "up"]
        result["color"] = np.select(condition, value, default="non-significant")

        # create volcano plot
        volcano_plot = px.scatter(
            result,
            x="log2fc",
            y="-log10(p-value)",
            color="color",
            hover_data=[self.index_column],
        )

        #  save plotting data in figure object
        volcano_plot = plotly_object(volcano_plot)
        volcano_plot = self._update_figure_attributes(
            figure_object=volcano_plot, plotting_data=result, method=method
        )

        # update coloring
        color_dict = {"non-significant": "#404040", "up": "#B65EAF", "down": "#009599"}
        volcano_plot = self._update_colors_plotly(volcano_plot, color_dict=color_dict)
        volcano_plot.update_layout(showlegend=False)
        return volcano_plot

    def _clustermap_get_colors_for_bar(self, columnname, color) -> pd.Series:
        s = self.metadata[columnname]
        su = s.unique()
        colors = sns.light_palette(color, len(su))
        lut = dict(zip(su, colors))
        return s.map(lut)

    def _clustermap_create_label_bar(self, list_of_labels):
        label_colors = []
        colorway = [
            "#009599",
            "#005358",
            "#772173",
            "#B65EAF",
            "#A73A00",
            "#6490C1",
            "#FF894F",
        ]
        for label in list_of_labels:
            color_label = self._clustermap_get_colors_for_bar(
                columnname=label, color=random.choice(colorway)
            )
            label_colors.append(color_label)
        return label_colors

    @check_for_missing_values
    def plot_clustermap(self, label_bar=None):
        """Plot clustermap with samples as columns and Proteins as rows

        Args:
            label_bar (list, optional): List of columns/variables names described in the metadata. Will be plotted as bar above the heatmap to see wheteher groups are clustering together. Defaults to None.

        Returns:
            ClusterGrid: Clustermap
        """
        if label_bar is not None:
            label_bar = self._clustermap_create_label_bar(label_bar)

        fig = sns.clustermap(self.mat.transpose(), col_colors=label_bar)
        return fig

    @check_for_missing_values
    def plot_dendogram(
        self, linkagefun=lambda x: scipy.cluster.hierarchy.linkage(x, "complete")
    ):
        """Plot Hierarichical Clustering Dendogram. This is a wrapper around: 
        https://plotly.com/python-api-reference/generated/plotly.figure_factory.create_dendrogram.html

        Args:
            linkagefun (_type_, optional): Function to compute the linkage matrix from
                               the pairwise distance. Defaults to lambdax:scipy.cluster.hierarchy.linkage(x, "complete").

        Raises:
            ValueError: If data contains missing values, is not imputed

        Returns:
            plotly.figure_factory.create_dendrogram: dendrogram Plotly figure object
        """
        # of anova results
        # general of a subset of proteins
        fig = plotly.figure_factory.create_dendrogram(
            self.mat, labels=self.mat.index, linkagefun=linkagefun
        )
        return fig

    # def plot_line(self):
    #   pass

    # def plot_upset(self):
    #    pass
    # Plotly update figures
    # https://maegul.gitbooks.io/resguides-plotly/content/content/plotting_locally_and_offline/python/methods_for_updating_the_figure_or_graph_objects.html
