# FnO Function Converter

A tool to automatically semantically annotate pipelines written in Dockerfiles and/or Python files using FnO. These semantic representations allow execution to capture provenance across implementation framework using PROV-O.

## Installation

### Quick Use

```
pip install .
```

### Development

1. create virtual environment
```python
python -m venv <path to env folder>
```

2. activate environment

3. install requirements
```python
pip install -r requirements.txt
```

4. install fno-convert for testing
```python
pip install -e .
```

## Usage

### Running the tool

```
python test_app.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
