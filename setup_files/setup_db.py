from __future__ import print_function
from pymongo import MongoClient
import pyangbind.lib.serialise as serialise
import pyangbind.lib.pybindJSON as pybindJSON
import sys
import json
from os import listdir, getcwd
from pydoc import locate
from lxml import etree

if sys.argv[1] is None:
    print("The startup config is missing")
    exit(1)

if sys.argv[2] is None:
    print("The module dependencies are missing")
    exit(1)

bindings_files_folder = getcwd()+"/bindings"

cfg = sys.argv[1]
dependencies = sys.argv[2].replace("\n", " ").replace(".yang", "").split(" ")
module = dependencies[0]
database = cfg.replace(".xml", "")

bindings_folder_list = listdir(bindings_files_folder)
for bind_file in bindings_folder_list:
    if database in bind_file and '.py' in bind_file and '.pyc' not in bind_file:
        binding_file = bind_file
        break

binding_file_fixed = binding_file.replace(".py", "")

binding = locate('bindings.'+binding_file_fixed)

print("Creating database", database)

dbclient = MongoClient()
db = dbclient.netconf

print("Parsing data from the xml provided")
with open(cfg, 'r+') as database_reader:
    data = database_reader.read().replace('\n', '')

data = data.replace('xmlns=','xmlns:m=')

database_data = serialise.pybindIETFXMLDecoder.decode(data, binding, module)
database_string = pybindJSON.dumps(database_data, mode="ietf")

startup_json = json.loads(database_string)
startup_json["_id"] = "startup"

candidate_json = json.loads(database_string)
candidate_json["_id"] = "candidate"

running_json = json.loads(database_string)
running_json["_id"] = "running"

modules_json = json.loads('{}')
modules_json["_id"] = "modules"
modules_json["modules"] = dependencies

print("Inserting files into database")
collection = getattr(db, database)
result_startup = collection.insert_one(startup_json)
result_candidate = collection.insert_one(candidate_json)
result_running = collection.insert_one(running_json)
result_modules = collection.insert_one(modules_json)
