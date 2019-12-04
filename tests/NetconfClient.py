from ncclient import manager
from argparse import ArgumentParser
from lxml import etree

def main(*margs):
    parser = ArgumentParser("Netconf Client CLI")
    parser.add_argument('--host',default='localhost', help='Netconf host')
    parser.add_argument('--port', type=int, default=8300, help='Netconf server port')
    parser.add_argument("--username", default="admin", help='Netconf username')
    parser.add_argument("--password", default="admin", help='Netconf password')
    parser.add_argument("--rpc", default='get-config', help="RPC to execute (get-config, get, edit-config, available-profiles, activate-profile, commit, discard-changes)")
    parser.add_argument("--datastore", default='running', help="Netconf datastore (running, candidate or startup). Only for get-config, edit-config and delete-config RPCs.")
    parser.add_argument("--new_active_profile", default=None, help="Profile to activate. Only for activate-profile RPC.")
    parser.add_argument("--filter_or_config_file", default=None, help="RPC filter field for get-config and get RPCs or RPC config field for edit-config RPC.")
    parser.add_argument("--source_target_datastores", default="running_startup", help="Source and target datastores (Separated by a _ character). Only for copy-config RPC.")
    args = parser.parse_args(*margs)

    host = args.host
    port = args.port
    username = args.username
    password = args.password
    rpc = args.rpc
    datastore = args.datastore
    new_profile = args.new_active_profile
    filter_or_config = open(args.filter_or_config_file, 'r+').read() if args.filter_or_config_file is not None else None
    source_target_datastores = args.source_target_datastores

    man = manager.connect(host=host, port=port, username=username, password=password, timeout=120, hostkey_verify=False, look_for_keys=False, allow_agent=False)

    if rpc == 'get-config':

        get_config_response = man.get_config(datastore, filter_or_config)
        print get_config_response

    elif rpc == 'get':

        if filter_or_config is not None:
            rpc = "<get>" + filter_or_config + "</get>"
        else:
            rpc = "<get/>"
        get_response = man.dispatch(etree.fromstring(rpc))
        print get_response

    elif rpc == 'edit-config':

        if filter_or_config is None:
            print("Error. Cannot send an edit-config rpc without config tag")
            exit(1)

        rpc = "<edit-config><target><" + datastore + "/></target>" + filter_or_config + "</edit-config>"
        edit_config_response = man.dispatch(etree.fromstring(rpc))
        print edit_config_response

    elif rpc == 'available-profiles':

        rpc = "<available-profiles/>"
        available_profiles_response = man.dispatch(etree.fromstring(rpc))
        print available_profiles_response

    elif rpc == 'activate-profile':

        if new_profile is None:
            print("Error. Cannot send an active-profile rpc without new_profile tag")
            exit(1)

        rpc = "<activate-profile><name>" + new_profile + "</name></activate-profile>"
        activate_profiles_response = man.dispatch(etree.fromstring(rpc))
        print activate_profiles_response


    elif rpc == 'commit':

        rpc = "<commit/>"
        commit_response = man.dispatch(etree.fromstring(rpc))
        print commit_response

    elif rpc == 'discard-changes':

        rpc = "<discard-changes/>"
        discard_changes_response = man.dispatch(etree.fromstring(rpc))
        print discard_changes_response

    elif rpc == 'copy-config':

        source_target_datastores_list = source_target_datastores.split("_")
        rpc = "<copy-config><target><" + source_target_datastores_list[1] + "/></target><source><" + source_target_datastores_list[0] + "/></source></copy-config>"
        copy_config_response = man.dispatch(etree.fromstring(rpc))
        print copy_config_response

    elif rpc == 'delete-config':

        rpc = "<delete-config><target><" + datastore + "/></target></delete-config>"
        delete_config_response = man.dispatch(etree.fromstring(rpc))
        print delete_config_response

    else:
        print("Unknown RPC")


if __name__ == "__main__":
    main()
