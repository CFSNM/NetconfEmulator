# -*- coding: utf-8 eval: (yapf-mode 1) -*-
# February 24 2018, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2018, Deutsche Telekom AG.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import absolute_import, division, unicode_literals, print_function, nested_scopes
import argparse
import logging
import os
import sys
import time
from netconf import error, server, util
from netconf import nsmap_add, NSMAP
from pymongo import MongoClient
from lxml import etree
import pyangbind.lib.serialise as serialise
import pyangbind.lib.pybindJSON as pybindJSON
from pyangbind.lib.serialise import pybindJSONDecoder
import json
from os import listdir, getcwd
from pydoc import locate
from internal import objects, utils

nsmap_add("sys", "urn:ietf:params:xml:ns:yang:ietf-system")


class NetconfEmulator(object):
    def __init__(self, port, host_key, auth, debug):
        self.server = objects.NetconfEmulatorServer(auth, self, port, host_key, debug)
        bindings_files_folder = getcwd() + "/bindings"
        bindings_folder_list = listdir(bindings_files_folder)
        for bind_file in bindings_folder_list:
            if "binding-" in bind_file and '.py' in bind_file and '.pyc' not in bind_file:
                binding_file = bind_file
                break

        binding_file_fixed = binding_file.replace(".py", "")

        self.used_profile = binding_file_fixed.split("inding-")[1]
        self.binding = locate('bindings.' + binding_file_fixed)

        logging.info("Used profile: "+self.used_profile)


    def close(self):
        self.server.close()

    def nc_append_capabilities(self, capabilities):  # pylint: disable=W0613
        """The server should append any capabilities it supports to capabilities"""
        util.subelm(capabilities,
                    "capability").text = "urn:ietf:params:netconf:capability:xpath:1.0"
        util.subelm(capabilities, "capability").text = NSMAP["sys"]


    def rpc_available_profiles(self, session, rpc, *unused):
        logging.info("Received available-profiles rpc: " + etree.tostring(rpc, pretty_print=True))
        dbclient = MongoClient()
        db = dbclient.netconf
        response = etree.Element("available-profiles")

        bindings_files_folder = getcwd() + "/bindings"
        bindings_folder_list = listdir(bindings_files_folder)
        i = 0
        for bind_file in bindings_folder_list:
            if "binding-" in bind_file and '.py' in bind_file and '.pyc' not in bind_file:
                binding_file_fixed = bind_file.replace(".py", "")
                profile = str(binding_file_fixed.split("inding-")[1])
                profile_name_subel = etree.Element("name")
                profile_name_subel.text = profile
                profile_active_subel = etree.Element("active")
                profile_active_subel.text = str(profile == self.used_profile)

                profile_element = etree.Element("available-profile")
                profile_element.insert(0, profile_name_subel)
                profile_element.insert(1, profile_active_subel)

                modules_element = etree.Element("modules")

                for collection_name in db.list_collection_names():
                    if collection_name == profile:
                        collection = getattr(db, collection_name)
                        modules_data = collection.find_one({"_id": "modules"})
                        modules_dict = dict(modules_data)
                        modules = modules_dict["modules"]
                        j = 0
                        for module in modules:
                            module_name_element = etree.Element("module")
                            module_name_element.text = module
                            modules_element.insert(j, module_name_element)
                            j = j + 1

                profile_element.insert(2, modules_element)
                response.insert(i, profile_element)
                i += 1

        return response

    def rpc_activate_profile(self, session, rpc, *unused):
        logging.info("Received activate-profile rpc: "+etree.tostring(rpc, pretty_print=True))
        response = etree.Element("ok")

        name = rpc[0][0].text
        logging.info(name)
        bindings_files_folder = getcwd() + "/bindings"
        bindings_folder_list = listdir(bindings_files_folder)
        for bind_file in bindings_folder_list:
            if "binding-" in bind_file and '.py' in bind_file and '.pyc' not in bind_file and name in bind_file:
                binding_file = bind_file
                break

        binding_file_fixed = binding_file.replace(".py", "")

        self.used_profile = binding_file_fixed.split("inding-")[1]
        self.binding = locate('bindings.' + binding_file_fixed)

        logging.info("Used profile: "+self.used_profile)

        return response

    def rpc_commit(self, session, rpc, *unused):
        logging.info("Received commit rpc: " + etree.tostring(rpc, pretty_print=True))
        response = etree.Element("ok")
        dbclient = MongoClient()
        db = dbclient.netconf
        for collection_name in db.list_collection_names():
            if self.used_profile in collection_name:
                collection = getattr(db, collection_name)
                modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                delete_running_result = collection.delete_one({"_id": "running"})
                collection_data_candidate = collection.find_one({"_id": "candidate"})
                del collection_data_candidate["_id"]
                collection_binding_candidate = pybindJSONDecoder.load_ietf_json(collection_data_candidate, self.binding, modules[0])
                collection_xml_string_candidate = serialise.pybindIETFXMLEncoder.serialise(collection_binding_candidate)

                database_data = serialise.pybindIETFXMLDecoder.decode(collection_xml_string_candidate, self.binding, modules[0])
                database_string = pybindJSON.dumps(database_data, mode="ietf")
                database_json = json.loads(database_string)

                database_json["_id"] = "running"
                collection.insert_one(database_json)

        return response

    def rpc_delete_config(self, session, rpc, *unused):
        logging.info("Received delete-config rpc: " + etree.tostring(rpc, pretty_print=True))
        dbclient = MongoClient()
        selected_datastore = utils.get_datastore(rpc)

    def rpc_discard_changes(self, session, rpc, *unused):
        logging.info("Received discard-changes rpc: " + etree.tostring(rpc, pretty_print=True))
        response = etree.Element("ok")
        dbclient = MongoClient()
        db = dbclient.netconf
        for collection_name in db.list_collection_names():
            if self.used_profile in collection_name:
                collection = getattr(db, collection_name)
                modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                delete_running_result = collection.delete_one({"_id": "candidate"})
                collection_data_running = collection.find_one({"_id": "running"})
                del collection_data_running["_id"]
                collection_binding_running = pybindJSONDecoder.load_ietf_json(collection_data_running, self.binding,
                                                                                modules[0])
                collection_xml_string_running = serialise.pybindIETFXMLEncoder.serialise(collection_binding_running)

                database_data = serialise.pybindIETFXMLDecoder.decode(collection_xml_string_running, self.binding, modules[0])
                database_string = pybindJSON.dumps(database_data, mode="ietf")
                database_json = json.loads(database_string)

                database_json["_id"] = "candidate"
                collection.insert_one(database_json)

    def rpc_get(self, session, rpc, filter_or_none):  # pylint: disable=W0613
        logging.info("Received get rpc: "+etree.tostring(rpc, pretty_print=True))
        dbclient = MongoClient()
        data_elm = etree.Element('data', nsmap={None: 'urn:ietf:params:xml:ns:netconf:base:1.0'})
        if rpc[0].find('{*}filter') is None:

            db = dbclient.netconf
            for collection_name in db.list_collection_names():
                if self.used_profile in collection_name:
                    collection = getattr(db, collection_name)
                    collection_data = collection.find_one({"_id": "running"})
                    modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                    collection_data_1 = dict(collection_data)
                    for element in collection_data:
                        if "id" in element:
                            del collection_data_1[element]
                    collection_data = collection_data_1

                    collection_binding = pybindJSONDecoder.load_ietf_json(collection_data, self.binding, modules[0])
                    xml_data_string = serialise.pybindIETFXMLEncoder.serialise(collection_binding)
                    xml_data = etree.XML(xml_data_string)
                    data_elm.insert(1, xml_data)

        else:

            db = dbclient.netconf
            for collection_name in db.list_collection_names():
                if self.used_profile in collection_name:
                    collection = getattr(db, collection_name)
                    datastore_data = collection.find_one({"_id": "running"})
                    modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                    datastore_data_1 = dict(datastore_data)
                    for element in datastore_data:
                        if "id" in element:
                            del datastore_data_1[element]
                    datastore_data = datastore_data_1

                    database_data_binding = pybindJSONDecoder.load_ietf_json(datastore_data, self.binding, modules[0])
                    xml_data_string = serialise.pybindIETFXMLEncoder.serialise(database_data_binding)
                    xml_data = etree.XML(xml_data_string)
                    data_elm.insert(1, xml_data)


        xml_response = data_elm
        toreturn = util.filter_results(rpc, xml_response, filter_or_none, self.server.debug)

        if "data" not in toreturn.tag:
            logging.info("Error, data header not found")
            nsmap = {None : 'urn:ietf:params:xml:ns:netconf:base:1.0'}
            data_elm = etree.Element('data', nsmap=nsmap)
            data_elm.insert(1, toreturn)
            toreturn = data_elm

        return toreturn

    def rpc_get_config(self, session, rpc, source_elm, filter_or_none):
        logging.info("Received get-config rpc: " + etree.tostring(rpc, pretty_print=True))
        dbclient = MongoClient()
        selected_datastore = utils.get_datastore(rpc)
        data_elm = etree.Element('data', nsmap={None: 'urn:ietf:params:xml:ns:netconf:base:1.0'})

        if rpc[0].find('{*}filter') is None:

            db = dbclient.netconf
            for collection_name in db.list_collection_names():
                if self.used_profile in collection_name:
                    collection = getattr(db, collection_name)
                    collection_data = collection.find_one({"_id": selected_datastore})
                    modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                    collection_data_1 = dict(collection_data)
                    for element in collection_data:
                        if "id" in element:
                            del collection_data_1[element]
                    collection_data = collection_data_1

                    collection_binding = pybindJSONDecoder.load_ietf_json(collection_data, self.binding, modules[0])
                    xml_data_string = serialise.pybindIETFXMLEncoder.serialise(collection_binding)
                    xml_data = etree.XML(xml_data_string)
                    data_elm.insert(1, xml_data)

        else:

            db = dbclient.netconf
            for collection_name in db.list_collection_names():
                if self.used_profile in collection_name:
                    collection = getattr(db, collection_name)
                    datastore_data = collection.find_one({"_id": selected_datastore})
                    modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                    datastore_data_1 = dict(datastore_data)
                    for element in datastore_data:
                        if "id" in element:
                            del datastore_data_1[element]
                    datastore_data = datastore_data_1

                    database_data_binding = pybindJSONDecoder.load_ietf_json(datastore_data, self.binding, modules[0])
                    xml_data_string = serialise.pybindIETFXMLEncoder.serialise(database_data_binding)
                    xml_data = etree.XML(xml_data_string)
                    data_elm.insert(1, xml_data)

        xml_response = data_elm
        toreturn = util.filter_results(rpc, xml_response, filter_or_none, self.server.debug)
        utils.remove_state(toreturn)

        if "data" not in toreturn.tag:
            logging.info("Error, data header not found")
            nsmap = {None : 'urn:ietf:params:xml:ns:netconf:base:1.0'}
            data_elm = etree.Element('data', nsmap=nsmap)
            data_elm.insert(1, toreturn)
            toreturn = data_elm

        return toreturn

    def rpc_edit_config(self, session, rpc, *unused_params):
        logging.info("Received edit-config rpc: "+etree.tostring(rpc, pretty_print=True))
        dbclient = MongoClient()
        db = dbclient.netconf

        response = etree.Element("ok")
        datastore_to_insert = utils.get_datastore(rpc)
        data_to_insert_xml = etree.fromstring(etree.tostring(rpc[0][1]))

        for collection_name in db.list_collection_names():
            if self.used_profile in collection_name:
                 collection = getattr(db, collection_name)
                 running_config = collection.find_one({"_id": datastore_to_insert})
                 modules = dict(collection.find_one({"_id": "modules"}))["modules"]
                 del running_config["_id"]
                 running_config_b = pybindJSONDecoder.load_ietf_json(running_config, self.binding, modules[0])
                 running_config_xml_string = serialise.pybindIETFXMLEncoder.serialise(running_config_b)
                 running_config_xml = etree.fromstring(running_config_xml_string)

                 newconfig = utils.process_changes(data_to_insert_xml, running_config_xml)

                 collection.delete_one({"_id": datastore_to_insert})
                 newconfig_string = etree.tostring(newconfig)
                 database_data = serialise.pybindIETFXMLDecoder.decode(newconfig_string, self.binding, modules[0])
                 database_string = pybindJSON.dumps(database_data, mode="ietf")
                 database_json = json.loads(database_string)

                 database_json["_id"] = datastore_to_insert
                 collection.insert_one(database_json)

        return response

    def rpc_system_restart(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)

    def rpc_system_shutdown(self, session, rpc, *params):
        raise error.AccessDeniedAppError(rpc)


def main(*margs):
    parser = argparse.ArgumentParser("Netconf Agent Emulator")
    parser.add_argument("--debug", default=False, help="Enable debug logging")
    parser.add_argument('--port', type=int, default=8300, help='Netconf server port')
    parser.add_argument("--username", default="admin", help='Netconf username')
    parser.add_argument("--password", default="admin", help='Netconf password')
    args = parser.parse_args(*margs)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    host_key = os.getcwd() + "/hostkey/id_rsa"

    auth = server.SSHUserPassController(username=args.username, password=args.password)
    s = NetconfEmulator(args.port, host_key, auth, args.debug)

    if sys.stdout.isatty():
        print("^C to stop emulator")
    try:
        while True:
            time.sleep(1)
    except Exception:
        print("Quitting emulator")

    s.close()


if __name__ == "__main__":
    main()
