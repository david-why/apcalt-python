# apcalt-python

> A better way to view your AP Classroom

Have you ever thought, *heck, why is my AP Classroom so slow?* Well, I certainly have, and this is my solution to it.

This is a website on which you can view your AP Classroom, complete your assignments, and even watch the AP Daily videos. Although the interface might seem less polished, it's much faster than the original website, and you don't need to login every 20 minutes.

## DISCLAIMER: THIS PROJECT IS WRITTEN FOR EDUCATIONAL PURPOSES ONLY! ANY ILLEGAL USE IS STRICTLY PROHIBITED AND IS NOT SUPPORTED BY THE PROJECT OWNER!

## Instructions for use

Download the latest GitHub Actions build for your OS, unzip it, and run it. Now visit http://localhost:8052, and voila!

## Running from source

It's not suggested to do this; the Actions artifacts work for most people. But if you want to, basically:
1. Make sure that you have Python 3.11 and Poetry installed on your system.
2. Clone the repository with `git clone https://github.com/david-why/apcalt-python --recurse-submodules`.
3. Run `make` in the project root.
4. Run `poetry install` in the project root.
5. Run `python3.11 apcalt_python/_entrypoint.py` to start APCAlt.
