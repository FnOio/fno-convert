import json
import pyarrow as pa
from functools import reduce

import numpy as np
import pandas as pd
from tsflex.chunking import chunk_data

from is_on_table_lib import is_on_table
from library import rolling_acc
from make_model import make_model


def process_data(conf, events):

    ### take only accelerometer events
    acc_events = events[
        (events["Metric"].str.contains("smartphone"))
        & (events["Metric"].str.contains("acceleration"))
        & (~events["Metric"].str.contains("linear"))
    ]

    print(
        f"Received {len(events)} events - {len(acc_events)} of them are accelerometer data"
    )

    del events

    # Check if there is enough samples
    # *3 is for the three channels, because there is event for each channel
    if len(acc_events) >= 3 * conf["min_duration_s"] * conf["frequency"]:

        ### Get separately x axis from accelerometer
        acc_x = acc_events[acc_events["Metric"].str.contains("x")].copy()

        ### Making DataFrames with columns "timestamp" and "ACC_x"
        ### Sort by timestamp
        acc_x.sort_values(by="Timestamp")
        acc_x.drop(columns=["Metric", "Sensor"], inplace=True)
        acc_x.rename(columns={"Value": "ACC_x"}, inplace=True)

        ### Get separately y axis from accelerometer
        acc_y = acc_events[acc_events["Metric"].str.contains("y")].copy()

        ### Making DataFrames with columns "timestamp" and "ACC_y"
        ### Sort by timestamp
        acc_y.sort_values(by="Timestamp")
        acc_y.drop(columns=["Metric", "Sensor"], inplace=True)
        acc_y.rename(columns={"Value": "ACC_y"}, inplace=True)

        ### Get separately z axis from accelerometer
        acc_z = acc_events[acc_events["Metric"].str.contains("z")].copy()

        ### Making DataFrames with columns "timestamp" and "ACC_z"
        ### Sort by timestamp
        acc_z.sort_values(by="Timestamp")
        acc_z.drop(columns=["Metric", "Sensor"], inplace=True)
        acc_z.rename(columns={"Value": "ACC_z"}, inplace=True)

        ### Merge the three different dfs into one, based on timestamp
        ### TODO: check whether exactly ON or CLOSEST
        data = reduce(
            lambda x, y: pd.merge(x, y, on="Timestamp", how="inner"),
            [acc_x, acc_y, acc_z],
        )

        del acc_x, acc_y, acc_z

        data["Timestamp"] = pd.to_datetime(data["Timestamp"], format="%H:%M:%S.%f")
        data.sort_values(by="Timestamp", inplace=True)

        return data
    else:
        print("Not enough accelerometer data")
        return None, None


def controller(conf, act_dict_inverse, model, data):

    data = process_data(conf, data)
    if data is not None:
        if len(data) > conf["min_duration_s"] * conf["frequency"]:
            print("Received enough data to proceed with making predictions")
            data.set_index("Timestamp", inplace=True)

            fs_dict = {}
            for name in data.columns:
                fs_dict[name] = conf["frequency"]

            chunks = chunk_data(data=data, fs_dict=fs_dict, min_chunk_dur="15s")

            for chunk in chunks:

                chunk_df = reduce(
                    lambda x, y: pd.merge(x, y, on="Timestamp", how="inner"), chunk
                )
                print("start time of chunk is ", str(chunk_df.index[0]))
                print("end time of chunk is ", str(chunk_df.index[-1]))

                if len(chunk_df) >= conf["win_size_s"] * conf["frequency"]:

                    ### Integer values for Value column
                    for col in ["ACC_x", "ACC_y", "ACC_z"]:
                        chunk_df[col] = pd.to_numeric(chunk_df[col], errors="coerce")
                        chunk_df.dropna(subset=[col], inplace=True)
                        chunk_df[col] = chunk_df[col].round().astype(float)

                    # Check if phone is on table
                    on_table_df = is_on_table(chunk_df.copy())
                    counts = np.bincount(
                        np.array(on_table_df.is_on_table.values, dtype="int64")
                    )
                    on_table = np.argmax(counts)

                    # If phone is not on table get class prediction
                    if on_table == 0:

                        chunk_df.loc[:, ["ACC_x", "ACC_y", "ACC_z"]] = (
                            chunk_df.loc[:, ["ACC_x", "ACC_y", "ACC_z"]] / 9.81
                        )

                        x_acc, y_acc, z_acc, timestamps = rolling_acc(
                            chunk_df.copy(),
                            conf["win_size_s"],
                            conf["frequency"],
                            conf["overlap"],
                        )

                        x_acc_df = pd.DataFrame(
                            x_acc,
                            columns=["acc_x_" + str(x) for x in range(len(x_acc[0]))],
                        )
                        y_acc_df = pd.DataFrame(
                            y_acc,
                            columns=["acc_y_" + str(x) for x in range(len(y_acc[0]))],
                        )
                        z_acc_df = pd.DataFrame(
                            z_acc,
                            columns=["acc_z_" + str(x) for x in range(len(z_acc[0]))],
                        )
                        # Save memory
                        x_acc = y_acc = z_acc = None

                        # Make predictions
                        model_input = np.stack([x_acc_df, y_acc_df, z_acc_df], axis=2)

                        del x_acc_df, y_acc_df, z_acc_df

                        predictions = model.predict(model_input)

                        # Take majority class
                        majority_prediction = np.argmax(
                            np.bincount(np.argmax(predictions, axis=1))
                        )
                        final_prediction = act_dict_inverse[majority_prediction]

                    # If phone is on table, set label to OnTable
                    else:
                        final_prediction = "OnTable"

                    chunk_df.reset_index(inplace=True, drop=False)

                    # Get start and end time of activity prediction
                    start_ms = chunk_df.iloc[0].Timestamp.value // 10**6
                    end_ms = chunk_df.iloc[-1].Timestamp.value // 10**6

                    print("Predicted ", final_prediction)
                    print(
                        "Start time %s, End time %s"
                        % (
                            str(pd.to_datetime(start_ms, unit="ms")),
                            str(pd.to_datetime(end_ms, unit="ms")),
                        )
                    )
        else:
            print("Did not receive enough data to proceed with making predictions")
    else:
        print("No data returned")


def run():
    ### Configuration
    conf = {
        "min_duration_s": 16,
        "win_size_s": 15,
        "frequency": 32,
        "overlap": 0.5,
        "amp_sdo": 0.2,
        "amp_do": 0.1,
        "amp_gn": 1.0,
    }

    ### Dictionary for converting model predictions to text
    act_dict = {"Lying": 0, "Running": 1, "Sitting": 2, "Standing": 3, "Walking": 4}

    # TODO Handle dict comprehension
    act_dict_inverse = {}
    for key in act_dict.keys():
        act_dict_inverse[act_dict[key]] = key

    model = make_model(5, conf["amp_sdo"], conf["amp_do"], conf["amp_gn"])

    model.load_weights("nn_protego_full.h5")

    reader = pa.ipc.open_file("data/patient_1.feather")
    for i in range(reader.num_record_batches):
        df = reader.get_batch(i).to_pandas()
        i += 1
        controller(conf, act_dict_inverse, model, df)
