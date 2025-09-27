import pandas as pd
import numpy as np

import sys

sys.path.append("/home/marja/Documents/phd/Projects/tsflex")

from tsflex.features import (
    FeatureDescriptor,
    FeatureCollection,
    FuncWrapper,
    MultipleFeatureDescriptors,
)
from tsflex.features.utils import make_robust


def is_on_table(df: pd.DataFrame):

    fc_std = FeatureCollection(
        feature_descriptors=[
            FeatureDescriptor(make_robust(np.std), "ACC_x", "1s", "0.5s"),
            FeatureDescriptor(make_robust(np.std), "ACC_y", "1s", "0.5s"),
            FeatureDescriptor(make_robust(np.std), "ACC_z", "1s", "0.5s"),
        ]
    )
    fc_mean = FeatureCollection(
        feature_descriptors=[
            FeatureDescriptor(make_robust(np.mean), "ACC_x", "1s", "0.5s"),
            FeatureDescriptor(make_robust(np.mean), "ACC_y", "1s", "0.5s"),
            FeatureDescriptor(make_robust(np.mean), "ACC_z", "1s", "0.5s"),
        ]
    )

    feat_std = fc_std.calculate(df, return_df=True, approve_sparsity=True)
    feat_mean = fc_mean.calculate(df, return_df=True, approve_sparsity=True)

    feat_mean["filter_x_mean"] = feat_mean["ACC_x__mean__w=1s"]
    feat_mean["filter_y_mean"] = feat_mean["ACC_y__mean__w=1s"]
    feat_mean["filter_z_mean"] = feat_mean["ACC_z__mean__w=1s"]

    feat_std["filter_x_std"] = feat_std["ACC_x__std__w=1s"]
    feat_std["filter_y_std"] = feat_std["ACC_y__std__w=1s"]
    feat_std["filter_z_std"] = feat_std["ACC_z__std__w=1s"]

    feat_std["is_on_table"] = (
        (feat_std["filter_x_std"] < 0.7)
        & (feat_std["filter_y_std"] < 0.7)
        & (feat_std["filter_z_std"] < 0.7)
        & ((feat_mean["filter_z_mean"] > 9) | (feat_mean["filter_z_mean"] < -9))
    )

    feat_std["is_on_table"] = feat_std["is_on_table"].astype(int)

    return feat_std


def filter_out_on_table(df: pd.DataFrame):

    on_table = is_on_table(df)

    start_indices = on_table.loc[
        (on_table.is_on_table.diff() != 0) & (on_table.is_on_table == 0)
    ].index
    end_indices = on_table.loc[
        (on_table.is_on_table.diff() != 0) & (on_table.is_on_table == 1)
    ].index

    if len(on_table.loc[(on_table.is_on_table.diff() != 0)]) == 1:

        if on_table.iloc[0].is_on_table == 0:
            start_indices = [on_table.iloc[0].name]
            end_indices = [on_table.iloc[-1].name]
            return on_table, start_indices, end_indices

        if on_table.iloc[0].is_on_table == 1:
            return on_table, [], []

    if start_indices[0] > end_indices[0]:
        end_indices = end_indices[1:]

    if on_table.iloc[-1].is_on_table == 0:
        end_indices = np.append(end_indices, [on_table.iloc[-1].name])

    if len(start_indices) != len(end_indices):
        print("Lengths: ")
        print(len(start_indices))
        print(len(end_indices))

    return on_table, start_indices, end_indices
