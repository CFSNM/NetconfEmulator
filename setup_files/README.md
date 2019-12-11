This scripts are used to configure the initial linking files and databases for the netconf server.

In order to do so, setup_binding.sh needs to be run. The steps to prepare the execution are:

1. Create a txt file listing the different yang models you want to use --> models.txt
2. Create a xml file with the startup configuration of your agent --> startup-cfg.xml
3. Insert into setup_files directory the pertinent yang files.
4. From setup_files directory, run setup_binding.sh like so:
``
./setup_binding.sh models.txt startup-cfg.xml
``