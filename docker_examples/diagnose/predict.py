import joblib
import numpy as np
import argparse
from pandas import read_csv
import statistics

# Defining the Function
# Input: string containing symptoms separated by commas
# Output: Generated predictions by models
def predictDisease(symptoms, data_dict, rf_model, nb_model, svm_model):    
    # creating input data for the models
    input_data = [0] * len(data_dict["symptom_index"])
    for symptom in symptoms:
        index = data_dict["symptom_index"][symptom]
        input_data[index] = 1
        
    # reshaping the input data and converting it
    # into suitable format for model predictions
    input_data = np.array(input_data).reshape(1,-1)
    
    # generating individual outputs
    rf_prediction = data_dict["predictions_classes"][rf_model.predict(input_data)[0]]
    nb_prediction = data_dict["predictions_classes"][nb_model.predict(input_data)[0]]
    svm_prediction = data_dict["predictions_classes"][svm_model.predict(input_data)[0]]
    
    # making final prediction by taking mode of all predictions
    # Use statistics.mode instead of scipy.stats.mode
    final_prediction = statistics.mode([rf_prediction, nb_prediction, svm_prediction])
    predictions = {
        "rf_model_prediction": rf_prediction,
        "naive_bayes_prediction": nb_prediction,
        "svm_model_prediction": svm_prediction,
        "final_prediction":final_prediction
    }
    return predictions

def symptom_index():
  DATA_PATH = "dataset/Training.csv"
  data = read_csv(DATA_PATH).dropna(axis = 1)
  symptom_labels = data.iloc[:,:-1].columns.values

  # Creating a symptom index dictionary to encode the
  # input symptoms into numerical form
  symptom_index = {}
  for index, value in enumerate(symptom_labels):
    symptom = []
    for i in value.split("_"):
      i = i.capitalize()
      symptom.append(i)
    symptom = " ".join(symptom)
    symptom_index[symptom] = index
  
  return symptom_index

if __name__ == "__main__":
  # Create the parser
  parser = argparse.ArgumentParser(description='Predict diagnosis based on symptoms.')

  # Add the argument for a list of strings
  parser.add_argument('symptoms', nargs='+', help='A list of symptoms')

  # Parse the arguments
  args = parser.parse_args()
    
  encoder = joblib.load("models/encoder.pkl")
  final_rf_model = joblib.load("models/rf_model.pkl")
  final_nb_model = joblib.load("models/nb_model.pkl")
  final_svm_model = joblib.load("models/svm_model.pkl")

  data_dict = {
      "symptom_index":symptom_index(),
      "predictions_classes":encoder.classes_
  }
  
  print(predictDisease(args.symptoms, data_dict, final_rf_model, final_nb_model, final_svm_model))