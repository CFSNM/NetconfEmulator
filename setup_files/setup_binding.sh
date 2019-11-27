if [ "$#" -ne "2" ]; then
  	echo "You need to include three parameters:\n\r"
  	echo "1) A file with the datastores\n\r"
  	echo "2) A file with the startup config (its name will be used to create the mongo collection)\n\r"
  	exit 1
fi
dependencies="$(cat $1)"
config=$2

PYBINDPLUGIN=$(/usr/bin/env python -c 'import pyangbind; import os; print ("{}/plugin".format(os.path.dirname(pyangbind.__file__)))')

name=${config/.xml/}
filename="binding_"$name".py"
pyang --plugindir $PYBINDPLUGIN -f pybind -o $filename $dependencies
cp $filename bindings/
cp $filename ../bindings/
rm $filename
python setup_db.py "$config"
