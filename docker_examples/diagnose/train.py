# Importing libraries
from operator import __setitem__
from pandas import read_csv
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from joblib import dump
  
if __name__ == "__main__":
  # Reading the train.csv by removing the 
  # last column since it's an empty column
  DATA_PATH = "dataset/Training.csv"
  data = read_csv(DATA_PATH).dropna(axis = 1)

  # Encoding the target value into numerical
  # value using LabelEncoder
  encoder = LabelEncoder()
  data["prognosis"] = encoder.fit_transform(data["prognosis"])
  
  X = data.iloc[:,:-1]
  y = data.iloc[:, -1]
    
  # Training and testing SVM Classifier
  svm_model = SVC()
  svm_model.fit(X, y)

  # Training and testing Naive Bayes Classifier
  nb_model = GaussianNB()
  nb_model.fit(X, y)

  # Training and testing Random Forest Classifier
  rf_model = RandomForestClassifier(random_state=18)
  rf_model.fit(X, y)

  # Save the LabelEncoder
  dump(encoder, "models/encoder.pkl")

  # Save the trained models
  dump(svm_model, "models/svm_model.pkl")
  dump(nb_model, "models/nb_model.pkl")
  dump(rf_model, "models/rf_model.pkl")