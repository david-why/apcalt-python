# apcalt-python

> A better way to view your AP Classroom

Have you ever thought, *heck, why is my AP Classroom so slow?* Well, I certainly have, and this is my solution to it.

This is a website on which you can view your AP Classroom, complete your assignments, and even watch the AP Daily videos. Although the interface might seem less polished, it's much faster than the original website, and you don't need to login every 20 minutes.

## DISCLAIMER: THIS PROJECT IS WRITTEN FOR EDUCATIONAL PURPOSES ONLY! ANY ILLEGAL USE IS STRICTLY PROHIBITED AND IS NOT SUPPORTED BY THE PROJECT OWNER!

## Instructions for use

1. Download the file corresponding to your operating system from the Assets section in [here](https://github.com/david-why/apcalt-python/releases/tag/nightly), or click on the links below:
   * Mac OS: [apcalt-python.dmg](https://github.com/david-why/apcalt-python/releases/download/nightly/apcalt-python.dmg)
   * Windows: [apcalt-python.exe](https://github.com/david-why/apcalt-python/releases/download/nightly/apcalt-python.exe)
   * Linux: [apcalt-python.AppImage](https://github.com/david-why/apcalt-python/releases/download/nightly/apcalt-python.AppImage)
2. Run the downloaded application.
   * For Mac OS, you may drag the APCAlt application into the Applications folder to install it. You can also just double-click on the APCAlt app to run it without installation.
3. Open [http://localhost:8052](http://localhost:8052) and happy studying!

## Running from source

It's not suggested to do this; the steps above work for most people. But if you want to, basically:

1. Make sure that you have Python 3.11 and Poetry installed on your system.
2. Clone the repository with `git clone https://github.com/david-why/apcalt-python --recurse-submodules`.
3. Run `make` and then `poetry install` in the project root.
4. Run `python apcalt_python/_entrypoint.py` to start APCAlt.
