from lxml import etree
import logging

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
    
    
def subtree_filter(data,rpc):

    # Aqui estan los distintos componentes de la base de datos
    for filter_item in rpc.iter(qmap('nc')+'filter'):
        filter_tree = filter_item

    unprunned_toreturn = data
    filter_elm = filter_tree

    logging.info(etree.tostring(unprunned_toreturn,pretty_print=True))
    logging.info(etree.tostring(filter_elm,pretty_print=True))

    def check_content_match(data):
        response = False
        for child in data:
            if not(child.text == '' or child.text is None):
                response = True
        return response

    def prune_descendants(data,filter):
        logging.info("The child " + filter.tag + " is a content match: " + str(check_content_match(filter)))
        if check_content_match(filter):

            # logging.info("Elements of the content match: ------------------")
            # logging.info(etree.tostring(data,pretty_print=True))
            # logging.info(etree.tostring(filter, pretty_print=True))

            #find content match element
            for child in filter:
                if not(child.text is '' or child.text is None):
                    matching_elem = child
            # logging.info("Looking for the element " + matching_elem.tag + " , " + matching_elem.text)

            # Checking if the current elem matches the seached one
            if data.find(matching_elem.tag) is not None and data.find(matching_elem.tag).text == matching_elem.text:
                # logging.info("This element matches")
                #logging.info(etree.tostring(data,pretty_print=True))
                #logging.info(etree.tostring(filter, pretty_print=True))
                if len(list(filter)) > 1:
                    matching_elem.text = ''
                    logging.info("Containment nodes inside")
                    logging.info(etree.tostring(data,pretty_print=True))
                    logging.info(etree.tostring(filter, pretty_print=True))
                    prune_descendants(data,filter)
            else:
                # logging.info("This element doesnt match")
                data.getparent().remove(data)

        else:
            for child in data:

                if len(list(filter)) is not 0:
                    if filter.find(child.tag) is not None:
                        logging.info("Element " + child.tag + " found in data, so persisting it")
                        prune_descendants(child, filter[0])

                    else:
                        logging.info("Element " + child.tag + " missing in data, deleting it")
                        data.remove(child)

    prune_descendants(unprunned_toreturn,filter_elm)

    #logging.info(etree.tostring(unprunned_toreturn,pretty_print=True))

    return unprunned_toreturn
    
def filter_result(rpc, data, filter_or_none, debug=False):
    """Check for a user filter and prune the result data accordingly.
    :param rpc: An RPC message element.
    :param data: The data to filter.
    :param filter_or_none: Filter element or None.
    :type filter_or_none: `lxml.Element`
    """
    if filter_or_none is None:
        return data

    if 'type' not in filter_or_none.attrib:
        # Check for the pathalogical case of empty filter since that's easy to implement.
        if not filter_or_none.getchildren():
            return elm("data")
        # xpf = Convert subtree filter to xpath!

    elif filter_or_none.attrib['type'] == "subtree":
        logger.debug("Filtering with subtree")
        return subtree_filter(data,rpc)

    elif filter_or_none.attrib['type'] == "xpath":
        if 'select' not in filter_or_none.attrib:
            raise error.MissingAttributeProtoError(rpc, filter_or_none, "select")
        xpf = filter_or_none.attrib['select']

        logger.debug("Filtering on xpath expression: %s", str(xpf))
        return xpath_filter_result(data, xpf)
    else:
        msg = "unexpected type: " + str(filter_or_none.attrib['type'])
        raise error.BadAttributeProtoError(rpc, filter_or_none, "type", message=msg)