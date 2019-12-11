from lxml import etree
import logging
from netconf import NSMAP, error, qmap, util


def remove_state(data):
    for state in data.iter("{*}state"):
        state.getparent().remove(state)



def process_changes(data_to_insert_xml, current_config_xml):

    config_tree = etree.ElementTree(current_config_xml)
    data_tree = etree.ElementTree(data_to_insert_xml)

    identifier_tag = ""
    identifier_value = ""

    for subitem_data in data_to_insert_xml.iter():
        if subitem_data.text.strip() != "":
            identifier_tag = subitem_data.tag
            identifier_value = subitem_data.text
            target_element_path = data_tree.getelementpath(subitem_data)
            target_element_data = data_tree.find(target_element_path).getparent()
            break


    target_element_config = None

    for subitem_config in current_config_xml.iter():
        if subitem_config.tag == identifier_tag and subitem_config.text.strip() == identifier_value:
            element_path = config_tree.getelementpath(subitem_config)
            target_element_config = config_tree.find(element_path).getparent()
            break

    if target_element_config is not None:
        target_element_config_tree = etree.ElementTree(target_element_config)

    target_element_data_tree = etree.ElementTree(target_element_data)

    if target_element_config is None:
        element_data_path = data_tree.getelementpath(target_element_data)
        element_data_path_split = element_data_path.split("/{")
        element_data_path_split.pop()
        parent_path = ""
        for subpath in element_data_path_split:
            parent_path = parent_path + "/{" + subpath

        parent_path = parent_path[2:len(parent_path)]
        parent_element = config_tree.find(parent_path)
        parent_element.insert(len(parent_element.getchildren()), target_element_data)

    else:

        for data_item in target_element_data.iter():

            if data_item.text.strip() != "":
                path = target_element_data_tree.getelementpath(data_item)
                config_subel = target_element_config_tree.find(path)

                if config_subel is None:
                    path_split = path.split("/{")
                    path_split.pop()
                    parent_path = ""
                    for subpath in path_split:
                        parent_path = parent_path + "/{" + subpath

                    parent_path = parent_path[2:len(parent_path)]
                    parent_element = target_element_config_tree.find(parent_path)
                    parent_element.insert(len(parent_element.getchildren()), data_item)

                else:
                    if config_subel.text != data_item.text:
                        config_subel.text = data_item.text


    return current_config_xml


def get_datastore(rpc):
    datastore_raw = etree.tostring(rpc[0][0][0])
    if "running" in datastore_raw:
        datastore = 'running'
    elif "candidate" in datastore_raw:
        datastore = 'candidate'
    elif "startup" in datastore_raw:
        datastore = 'startup'
    else:
        logging.info("Unknown datastore: "+datastore_raw)
        exit(1)

    return datastore

    
def from_filter_to_xpath(rpc):

    xpath = ''

    filter_elm = None
    for rpc_elm in rpc.iter():
        if 'filter' in rpc_elm.tag:
            filter_elm = rpc_elm

    for filter_subel in filter_elm[0].iter():
        tag = filter_subel.tag.split('}')[1]
        text = filter_subel.text
        if text is None:
            text = ''
        if text.strip() == '':
            xpath += '/' + tag
        else:
            xpath += '[' + tag + '=\'' + text + '\']'

    logging.info(xpath)

    return xpath
    
def filter_result(rpc, data, filter_or_none, debug=False):
    """Check for a user filter and prune the result data accordingly.
    :param rpc: An RPC message element.
    :param data: The data to filter.
    :param filter_or_none: Filter element or None.
    :type filter_or_none: `lxml.Element`
    """

    if filter_or_none is None:
        return data

    if ('type' not in filter_or_none.attrib) or (filter_or_none.attrib['type'] == "subtree"):
        logging.debug("Filtering with subtree")
        xpf = from_filter_to_xpath(rpc)
        return util.xpath_filter_result(data, xpf)

    elif filter_or_none.attrib['type'] == "xpath":
        if 'select' not in filter_or_none.attrib:
            raise error.MissingAttributeProtoError(rpc, filter_or_none, "select")
        xpf = filter_or_none.attrib['select']

        logging.debug("Filtering on xpath expression: %s", str(xpf))
        return util.xpath_filter_result(data, xpf)
    else:
        msg = "unexpected type: " + str(filter_or_none.attrib['type'])
        raise error.BadAttributeProtoError(rpc, filter_or_none, "type", message=msg)
