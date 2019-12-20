# CTDChecker

To achieve this goal, SeaDataNet provides some tools to prepare XML metadata files (MIKADO), convert from any type of ASCII format to the SeaDataNet ODV and Medatlas ASCII formats as well as the SeaDataNet NetCDF format (NEMO) and check the compliance of a file (OCTOPUS).

All these tasks are time consuming and require human interaction that can lead to errors or lack of uniformity in data. Taking into account that CTD data usually follows the same format and involves similar processing, a software has been developed to perform all these tasks straightforward. 

Why is the existence of a CSR file mandatory?
To process a set of CTD files, the application always requires the previous existence of a XML file containing information of the cruise, also known as Cruise Summary Report (CSR). By so doing, it is ensured that common information is translated unequivocally to formatted data files (MedAtlas format in this case) and also new metadata (CDI). Moreover, after a CSR is submitted to the SeaDataNet infrastructure, a ID is assigned. This ID can therefore be used in the creation of the new CDI files (metadata concerning each CTD cast) properly linking cruise metadata and datasets metadata. 
