FROM ubuntu:20.04

# install Python and Python requirements
RUN apt-get update
RUN apt-get install -y python3
RUN apt-get install -y python3-pip

# copy all job files to home directory & give execution rights
WORKDIR /home
COPY . .
RUN find . -type f -exec chmod 0744 {} \;

# Train and save the models
RUN pip install -r requirements.txt
RUN python3 train.py --data-path dataset/Training.csv --output-dir models

# run the command on container startup
ENTRYPOINT [ "python3", "predict.py", "--data-path", "dataset/Training.csv" ]