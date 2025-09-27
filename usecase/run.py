from warnings import filterwarnings
import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import StratifiedKFold
import pytorch_lightning as pl
from pytorch_lightning.callbacks import (
    LearningRateMonitor,
    TQDMProgressBar,
    StochasticWeightAveraging,
)
from .preparation import load_data, get_feature_types, preprocess_data
from .model import LitNN


def train_final(
    X_num_train, dl_train, dl_val, transformers, hparams=None, categorical_cols=None
):
    """
    Defines model hyperparameters and fit the model.
    """
    if hparams is None:
        hparams = {
            "embedding_dim": 27,
            "projection_dim": 43,
            "hidden_dim": 76,
            "lr": 0.00487,
            "dropout": 0.38886,
            "aux_weight": 0.49631,
            "margin": 0.10025,
            "weight_decay": 0.000115,
        }
    model = LitNN(
        continuous_dim=X_num_train.shape[1],
        categorical_cardinality=[len(t.classes_) for t in transformers],
        race_index=categorical_cols.index("race_group"),
        **hparams
    )
    checkpoint_callback = pl.callbacks.ModelCheckpoint(monitor="val_loss", save_top_k=1)
    trainer = pl.Trainer(
        accelerator="cuda",
        max_epochs=100,  #### 56 is used in this competition but 100 epoch achieve the lowest validation loss
        log_every_n_steps=6,
        callbacks=[
            checkpoint_callback,
            LearningRateMonitor(logging_interval="epoch"),
            TQDMProgressBar(),
            StochasticWeightAveraging(
                swa_lrs=1e-5, swa_epoch_start=40, annealing_epochs=15
            ),
        ],
    )
    trainer.fit(model, dl_train)
    trainer.test(model, dl_val)
    return model.eval()


def main(hparams):
    """
    Main function to train the model.
    The steps are as following :
    * load data and fill efs and efs time for test data with 1
    * initialize pred array with 0
    * get categorical and numerical columns
    * split the train data on the stratified criterion : race_group * newborns yes/no
    * preprocess the fold data (create dataloaders)
    * train the model and create final submission output
    """
    test, train_original = load_data()
    test["efs_time"] = 1
    test["efs"] = 1
    test_pred = np.zeros(test.shape[0])
    categorical_cols, numerical = get_feature_types(train_original)
    kf = StratifiedKFold(
        n_splits=5,
        shuffle=True,
    )
    for i, split in enumerate(
        kf.split(
            train_original,
            train_original.race_group.astype(str)
            + (train_original.age_at_hct == 0.044).astype(str),
        )
    ):
        train_index, test_index = split
        tt = train_original.copy()
        train = tt.iloc[train_index]
        val = tt.iloc[test_index]
        X_cat_val, X_num_train, X_num_val, dl_train, dl_val, transformers = (
            preprocess_data(train, val)
        )
        model = train_final(
            X_num_train,
            dl_train,
            dl_val,
            transformers,
            categorical_cols=categorical_cols,
        )
        # Create submission
        train = tt.iloc[train_index]
        X_cat_val, X_num_train, X_num_val, dl_train, dl_val, transformers = (
            preprocess_data(train, test)
        )
        pred, _ = model.cuda().eval()(
            torch.tensor(X_cat_val, dtype=torch.long).cuda(),
            torch.tensor(X_num_val, dtype=torch.float32).cuda(),
        )
        test_pred += pred.detach().cpu().numpy()

    subm_data = pd.read_csv("sample_submission.csv")
    subm_data["prediction"] = -test_pred
    subm_data.to_csv("submission.csv", index=False)

    return


if __name__ == "__main__":
    filterwarnings("ignore")
    pl.seed_everything(42)
    hparams = None
    main(hparams)
    print("done")
