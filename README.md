# IEO CTD Checker

## Features

- Import ocean vertical profiles (SeaBird CTD files)
- Apply quality control (flags)
- Reformat to MedAtlas format
- Create metadata for each profile
- Plot stations
- Show warnings and helpful info on the screen

## Background
<p id="bkmrk-the-ctd-is-a-cluster">The <a href="https://en.wikipedia.org/wiki/CTD_(instrument)">CTD</a> is a cluster of sensors which measure conductivity (to derive salinity), temperature, and pressure. Other sensors may be added to the cluster, including some that measure chemical or biological parameters, such as <a class="mw-redirect" title="Dissolved oxygen" href="https://en.wikipedia.org/wiki/Dissolved_oxygen">dissolved oxygen</a> and <a title="Chlorophyll fluorescence" href="https://en.wikipedia.org/wiki/Chlorophyll_fluorescence">chlorophyll fluorescence</a>. The CTD cast collects high-resolution data that upon retrieval is downloaded to a computer and specialized software is used to graph and interpret data. However, as stated by the SeaDataNet consortium, many times the collected data are neither easily accessible nor standardized. They are not always validated and their security and availability have to be insured in the future. </p>
<p id="bkmrk-hundreds-of-ctd-prof">Hundreds of CTD profiles are recorded by Instituto Español de Oceanografía each year and they are routinely incorporated to the SeaDataNet infrastructure network, which in a unique virtual data management system provide integrated data sets of standardized quality on-line. </p>
<p id="bkmrk-thus%2C-each-individua">Thus, each individual record coming from a CTD instrument must be properly flagged to point how confidence is (<strong><a href="https://www.seadatanet.org/Standards/Data-Quality-Control" target="_blank" rel="noopener">Quality Flag Scale</a></strong>), data stored in files according to <strong><a href="https://www.seadatanet.org/Standards/Data-Transport-Formats">common data transport formats</a></strong> and <strong><a href="https://www.seadatanet.org/Standards/Common-Vocabularies">standard vocabularies</a></strong> and associated metadata created to allow the dataset to be findable and interoperable (<a href="https://www.seadatanet.org/Metadata/CDI-Common-Data-Index"><strong>Common Data Index</strong></a>).</p>
<p id="bkmrk-to-achieve-this-goal">To achieve this goal, SeaDataNet provides some tools to prepare XML metadata files (<a href="https://www.seadatanet.org/Software/MIKADO">MIKADO</a>), convert from any type of ASCII format to the SeaDataNet ODV and Medatlas ASCII formats as well as the SeaDataNet NetCDF format (<a href="https://www.seadatanet.org/Software/NEMO">NEMO</a>) and check the compliance of a file (<a href="https://www.seadatanet.org/Software/OCTOPUS">OCTOPUS</a>).</p>
<p id="bkmrk-all-these-tasks-are-">All these tasks are time-consuming and require human interaction that can lead to errors or lack of uniformity in data. Taking into account that CTD data usually follows the same format and involves similar processing, software has been developed to perform all these tasks straightforward. Technically, the software is written in Python and there is also a Flask version to serve the application through web. To learn about the deployment of this application in a web server, please, <a title="Deploying Python Flask: the example of IEO CTD Checker" href="http://www.wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/deploying-python-flask-the-example-of-ieo-ctd-checker">read this page</a>.</p>
<p id="bkmrk-%C2%A0"> </p>

## Run the code locally

### As a Python Flask application
You need to download and install all components in a virtual environment. Once the environment is active, run in your console:
```sh
python app.py
```
open your browser and verify that the application is up and running on  port 5000
```sh
127.0.0.1:5000
```

### As a classical Python application
Download and install all components in a virtual environment. The main file is `checking.py`. You need to make some changes before execute it:
1) Turn flash_messages variable in config.py.
2) Set your path with your files in config.py. This is the route of your xml file and your cnv files. No other kind of files can coexist in this folder. In this case, the xml is the Cruise Summary Report (CSR) file. 
3) Uncomment the last block of lines at the end of this file.


## Installation

For production environments have a look at the [deployment] documentation.


## About this software

Most of the tests done by the application simply reproduce the procedure recommended by GTSPP. Its real-time quality control manual lays out in detail the automatic tests to be carried out on temperature and salinity data (se also SeaDataNet Data Quality Control Procedures manual). 

## Acknowledgements

In order not to reinvent the wheel, some parts of the CoTeDe Python package created by Guilherme P. Castelao and the [python-ctd] library have been adopted.


[//]: # (These are reference links used in the body of this note and get stripped out when the markdown processor does its job. There is no need to format nicely because it shouldn't be seen. Thanks SO - http://stackoverflow.com/questions/4823468/store-comments-in-markdown-syntax)

[here]: <http://wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/ieo-ctd-checker>
[deployment]: <http://wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/deploying-python-flask-the-example-of-ieo-ctd-checker>
[python-ctd]: <https://github.com/pyoceans/python-ctd>
