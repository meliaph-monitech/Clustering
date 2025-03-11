# -*- coding: utf-8 -*-
"""WORK_250311_ClusteringUI.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1aGMp4pLUuCeh0GOyzS3i3iXfcE2ChGPg
"""

import streamlit as st
import zipfile
import os
import pandas as pd
import plotly.express as px
from sklearn.cluster import KMeans
from sklearn.preprocessing import RobustScaler
from sklearn.decomposition import PCA
import numpy as np
from collections import defaultdict

def extract_zip(zip_path, extract_dir="extracted_csvs"):
    if os.path.exists(extract_dir):
        for file in os.listdir(extract_dir):
            os.remove(os.path.join(extract_dir, file))
    else:
        os.makedirs(extract_dir)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except zipfile.BadZipFile:
        st.error("The uploaded file is not a valid ZIP file.")
        st.stop()

    csv_files = [f for f in os.listdir(extract_dir) if f.endswith('.csv')]
    if not csv_files:
        st.error("No CSV files found in the ZIP file.")
        st.stop()

    return [os.path.join(extract_dir, f) for f in csv_files], extract_dir

def segment_beads(df, column, threshold):
    start_indices = []
    end_indices = []
    signal = df[column].to_numpy()
    i = 0
    while i < len(signal):
        if signal[i] > threshold:
            start = i
            while i < len(signal) and signal[i] > threshold:
                i += 1
            end = i - 1
            start_indices.append(start)
            end_indices.append(end)
        else:
            i += 1
    return list(zip(start_indices, end_indices))

def extract_features(signal):
    if len(signal) == 0:
        return [0] * 10
    return [
        np.mean(signal), np.std(signal), np.min(signal), np.max(signal),
        np.median(signal), np.max(signal) - np.min(signal),
        np.sum(signal**2), np.sqrt(np.mean(signal**2)),
        np.percentile(signal, 25), np.percentile(signal, 75)
    ]

st.set_page_config(layout="wide")
st.title("Laser Welding Clustering Analysis")

with st.sidebar:
    uploaded_file = st.file_uploader("Upload a ZIP file containing CSV files", type=["zip"])
    if uploaded_file:
        with open("temp.zip", "wb") as f:
            f.write(uploaded_file.getbuffer())
        csv_files, extract_dir = extract_zip("temp.zip")
        st.success(f"Extracted {len(csv_files)} CSV files")

        df_sample = pd.read_csv(csv_files[0])
        columns = df_sample.columns.tolist()
        filter_column = st.selectbox("Select column for filtering", columns)
        threshold = st.number_input("Enter filtering threshold", value=0.0)

        num_clusters = st.slider("Select number of clusters", min_value=2, max_value=20, value=3)

        if st.button("Segment Beads"):
            with st.spinner("Segmenting beads..."):
                bead_segments = {}
                metadata = []
                for file in csv_files:
                    df = pd.read_csv(file)
                    segments = segment_beads(df, filter_column, threshold)
                    if segments:
                        bead_segments[file] = segments
                        for bead_num, (start, end) in enumerate(segments, start=1):
                            metadata.append({"file": file, "bead_number": bead_num, "start_index": start, "end_index": end})
                st.success("Bead segmentation complete")
                st.session_state["metadata"] = metadata

        if st.button("Run K-Means Clustering") and "metadata" in st.session_state:
            with st.spinner("Running K-Means Clustering..."):
                features_by_bead = []
                files_info = []

                for entry in st.session_state["metadata"]:
                    df = pd.read_csv(entry["file"])
                    bead_segment = df.iloc[entry["start_index"]:entry["end_index"] + 1]
                    features = extract_features(bead_segment.iloc[:, 0].values)
                    features_by_bead.append(features)
                    files_info.append((entry["file"], entry["bead_number"]))

                scaler = RobustScaler()
                scaled_features = scaler.fit_transform(features_by_bead)

                kmeans = KMeans(n_clusters=num_clusters, random_state=42)
                clusters = kmeans.fit_predict(scaled_features)

                pca = PCA(n_components=2)
                reduced_features = pca.fit_transform(scaled_features)

                results_df = pd.DataFrame({
                    "File Name": [info[0] for info in files_info],
                    "Bead Number": [info[1] for info in files_info],
                    "Cluster": clusters,
                    "PCA1": reduced_features[:, 0],
                    "PCA2": reduced_features[:, 1]
                })

                st.session_state["clustering_results"] = results_df
                st.success("Clustering completed!")

if "clustering_results" in st.session_state:
    if st.button("Download Results"):
        csv_data = st.session_state["clustering_results"].to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv_data, file_name="clustering_results.csv", mime="text/csv")

    st.write("## Visualization")
    sorted_results_df = st.session_state["clustering_results"].sort_values("Cluster")

    # Define a color palette with distinct colors for each cluster
    cluster_colors = px.colors.qualitative.Set1  # You can change this palette to your liking
    
    # Ensure there are enough colors for all clusters (repeat if necessary)
    if len(cluster_colors) < sorted_results_df["Cluster"].nunique():
        cluster_colors = cluster_colors * (sorted_results_df["Cluster"].nunique() // len(cluster_colors) + 1)
    
    # Convert clusters to string type (important for discrete mapping)
    sorted_results_df["Cluster"] = sorted_results_df["Cluster"].astype(str)
    
    # Plot the scatter plot with distinct colors for each cluster
    fig = px.scatter(
        sorted_results_df,
        x="PCA1", y="PCA2", color="Cluster", 
        hover_data=["File Name", "Bead Number", "Cluster"],
        title="K-Means Clustering Visualization (PCA Reduced)",
        color_discrete_map={str(i): cluster_colors[i] for i in sorted_results_df["Cluster"].unique()},
    )
    st.plotly_chart(fig)
