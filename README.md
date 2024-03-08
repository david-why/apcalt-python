# apcalt-python
A better way to view your AP Classroom, written in Python.

## DISCLAIMER: THIS PROJECT IS WRITTEN FOR EDUCATIONAL PURPOSES ONLY! ANY ILLEGAL USE IS STRICTLY PROHIBITED AND IS NOT SUPPORTED BY THE PROJECT OWNER!

## Instructions for use
Download the latest GitHub Actions build for your OS, unzip it, and run it.

## Running from source
It's not suggested to do this; the Actions artifacts work for most people. But if you want to, basically:
1. Make sure that you have Python 3.11 and Poetry installed on your system.
2. Clone the repository with `--recurse-submodules`.
3. Run `make` in the project root.
4. Run `poetry install` in the project root.
5. Run `python3.11 apcalt_python/_entrypoint.py` to start APCAlt.
