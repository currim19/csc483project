# Setup the environment

To run the project, one will need to set up the following environment.
 
* [git](https://git-scm.com/downloads/)
* [Python (3.8 or higher)](https://www.python.org/)
* [lupyne](https://pypi.org/project/lupyne/)
* [spaCy](https://spacy.io/) including spaCy lookups and the en_core_web_sm model
* [Docker desktop](https://www.docker.com/products/docker-desktop)

# Create a new docker container

To download the docker image with the pre-requisites (python, lupyne, pylucene, spacy) installed, please run:
   ```
   docker pull azdb/csc483:version1 
   ```

Then, you can start up a new container and connect to it.
   ```
   docker run --name csc483 -td azdb/csc483:version1
   docker exec -it csc483 bash
   ```

# Clone the github repository

To clone the github repository please use one of the following commands.

To clone the original repository (this version has a bug that over-inflates P@1) you can use:
   ```
   git clone https://github.com/currim19/csc483project.git
   ```

To clone the current version, please use:
   ```
   git clone https://github.com/currim19/csc483project.git/ --branch currim_faiz_post
   ```



# Download (or build) PyLucene index

A collection of pre-built indexes are available on box.arizona.edu. The URL is in the project report.

Please store the indexes in the project root (i.e., within the cs438project directory)

**Note: I could not find a way to automate the download of the index, and it may require a manual download

The main project python code is under:
- `src/test/python/edu/arizona/cs/query_engine.py`
 

# Run the code

To run the code, you can type the following command.

   ```
   python src/main/python/edu/arizona/cs/query_engine.py
   ```


