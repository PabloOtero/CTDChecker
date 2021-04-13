# IEO CTD Checker

## Features

- Import ocean vertical profiles (SeaBird CTD files)
- Apply quality control (flags)
- Reformat to MedAtlas format
- Create metadata for each profile
- Plot stations
- Show warnings and useful info on screen

## Background
<p id="bkmrk-the-ctd-is-a-cluster">The <a href="https://en.wikipedia.org/wiki/CTD_(instrument)">CTD</a> is a cluster of sensors which measure conductivity (to derive salinity), temperature, and pressure. Other sensors may be added to the cluster, including some that measure chemical or biological parameters, such as <a class="mw-redirect" title="Dissolved oxygen" href="https://en.wikipedia.org/wiki/Dissolved_oxygen">dissolved oxygen</a> and <a title="Chlorophyll fluorescence" href="https://en.wikipedia.org/wiki/Chlorophyll_fluorescence">chlorophyll fluorescence</a>. The CTD cast collects high resolution data that upon retrieval is downloaded to a computer and specialised software is used to graph and interpret data. However, as stated by the SeaDataNet consortium, many times the collected data are neither easily accessible, nor standardized. They are not always validated and their security and availability have to be insured in the future. </p>
<p id="bkmrk-hundreds-of-ctd-prof">Hundreds of CTD profiles are recorded by Instituto Español de Oceanografía each year and they are routinely incorporated to the SeaDataNet infrastructure network, which in a unique virtual data management system provide integrated data sets of standardized quality on-line. </p>
<p id="bkmrk-thus%2C-each-individua">Thus, each individual record coming from a CTD instrument must be properly flagged to point how confidence is (<strong><a href="https://www.seadatanet.org/Standards/Data-Quality-Control" target="_blank" rel="noopener">Quality Flag Scale</a></strong>), data stored in files according to <strong><a href="https://www.seadatanet.org/Standards/Data-Transport-Formats">common data transport formats</a></strong> and <strong><a href="https://www.seadatanet.org/Standards/Common-Vocabularies">standard vocabularies</a></strong> and associated metadata created to allow the dataset to be findable and interoperable (<a href="https://www.seadatanet.org/Metadata/CDI-Common-Data-Index"><strong>Common Data Index</strong></a>).</p>
<p id="bkmrk-to-achieve-this-goal">To achieve this goal, SeaDataNet provides some tools to prepare XML metadata files (<a href="https://www.seadatanet.org/Software/MIKADO">MIKADO</a>), convert from any type of ASCII format to the SeaDataNet ODV and Medatlas ASCII formats as well as the SeaDataNet NetCDF format (<a href="https://www.seadatanet.org/Software/NEMO">NEMO</a>) and check the compliance of a file (<a href="https://www.seadatanet.org/Software/OCTOPUS">OCTOPUS</a>).</p>
<p id="bkmrk-all-these-tasks-are-">All these tasks are time consuming and require human interaction that can lead to errors or lack of uniformity in data. Taking into account that CTD data usually follows the same format and involves similar processing, a software has been developed to perform all these tasks straightforward. Technically, the software is written in Python and there is also a Flask version to serve the application through web. To learn about the deployment of this application in a web server, please, <a title="Deploying Python Flask: the example of IEO CTD Checker" href="http://www.wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/deploying-python-flask-the-example-of-ieo-ctd-checker">read this page</a>.</p>
<p id="bkmrk-%C2%A0"> </p>


## How to use the application?
<p id="bkmrk-1%29-navigate-in-your-">1) Open the file ctd_check.py and provide the route of your xml file and your cnv files. No other kind of files can coexist in this foilder. In this case, the xml is the Cruise Summary Report (CSR) file. This is a XML file containing information of your research campaign (metadata). Usually, this file is created with <a href="https://www.seadatanet.org/Software/MIKADO">MIKADO</a> software at the end of the campaign and submitted to the corresponding National Oceanographic Data Center (NODC). After, the NODC checks and populates this file to the SeaDataNet infrastructure. If you don't have this file, try a search in the <a href="http://seadata.bsh.de/Cgi-csr/retrieve_sdn2/start_sdn2.pl">SeaDataNet database</a> and download the file as XML V2.
<p id="bkmrk-2%29-provide-a-cruise-">2) Run the code and you'll obtain an output folder in the same directory with data in MedAtlas formar, CDI (xml) files for each CTD profile and some figures. Here you can find and example of a figure:
  
  http://www.wiki.ieo.es/uploads/images/gallery/2020-03-Mar/scaled-840-0/image-1583136050784.png
  
 Salinity and temperature profiles are drawn for each profile. Shaded areas behind profiles indicate climatologic values (mean +/- standard deviation). An orange circle over the profile indicates that a test failed. 

Most of the tests done by the application simply reproduce the procedure recommended by GTSPP. Its real time quality control manual lays out in detail the automatic tests to be carried out on temperature and salinity data (se also SeaDataNet Data Quality Control Procedures manual). In order not to reinvent the wheel, the CoTeDe Python package created by Guilherme P. Castelao has been adapted.

To learn more: http://www.wiki.ieo.es/books/centro-nacional-de-datos-oceanogr%C3%A1ficos/page/ieo-ctd-checker

