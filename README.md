# Street2Sat

 Street2Sat is a new framework for obtaining large data sets of geo-referenced crop type labels obtained from vehicle mounted cameras that can be extended to other applications.

Paper accepted to ICML 2021 Tackling Climate Change Using AI Workshop. 🎉
Link coming soon!

## Setting up the environment
1. Clone the repository
2. Set up and activate a Python virtual environment
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3. Install the dependencies
    ```bash
    pip install -r requirements.txt
    ```
## Usage


#### Google Cloud Platform
Ensure the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) is installed.

**Initial Setup (only done once)**
```bash
gsutil mb gs://street2sat-uploaded
```
**Deploying resources (done on every code update)**
```bash
sh deploy.sh
```

## Background
<p></p>
<p>
Ground-truth labels on crop type and other variables are critically needed to develop machine learning methods that use satellite observations to combat climate change and food insecurity. These labels difficult and costly to obtain over large areas, particularly in Sub-Saharan Africa where they are most scarce.  Street2Sat is a new framework for obtaining large data sets of geo-referenced crop type labels obtained from vehicle mounted cameras that can be extended to other applications.
</p>
