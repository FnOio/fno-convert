import argparse
from pathlib import Path
from pandas import read_csv
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from joblib import dump


def main(data_path: str, output_dir: str):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Reading the train.csv and dropping any empty columns
    data = read_csv(data_path).dropna(axis=1)

    # Encode target variable
    encoder = LabelEncoder()
    data["prognosis"] = encoder.fit_transform(data["prognosis"])

    X = data.iloc[:, :-1]
    y = data.iloc[:, -1]

    # Train SVM
    svm_model = SVC()
    svm_model.fit(X, y)

    # Train Naive Bayes
    nb_model = GaussianNB()
    nb_model.fit(X, y)

    # Train Random Forest
    rf_model = RandomForestClassifier(random_state=18)
    rf_model.fit(X, y)

    # Save encoder and models
    dump(encoder, f"{output_dir}/encoder.pkl")
    dump(svm_model, f"{output_dir}/svm_model.pkl")
    dump(nb_model, f"{output_dir}/nb_model.pkl")
    dump(rf_model, f"{output_dir}/rf_model.pkl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train models on medical prognosis data.")
    parser.add_argument("--data-path", required=True, help="Path to the training CSV file.")
    parser.add_argument("--output-dir", required=True, help="Directory to save models and encoder.")

    args = parser.parse_args()
    main(args.data_path, args.output_dir)